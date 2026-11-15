#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""取 arXiv e-print 源码（作者原始 LaTeX），作为翻译与对账的基准。

为什么不在 PDF 上做提取
------------------------
MinerU 是「从版面反推结构」：能认出公式、表格、脚注，但认出不等于认得对——
多行公式被切碎、正体斜体被抹平、上下标压平、`\text{}` 里的标点被换掉、
参考文献年份并进正文。arXiv 论文的作者源码里本来就带着真公式、真定理环境、
真 `\cite` 与 `\bibitem`，从 PDF 反推等于把已知答案丢掉再猜一遍，还得为猜错
的部分付校对成本。

这个脚本只做五件事：下载 → 安全解包 → 找主文件 → 展开 `\input` → 出结构清单。
它**不**试图把 LaTeX 完整翻译成 Markdown（那是 pandoc 和模型的活），但会给出
一份能逐条核对的清单：多少章、多少公式、多少定理、多少图、多少引用。

用法
----
    python arxiv_src.py 2207.01848 -o _work/arxiv
    python arxiv_src.py https://arxiv.org/abs/2112.10510v2 -o _work/arxiv
    python arxiv_src.py --from Hollmann2022_原文.md -o _work/arxiv
    python arxiv_src.py 2207.01848 -o _work/arxiv --md      # 顺手 pandoc 转一份 Markdown
    python arxiv_src.py 2207.01848 -o _work/arxiv --main main_neurips.tex

产出
----
    <out>/
      src/            原始解压件，保持作者目录结构（含 .sty/.bib/.bbl）
      main.tex        主文件原样（`\input` 保留，便于对照作者结构）
      main.flat.tex   展开 `\input` 后的全文，模型直接读这份
      figures/        正文实际引用到的图（路径已改写为 figures/…）
      结构清单.md     章节树、公式、定理、图、表、引用、脚注的计数与明细
      原文.md         可选（有 pandoc 且加 --md 才出）
      arxiv.json      条目号、主文件、各项统计

退出码：0 拿到源码；2 拿到但缺图或没有参考文献；1 没有源码（只有 PDF）或网络失败。
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request

EPRINT = "https://arxiv.org/e-print/%s"
METADATA = "https://export.arxiv.org/api/query?id_list=%s"
UA = "translation-skills/1.0 (arxiv-src; translation research tool)"

MAIN_NAMES = ("main", "paper", "ms", "manuscript", "article", "root")

RE_DOCCLASS = re.compile(r"\\documentclass\b")
RE_BEGINDOC = re.compile(r"\\begin\s*\{document\}")
RE_INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
RE_GRAPHICS = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
RE_SECTION = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\s*(?:\[[^\]]*\])?\s*\{")
RE_EQ_ENV = re.compile(r"\\begin\s*\{(equation|align|gather|multline|eqnarray|flalign)\*?\}")
RE_LABEL_EQ = re.compile(r"\\label\s*\{(eq:[^}]+)\}")
RE_LABEL_ANY = re.compile(r"\\label\s*\{([^}]+)\}")
RE_THM = re.compile(r"\\begin\s*\{(theorem|lemma|proposition|corollary|definition|"
                    r"assumption|remark|claim|conjecture|example)\*?\}")
RE_FLOAT = re.compile(r"\\begin\s*\{(figure|table)\*?\}")
RE_CITE = re.compile(r"\\(?:cite|citep|citet|parencite|autocite|textcite)\*?\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
RE_BIBITEM = re.compile(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
RE_FOOTNOTE = re.compile(r"\\footnote\s*\{")
RE_GRAPHIC_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ps")


class SourceUnavailable(RuntimeError):
    """该条目拿不到 LaTeX 源码（常见原因：作者只上传了 PDF）。"""


# ---------------------------------------------------------------- 下载与解包

def parse_id(raw):
    """从 URL、``arXiv:xxx``、裸 ID 里取出条目号（保留版本后缀）。"""
    s = (raw or "").strip()
    m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", s)
    if m:
        return m.group(1) + (m.group(2) or "")
    m = re.search(r"([a-z][a-z\-]*(?:\.[A-Z]{2})?/\d{7})(v\d+)?", s, re.I)
    if m:
        return m.group(1) + (m.group(2) or "")
    raise SystemExit("认不出 arXiv 条目号：%s（示例：2207.01848 / https://arxiv.org/abs/2112.10510v2）" % raw)


def download(aid, timeout=120, retries=2):
    """取 e-print。返回 (bytes, content-type)。普通 HTTP 代理在此处照常生效。"""
    url = EPRINT % aid
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), (r.headers.get("Content-Type") or "")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            if i < retries:
                time.sleep(2 + 2 * i)
    raise SourceUnavailable("下载 %s 失败：%s" % (url, last))


def _safe_members(tf):
    """拒绝绝对路径、``..`` 与链接，只放行普通文件与目录。"""
    for m in tf.getmembers():
        p = pathlib.PurePosixPath(m.name)
        if p.is_absolute() or ".." in p.parts:
            continue
        if m.issym() or m.islnk() or not (m.isfile() or m.isdir()):
            continue
        yield m


def unpack(raw, dest):
    """把 e-print 落盘。兼容 tar.gz、纯 gz 单文件、未压缩 tar、裸 tex。"""
    dest.mkdir(parents=True, exist_ok=True)
    if raw[:5] == b"%PDF-":
        raise SourceUnavailable("这个条目只提供 PDF（作者没有上传 LaTeX 源码），"
                                "请改用 mineru_extract.py 从 PDF 提取。")
    if raw[:2] == b"\x1f\x8b":
        try:
            tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
        except tarfile.ReadError:
            data = gzip.decompress(raw)
            if data[:5] == b"%PDF-":
                raise SourceUnavailable("这个条目只有压缩的 PDF，没有 LaTeX 源码。")
            (dest / "main.tex").write_bytes(data)
            return dest
        with tf:
            for m in _safe_members(tf):
                try:
                    tf.extract(m, path=str(dest), filter="data")
                except TypeError:          # Python < 3.12 没有 filter 参数
                    tf.extract(m, path=str(dest))
        return dest
    if b"\\documentclass" in raw[:200000]:
        (dest / "main.tex").write_bytes(raw)
        return dest
    raise SourceUnavailable("未知的 e-print 格式（前 8 字节：%r）" % raw[:8])


# ---------------------------------------------------------------- 主文件与展开

def strip_comments(text):
    """去掉 TeX 注释。``\\%`` 是转义百分号，不算注释。

    这一步不能省：作者常把旧版本整段注释掉（``%\\input{...}``、``%\\begin{document}``），
    不剥掉就会把注释里的公式、脚注、图也算进结构清单，还会去展开注释掉的 \\input。
    """
    out = []
    for line in text.splitlines():
        buf, i = [], 0
        while i < len(line):
            if line[i] == "\\" and i + 1 < len(line):
                buf.append(line[i:i + 2])
                i += 2
                continue
            if line[i] == "%":
                break
            buf.append(line[i])
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


def find_mains(root):
    out = []
    for f in sorted(root.rglob("*.tex")):
        try:
            t = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if RE_DOCCLASS.search(t) and RE_BEGINDOC.search(t):
            out.append((f, len(t)))
    return out


def pick_main(mains, prefer=None, root=None):
    """多个 `\\documentclass` 文件时：显式指定 > 常见主文件名 > 体量最大。"""
    if prefer:
        p = (root / prefer) if root else pathlib.Path(prefer)
        if not p.is_file():
            raise SystemExit("指定的主文件不存在：%s" % p)
        return p
    for name in MAIN_NAMES:
        for f, _ in mains:
            if f.stem.lower() == name:
                return f
    if not mains:
        raise SourceUnavailable("包里没有找到带 \\documentclass 与 \\begin{document} 的 .tex")
    return max(mains, key=lambda x: x[1])[0]


def expand_inputs(path, root, seen=None, depth=0):
    """递归展开 ``\\input``/``\\include``，每段包上注释边界便于回溯。"""
    seen = seen if seen is not None else set()
    if depth > 10 or path in seen:
        return ""
    seen.add(path)
    text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))

    def repl(m):
        rel = m.group(1).strip()
        cands = [root / rel, path.parent / rel]
        if not rel.endswith(".tex"):
            cands = [c.with_suffix(".tex") for c in cands[:1]] + cands
        for c in cands:
            if c.is_file():
                inner = expand_inputs(c, root, seen, depth + 1)
                return "\n%%%% ==== input{%s} ==== %%%%\n%s\n%%%% ==== end input{%s} ==== %%%%\n" % (
                    rel, inner, rel)
        return m.group(0)

    return RE_INPUT.sub(repl, text)


# ---------------------------------------------------------------- 图

def collect_figures(tex, root, out):
    """把正文实际引用到的图复制到 ``<out>/figures``，并把 tex 里的路径改过去。"""
    figdir = out / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    copied, missing, renamed = {}, [], {}

    def repl(m):
        rel = m.group(1).strip()
        cands = [root / rel, (root / rel).with_suffix(".pdf"), (root / rel).with_suffix(".png"),
                 (root / rel).with_suffix(".jpg"), (root / rel).with_suffix(".jpeg"),
                 (root / rel).with_suffix(".eps")]
        cands = [c for c in cands if c.is_file()]
        if not cands:
            missing.append(rel)
            return m.group(0)
        src = cands[0]
        if rel in copied:
            return m.group(0).replace("{%s}" % rel, "{%s}" % copied[rel])
        dst = figdir / src.name
        n = 2
        while dst.exists() and dst.stat().st_size != src.stat().st_size:
            dst = figdir / ("%s_%d%s" % (src.stem, n, src.suffix))
            n += 1
        shutil.copy2(src, dst)
        rel_new = "figures/" + dst.name
        copied[rel] = rel_new
        if src.name != pathlib.Path(rel).name:
            renamed[rel] = rel_new
        return m.group(0).replace("{%s}" % rel, "{%s}" % rel_new)

    return RE_GRAPHICS.sub(repl, tex), copied, missing, renamed


# ---------------------------------------------------------------- 结构清单

def _count(pattern, text):
    return len(pattern.findall(text))


def _sections(text):
    """按出现顺序列标题，附 numberless 标记。"""
    out = []
    for m in re.finditer(r"\\(section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*\{", text):
        level = {"section": 1, "subsection": 2, "subsubsection": 3}[m.group(1)]
        i, depth, buf = m.end(), 1, []
        while i < len(text) and depth:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if not depth:
                    break
            buf.append(c)
            i += 1
        title = re.sub(r"\s+", " ", "".join(buf)).strip()
        out.append((level, title[:90]))
    return out


def _braced(text, start):
    """从 ``{`` 之后取配平内容，跳过 ``\\{``/``\\}`` 转义。"""
    depth, i, buf = 1, start, []
    while i < len(text) and depth:
        c = text[i]
        if c == "\\":
            buf.append(text[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if not depth:
                break
        buf.append(c)
        i += 1
    return "".join(buf), i


def extract_footnotes(tex):
    """按出现顺序抽 ``\\footnote{}``。tex 路线的页码不可知，靠序号与正文顺序对账。"""
    out = []
    for m in re.finditer(r"\\footnote\s*\{", tex):
        body, _ = _braced(tex, m.end())
        out.append(re.sub(r"\s+", " ", body).strip())
    return out


RE_MACRO = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator)\*?\s*"
    r"\{?\\\{?([A-Za-z@]+)\}?\}?\s*(?:\[\d\])?\s*\{")


def extract_macros(tex):
    """抽自定义宏。tex 源里到处都是 ``\\methodname{}``，不查定义没法译。"""
    out = {}
    for m in RE_MACRO.finditer(tex):
        body, _ = _braced(tex, m.end())
        body = re.sub(r"\s+", " ", body).strip()
        if body and len(body) < 200:
            out[m.group(1)] = body
    for m in re.finditer(r"\\def\s*\\([A-Za-z@]+)\s*\{", tex):
        body, _ = _braced(tex, m.end())
        body = re.sub(r"\s+", " ", body).strip()[:200]
        if body:
            out.setdefault(m.group(1), body)
    return out


def structure(tex):
    cites = sorted({k.strip() for grp in RE_CITE.findall(tex) for k in grp.split(",") if k.strip()})
    st = {
        "sections": _count(RE_SECTION, tex),
        "section_tree": _sections(tex),
        "equation_envs": _count(RE_EQ_ENV, tex),
        "display_brackets": len(re.findall(r"\\\[", tex)),
        "display_dollars": len(re.findall(r"\$\$", tex)) // 2,
        "labels_eq": RE_LABEL_EQ.findall(tex),
        "theorem_envs": _count(RE_THM, tex),
        "figures": len(re.findall(r"\\begin\s*\{figure\*?\}", tex)),
        "graphics": len(RE_GRAPHICS.findall(tex)),
        "inline_math": len(re.findall(r"(?<![\\$])\$(?!\$)", tex)) // 2,
        "tables": len(re.findall(r"\\begin\s*\{table\*?\}", tex)),
        "captions": _count(re.compile(r"\\caption\s*[\[{]"), tex),
        "cites": cites,
        "bibitems": RE_BIBITEM.findall(tex),
        "footnotes": _count(RE_FOOTNOTE, tex),
        "footnote_texts": extract_footnotes(tex),
        "appendix": bool(re.search(r"\\appendix\b", tex)),
    }
    return st


def bib_entries(root):
    """数 .bib 里的条目。用 BibTeX 的稿子没有 \\bibitem，只数它会是 0。"""
    n = 0
    for f in root.rglob("*.bib"):
        t = f.read_text(encoding="utf-8", errors="ignore")
        n += len(re.findall(r"@(?!string|comment|preamble)\w+\s*[{(]", t, re.I))
    return n


def near_misses(root, rel):
    """缺图时找找同名不同扩展名的文件，省得人再翻一遍包。"""
    stem = pathlib.Path(rel).stem
    hits = sorted({p.relative_to(root).as_posix() for p in root.rglob(stem + ".*")})
    return hits[:3]


def _ref_desc(st, bib_n):
    """参考文献口径：BibTeX 稿子只有 \\cite 没有 \\bibitem，直接报 0 会误导。"""
    if st["bibitems"]:
        return "%d 条（\\bibitem）" % len(st["bibitems"])
    if bib_n:
        return "BibTeX：.bib 共 %d 条，正文引用 %d 个键" % (bib_n, len(st["cites"]))
    return "未找到"


def report_md(aid, main, st, figs, missing, renamed, tex_len, bib_n=0, alt_mains=None, root=None, macros=None):
    L = ["# 结构清单 — arXiv:%s" % aid, "",
         "主文件：`%s`（展开后 %s 字符）" % (main.name, format(tex_len, ",")), "",
         "| 项 | 数量 |", "|---|---|",
         "| 章节标题（含各级） | %d |" % st["sections"],
         "| 编号公式环境 | %d |" % st["equation_envs"],
         "| 行间公式（`\\[` / `$$`） | %d |" % (st["display_brackets"] + st["display_dollars"]),
         "| 公式 label | %d |" % len(st["labels_eq"]),
         "| 定理类环境 | %d |" % st["theorem_envs"],
         "| 图（figure 环境） | %d |" % st["figures"],
         "| 图（`\\includegraphics` 调用） | %d |" % st.get("graphics", 0),
         "| 表（table 环境） | %d |" % st["tables"],
         "| caption | %d |" % st["captions"],
         "| `\\cite` 键（去重） | %d |" % len(st["cites"]),
         "| 参考文献 | %s |" % _ref_desc(st, bib_n),
         "| `\\footnote` | %d |" % st["footnotes"],
         "| 附录 | %s |" % ("有" if st["appendix"] else "无"),
         "", "## 章节树", ""]
    for level, title in st["section_tree"]:
        L.append("%s- %s" % ("  " * (level - 1), title))
    if not st["section_tree"]:
        L.append("（没有 section 级标题，可能用了自定义章节命令）")
    if alt_mains and len(alt_mains) > 1:
        L += ["", "## 包里有 %d 个可编译主文件" % len(alt_mains), "",
              "默认取 `%s`。**先确认它与要译的那一版一致**，不一致用 `--main` 指定：" % main.name, ""]
        for f, n in sorted(alt_mains, key=lambda x: -x[1])[:6]:
            L.append("- `%s`（%s 字符）%s" % (f, format(n, ","),
                                             " ← 当前" if f.name == main.name else ""))
    if missing:
        L += ["", "## 缺图（tex 里引用了但包里没有）", ""]
        for m in missing:
            L.append("- `%s`" % m)
            near = near_misses(root, m) if root else []
            if near:
                L.append("  - 包里同名文件：%s" % "、".join("`%s`" % x for x in near))
    if renamed:
        L += ["", "## 图路径改写", ""] + ["- `%s` → `%s`" % (k, v) for k, v in sorted(renamed.items())]
    if macros:
        L += ["", "## 自定义宏（%d 个）" % len(macros), "",
              "译到这些命令时照表还原，别当正文、也别丢：", "",
              "| 宏 | 定义 |", "|---|---|"]
        for k, v in sorted(macros.items())[:40]:
            L.append("| `\\%s` | `%s` |" % (k, v.replace("|", "\\|")[:80]))
        if len(macros) > 40:
            L.append("| … | 其余 %d 个见 `main.flat.tex` |" % (len(macros) - 40))
    fn_texts = st.get("footnote_texts") or []
    if fn_texts:
        L += ["", "## 脚注明细（`\\footnote` 顺序）", "",
              "页码在 tex 里不可知，用序号对账：译文的 `## 脚注` 节必须同样有 %d 条。" % len(fn_texts), ""]
        for i, s in enumerate(fn_texts, 1):
            L.append("%d. %s" % (i, (s[:110] + "…") if len(s) > 110 else s))
    L += ["", "## 怎么用这份清单", "",
          "译文定稿后逐项对照：章节数、公式数、定理数、图表数、引用键数必须一致；"
          "少一个就是漏译或漏排版，多一个就是凭空添加。明细见 `main.flat.tex`。"]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 入口

def from_md_frontmatter(md):
    text = pathlib.Path(md).read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        raise SystemExit("这个 Markdown 没有 front matter，读不到 arxiv 字段：%s" % md)
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip().lower() in ("arxiv", "eprint", "arxiv_id") and v.strip():
            return v.strip().strip('"').strip("'")
    raise SystemExit("front matter 里没有 arxiv 字段：%s" % md)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="取 arXiv e-print 的 LaTeX 源码，展开 \\input，产出结构清单。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python arxiv_src.py 2207.01848 -o _work/arxiv --md")
    ap.add_argument("target", nargs="?", help="arXiv 条目号或 abs/e-print URL")
    ap.add_argument("-o", "--outdir", default="_work/arxiv", help="输出目录")
    ap.add_argument("--from", dest="from_md", default=None, help="从译文/原文的 front matter 读 arxiv 号")
    ap.add_argument("--main", default=None, help="指定主 .tex（包里常有多个版本）")
    ap.add_argument("--md", action="store_true", help="有 pandoc 时顺手转一份 原文.md")
    ap.add_argument("--no-flat", action="store_true", help="不生成展开后的 main.flat.tex")
    ap.add_argument("--timeout", type=int, default=120, help="下载超时秒数")
    ap.add_argument("--refresh", action="store_true", help="忽略已存在的 src/，重新下载")
    args = ap.parse_args(argv)

    if not args.target and not args.from_md:
        ap.error("给一个 arXiv 条目号，或用 --from <md> 从 front matter 读")
    aid = parse_id(args.target or from_md_frontmatter(args.from_md))
    out = pathlib.Path(args.outdir)
    src = out / "src"

    if src.exists() and any(src.iterdir()) and not args.refresh:
        print("复用已解包的 src/（要重下加 --refresh）")
    else:
        print("下载 arXiv:%s …" % aid)
        raw, ctype = download(aid, timeout=args.timeout)
        print("  收到 %s 字节（%s）" % (format(len(raw), ","), ctype or "未知类型"))
        unpack(raw, src)

    mains = find_mains(src)
    print("  找到 %d 个带 \\documentclass 的 .tex" % len(mains))
    for f, n in sorted(mains, key=lambda x: -x[1])[:5]:
        print("    %-52s %s 字符" % (f.relative_to(src), format(n, ",")))
    main_tex = pick_main(mains, args.main, root=src)
    print("  主文件：%s" % main_tex.relative_to(src))

    raw_tex = main_tex.read_text(encoding="utf-8", errors="ignore")
    (out / "main.tex").write_text(raw_tex, encoding="utf-8")

    flat = expand_inputs(main_tex, src) if not args.no_flat else raw_tex
    flat, copied, missing, renamed = collect_figures(flat, src, out)
    if not args.no_flat:
        (out / "main.flat.tex").write_text(flat, encoding="utf-8")

    st = structure(flat)
    bib_n = bib_entries(src)
    macros = extract_macros(flat)
    (out / "结构清单.md").write_text(
        report_md(aid, main_tex, st, copied, missing, renamed, len(flat),
                  bib_n=bib_n, alt_mains=mains, root=src, macros=macros), encoding="utf-8")

    md_note = ""
    if args.md:
        pandoc = shutil.which("pandoc")
        if not pandoc:
            md_note = "没装 pandoc，跳过 原文.md（装好后重跑 --md 即可）"
        else:
            target = out / "原文.md"
            p = subprocess.run([pandoc, str(out / "main.flat.tex"), "-f", "latex", "-t", "gfm",
                                "--wrap=none", "--resource-path", str(out), "-o", str(target)],
                               capture_output=True, text=True)
            md_note = ("已转出 原文.md（pandoc 不展开自定义宏，转换后必须对照 结构清单.md 自查）"
                       if p.returncode == 0 else
                       "pandoc 转换失败（rc=%d）：%s" % (p.returncode, (p.stderr or "")[:200]))

    fn_texts = st.get("footnote_texts") or []
    if fn_texts:
        import csv as _csv
        with open(out / "脚注.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.writer(fh)
            w.writerow(["page", "marker", "category", "text", "plain", "bbox",
                        "in_full_md", "in_target", "zh", "in_pdf"])
            for i, s in enumerate(fn_texts, 1):
                w.writerow(["", i, "footnote", s, s, "", "no", "no", "", ""])
        print("  脚注清单：%d 条（tex 源，页码不可知）" % len(fn_texts))

    meta = {"arxiv": aid, "main": str(main_tex.relative_to(src)), "chars": len(flat),
            "figures_copied": len(copied), "figures_missing": missing,
            "stats": {k: (len(v) if isinstance(v, list) else v)
                      for k, v in st.items() if k != "section_tree"},
            "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (out / "arxiv.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n产出目录：%s" % out.resolve())
    print("  章节 %d ｜ 编号公式 %d ｜ 行内公式 %d ｜ 定理 %d ｜ 图 %d ｜ 表 %d ｜ 引用键 %d ｜ 脚注 %d"
          % (st["sections"], st["equation_envs"], st.get("inline_math", 0), st["theorem_envs"],
             st["figures"], st["tables"], len(st["cites"]), st["footnotes"]))
    if copied:
        print("  图已收 %d 张" % len(copied))
    if macros:
        print("  自定义宏 %d 个（见结构清单末尾，译时照表还原）" % len(macros))
    if missing:
        print("  [!] %d 张图在包里找不到：%s" % (len(missing), ", ".join(missing[:5])))
    if md_note:
        print("  %s" % md_note)
    print("\n下一步：以 main.flat.tex 为翻译基准；译文定稿后按 结构清单.md 逐项对账。")

    has_bib = bool(st["bibitems"]) or any(src.rglob("*.bib")) or any(src.rglob("*.bbl"))
    if missing or not has_bib:
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SourceUnavailable as e:
        print("[FAIL] %s" % e)
        sys.exit(1)
