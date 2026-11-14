#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MinerU 脚注体检与补回。

MinerU（vlm 尤其）常把期刊页底的脚注整批丢掉：正文里留下若干
`<sup>n</sup>` 标记，脚注正文一条也没有；有时标记还会被塞进行内公式
（`^ { 8 }`）或退化成句末一个裸数字。在这样一份底稿上翻译，脚注内容就
被"洗"掉了，后面的结构对账也查不出来——块数本来就对得上。

本脚本做两件事：

1. 从 **PDF 文字层**独立检出页底脚注（编号 + 缩进正文，含跨页续文），
   与 MinerU 的 Markdown 里的标记／定义对账，给出可读的体检报告与 CSV。
2. 可选 `--patch`：把 `<sup>n</sup>` 统一成 `[^n]`，并把缺失的脚注定义
   以 `[^n]: ...` 写回文末；不覆盖原文件、不猜正文里标记的位置。

文字层优先 `pdftotext -layout`（外部命令，随 poppler / TeX Live 安装），
没有则依次试 PyMuPDF、pdfplumber、pypdf；都不行时用 `--text` 传入自己
导出的文字层。除此之外只用 Python 标准库。

用法
----
    python footnotes.py paper.pdf --md _work/extract/paper/full.md -o _work/ --strict
    python footnotes.py paper.pdf --md full.md --patch _work/full_脚注已补.md -o _work/
    python footnotes.py --md full.md --text pdftotext.txt -o _work/   # 已有文字层
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

# ---------------------------------------------------------------- 文字层

PAGE_BREAK = "\f"
LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl",
             "\ufb03": "ffi", "\ufb04": "ffl", "\u2010": "-", "\u2011": "-"}


def from_pdftotext(pdf: str) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-layout", "-enc", "UTF-8", pdf, "-"],
                           capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"  ! pdftotext 调用异常：{e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        detail = r.stderr.decode("utf-8", errors="replace")[:200]
        print(f"  ! pdftotext 退出码 {r.returncode}：{detail}", file=sys.stderr)
        return None
    return r.stdout.decode("utf-8", errors="replace")


def from_library(pdf: str):
    """Try optional PDF libraries, in order. Return (text, backend) or None."""
    try:
        import fitz  # type: ignore
        doc = fitz.open(pdf)
        return PAGE_BREAK.join(p.get_text("text") for p in doc), "PyMuPDF"
    except Exception:
        pass
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(pdf) as doc:
            return PAGE_BREAK.join(p.extract_text(layout=True) or "" for p in doc.pages), "pdfplumber"
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore
        rd = PdfReader(pdf)
        return PAGE_BREAK.join(p.extract_text() or "" for p in rd.pages), "pypdf"
    except Exception:
        pass
    return None


def load_text(pdf: str | None, text_file: str | None):
    if text_file:
        raw = open(text_file, encoding="utf-8-sig", errors="replace").read()
        return raw, f"--text {text_file}"
    if not pdf:
        return None, "无"
    t = from_pdftotext(pdf)
    if t is not None:
        return t, "pdftotext -layout"
    got = from_library(pdf)
    if got:
        return got[0], got[1]
    raise SystemExit(
        "取不到 PDF 文字层。安装 poppler（pdftotext）或用 "
        "pdftotext -layout paper.pdf pdftotext.txt 导出后加 --text pdftotext.txt。"
    )


def clean(s: str) -> str:
    for a, b in LIGATURES.items():
        s = s.replace(a, b)
    return s


# ---------------------------------------------------------------- PDF 侧：页底脚注

NUM_LINE = re.compile(r"^\s{0,8}(\d{1,2})\s*$")
# 期刊脚注正文的缩进因刊而异：本篇有 4 空格的，也有只缩进 2 空格的
# （页 6 的脚注 4、5 就是 2 空格）。放宽到 >=2，靠"编号必须递增"挡误报。
INDENTED = re.compile(r"^\s{2,}\S")
# 公式残片的判定要留余地：脚注 4 的首行里有 `P(X . xi )`，只凭 P( 就判公式
# 会把整条脚注丢掉。有连续英文散文（两个实词相邻）的一律当脚注正文。
FORMULAISH = re.compile(r"\\tag|\\frac|\\mathbb|\\left|[≥≤]|[=]{2,}")
PROSE = re.compile(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}")
HEADER = re.compile(r"REVIEW OF|POLITICAL ECONOMY|J\.\s*KAPELLER|^\s*\d{1,3}\s+[A-Z]\.")
SENT_END = re.compile(r"[.;!?…'\"\u2019\u201d\)\]]\s*$")
RECOVERED_MARK = "<!-- FOOTNOTES-RECOVERED -->"


def join_lines(lines):
    """把折行的脚注正文接成一段。

    行末连字符分两种：硬断词的（`abso-` + `lute`）去掉连字符拼回去；复合专名
    的（`Kaldor-` + `Verdoorn`）连字符是词本身的一部分，去掉就成了 KaldorVerdoorn。
    判据取"下一行首字母是否大写"——硬断词的下半截永远是小写。
    """
    out = ""
    for ln in lines:
        cur = ln.strip()
        if not cur:
            continue
        if not out:
            out = cur
            continue
        if out.endswith("-") and cur and cur[0].isalpha():
            if cur[0].isupper():
                out = out + cur           # Kaldor- + Verdoorn -> Kaldor-Verdoorn
            else:
                out = out[:-1] + cur      # abso- + lute -> absolute
        else:
            out += " " + cur
    return re.sub(r"\s{2,}", " ", out).strip()


def extract_from_pdf(raw: str, drop: set[int], max_num: int):
    """返回 (脚注列表, 缺口列表, 页数)。编号必须递增，用来排除公式分子/页码误报。"""
    pages = clean(raw).split(PAGE_BREAK)
    items, gaps = [], []
    expected = 1
    for pno, page in enumerate(pages, 1):
        lines = page.split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        i = 0
        while i < len(lines):
            m = NUM_LINE.match(lines[i])
            if not m:
                i += 1
                continue
            n = int(m.group(1))
            if n > max_num or n in drop or n < expected:
                i += 1
                continue
            # 候选块：编号行之后到页末／下一个编号行
            j, body = i + 1, []
            while j < len(lines):
                if NUM_LINE.match(lines[j]) and lines[j].strip().isdigit():
                    nxt = int(lines[j].strip())
                    if nxt == n + 1 or nxt > n:
                        break
                body.append(lines[j])
                j += 1
            first = next((x for x in body if x.strip()), "")
            looks_formula = FORMULAISH.search(first) and not PROSE.search(first)
            if (not INDENTED.match(first) or len(first.strip()) < 25
                    or looks_formula or HEADER.search(first)):
                i += 1
                continue
            if n > expected:
                gaps.extend(range(expected, n))
            txt = join_lines(body)
            if len(txt) < 25:
                i += 1
                continue
            items.append({"num": n, "page": pno, "text": txt,
                          "continued_from": None, "continued_on": None})
            expected = n + 1
            i = j

        # 跨页续文：页末有整体缩进块、且上一条脚注未以句末标点收尾
        if items and not SENT_END.search(items[-1]["text"]):
            tail = [x for x in lines[-4:] if x.strip()]
            cand = [x for x in tail if INDENTED.match(x) and not HEADER.search(x)]
            if cand and re.match(r"^\s{3,}[a-z\u2018\u201c]", cand[0]):
                extra = join_lines(cand)
                if len(extra) > 15:
                    items[-1]["text"] += " " + extra
                    items[-1]["continued_on"] = pno
    return items, gaps, len(pages)


# ---------------------------------------------------------------- Markdown 侧

SUP = re.compile(r"<sup>\s*(\d{1,2})\s*</sup>")
FN_REF = re.compile(r"\[\^(\d{1,2})\](?!:)")
FN_DEF = re.compile(r"^\[\^(\d{1,2})\]:\s*(.*)$", re.M)
IN_MATH = re.compile(r"\^\s*\{\s*(\d{1,2})\s*\}")
INLINE_MATH = re.compile(r"(?<!\\)\$([^$\n]*)\$")
BARE = re.compile(r"[.;]\s+(\d{1,2})(?=\s|$)")
TAIL_NUM = re.compile(r"\s(\d{1,2})\s*$")
UNICODE_SUP = {"\u00b9": 1, "\u00b2": 2, "\u00b3": 3,
               "\u2070": 0, "\u2074": 4, "\u2075": 5, "\u2076": 6,
               "\u2077": 7, "\u2078": 8, "\u2079": 9}


def scan_markdown(md: str):
    marks = set()
    for m in SUP.finditer(md):
        marks.add(int(m.group(1)))
    for m in FN_REF.finditer(md):
        marks.add(int(m.group(1)))
    for ch, n in UNICODE_SUP.items():
        if ch in md:
            marks.add(n)
    defs = {int(m.group(1)) for m in FN_DEF.finditer(md)}
    suspects = []
    for i, line in enumerate(md.split("\n"), 1):
        ctx = line.strip()[:110]
        # 公式内部：^ { n } 形态（MinerU 把脚注标记塞进 LaTeX 的常见形态）
        for seg in INLINE_MATH.findall(line):
            for m in IN_MATH.finditer(seg):
                suspects.append((i, "行内公式里的上标", m.group(1), ctx))
        # 公式外部：先抹掉行内公式，避免把 `x ^ { 2 . 8 }` 里的小数当脚注编号
        plain = INLINE_MATH.sub(" ", line)
        for m in TAIL_NUM.finditer(plain):
            suspects.append((i, "行末孤立数字", m.group(1), ctx))
        for m in BARE.finditer(plain):
            suspects.append((i, "句末裸数字", m.group(1), ctx))
    return marks, defs, suspects


# ---------------------------------------------------------------- 报告与补回

def write_report(path, pdf_name, md_name, backend, pages, items, gaps,
                 marks, defs, suspects, drop, wanted):
    nums = [x["num"] for x in items]
    missing_defs = [n for n in nums if n not in defs]
    missing_marks = [n for n in nums if n not in marks]
    # 无脚注的文献不该被 --strict 卡住；这时三项都为空，结论是 PASS + 一句提醒。
    ok = not missing_defs and not missing_marks and not gaps
    lines = [
        "# 脚注体检",
        "",
        f"- PDF：`{pdf_name}`",
        f"- MinerU 稿：`{md_name}`",
        f"- 文字层：{backend}（{pages} 页）",
        f"- 排除编号：{', '.join(map(str, sorted(drop))) or '无'}",
        "",
        f"**PDF 页底检出 {len(items)} 条脚注**（编号 {min(nums) if nums else '—'}–{max(nums) if nums else '—'}）"
        + (f"，编号缺口：{gaps}" if gaps else "，编号连续"),
        f"跨页续文合并：{sum(1 for x in items if x['continued_on'])} 处"
        + ("（" + "、".join(f"脚注 {x['num']} 续于第 {x['continued_on']} 页"
                         for x in items if x['continued_on']) + "）"
           if any(x["continued_on"] for x in items) else ""),
        "",
        f"- MinerU 稿中的脚注标记：{len(marks)} 个 → {sorted(marks) or '无'}",
        f"- MinerU 稿中的脚注定义：{len(defs)} 条 → {sorted(defs) or '无'}",
        f"- **缺失定义**：{missing_defs or '无'}",
        f"- **正文缺标记**：{missing_marks or '无'}（这些编号的标记多半藏在下面的可疑位置）",
        "",
        "## 可疑标记（只列 PDF 有脚注、MinerU 稿却没标记的编号）",
        "",
        f"待补标记编号：{sorted(wanted) or '无'}。数学平方 `^ {{ 2 }}`、年份、小数一律不列。",
        "",
    ]
    if suspects:
        for ln, kind, n, ctx in suspects[:40]:
            lines.append(f"- 第 {ln} 行｜{kind}｜候选编号 {n}｜`{ctx}`")
        if len(suspects) > 40:
            lines.append(f"- …另有 {len(suspects) - 40} 处")
    else:
        lines.append("- 无")
    lines += [
        "",
        "## 结论",
        "",
    ]
    if not items:
        lines.append("未检出 PDF 脚注。可能是无脚注文献，也可能是文字层不可读——"
                     "翻两页页底确认一次再进入翻译。")
        lines.append("结论：PASS（无脚注可丢）")
    elif ok:
        lines.append("PASS —— 标记与定义齐全，可以进入翻译。")
    elif missing_marks and not missing_defs:
        lines.append(f"**部分完成 —— 定义已齐，正文还缺 {len(missing_marks)} 个标记。**")
        lines.append("按上表行号对照 PDF，把藏在 `^ { n }`、`\\mathrm{...}` 或行末裸数字里的")
        lines.append(f"标记手工补成 `[^n]`（待补编号 {missing_marks}），重跑本脚本确认 PASS。")
    else:
        lines.append("**FAIL —— 脚注正文整批或部分丢失，禁止带着这份底稿进入翻译。**")
        lines.append("")
        lines.append("第一步，补回定义与形态明确的标记：")
        lines.append("```bash")
        lines.append(f"python scripts/footnotes.py <PDF> --md {md_name} --patch <输出.md> --auto-mark -o <_work/>")
        lines.append("```")
        lines.append("`--patch` 统一 `<sup>n</sup>` → `[^n]`、把缺失的 `[^n]: ...` 写回文末；")
        lines.append("`--auto-mark` 只动句末裸数字（`. 5`），**不动行内公式**，避免改坏公式。")
        lines.append("第二步，按上表「可疑标记」的行号对照 PDF，把塞进 `^ { n }`、")
        lines.append("`\\mathrm{...}` 或行末裸数字的标记手工补成 `[^n]`。")
        lines.append("第三步，对补回稿重跑本脚本，确认 PASS 后再进入翻译。")
    lines.append("")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return ok, missing_defs, missing_marks


def patch_markdown(md: str, items, defs, wanted, auto_mark: bool, out_path: str):
    text = SUP.sub(lambda m: f"[^{int(m.group(1))}]", md)
    for ch, n in UNICODE_SUP.items():
        text = text.replace(ch, f"[^{n}]")
    fixed = 0
    if auto_mark and wanted:
        # 只动形态最明确的"行末孤立数字"（`.$ 5`、`power. 15`）；行内公式
        # 里的 `^ { n }` 一律不动，改错一个字符整条公式就坏了，交给人对照 PDF。
        pat = re.compile(r"(\s)(\d{1,2})(\s*)$", re.M)

        def repl(m):
            nonlocal fixed
            n = int(m.group(2))
            if n in wanted:
                fixed += 1
                return f"{m.group(1)}[^{n}]{m.group(3)}"
            return m.group(0)

        text = pat.sub(repl, text)
    missing = [x for x in items if x["num"] not in defs]
    if missing:
        add = "\n\n" + RECOVERED_MARK + "\n\n"
        for x in missing:
            add += f"[^{x['num']}]: {x['text']}\n\n"
        if RECOVERED_MARK not in text:
            text = text.rstrip() + add
        else:
            # 幂等：已有补回块时，只把新编号插在补回块末尾
            text = text.rstrip() + "\n\n" + "".join(
                f"[^{x['num']}]: {x['text']}\n\n" for x in missing)
    open(out_path, "w", encoding="utf-8", newline="\n").write(text)
    return len(missing), fixed


def main(argv=None):
    ap = argparse.ArgumentParser(description="MinerU 脚注体检与补回")
    ap.add_argument("pdf", nargs="?", help="源 PDF（有 --text 时可省）")
    ap.add_argument("--md", required=True, help="MinerU 输出的 full.md")
    ap.add_argument("--text", help="已有的 pdftotext -layout 文字层文件")
    ap.add_argument("-o", "--outdir", default="_work", help="报告与 CSV 输出目录")
    ap.add_argument("--patch", metavar="OUT.md", help="写出补回脚注后的 Markdown")
    ap.add_argument("--strict", action="store_true", help="体检不通过时返回非零退出码")
    ap.add_argument("--drop", default="", help="排除的编号，逗号分隔（如作者单位角标 1）")
    ap.add_argument("--max-num", type=int, default=60, help="脚注编号上限，默认 60")
    ap.add_argument("--auto-mark", action="store_true",
                    help="--patch 时把句末裸数字（. 5）补成 [^5]；公式内的上标不动")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.md):
        raise SystemExit(f"找不到 MinerU 稿：{args.md}")
    md = open(args.md, encoding="utf-8-sig").read()
    marks, defs, suspects = scan_markdown(md)

    raw, backend = load_text(args.pdf, args.text)
    if raw is None:
        print("未提供 PDF 或文字层，只做 Markdown 侧检查：")
        print(f"  标记 {sorted(marks)}｜定义 {sorted(defs)}")
        print("  要核 PDF 里究竟有几条脚注，请传 PDF 或 --text。")
        return 0

    drop = {int(x) for x in re.findall(r"\d+", args.drop)}
    items, gaps, pages = extract_from_pdf(raw, drop, args.max_num)
    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.md))[0]
    csv_path = os.path.join(args.outdir, f"{stem}_脚注.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["num", "page", "continued_on", "text"])
        w.writeheader()
        for x in items:
            w.writerow({k: x.get(k) or "" for k in ["num", "page", "continued_on", "text"]})
    # 只报「PDF 里有脚注、Markdown 里却没标记」的编号，挡掉 ^ {2}、年份、
    # 小数、图号这些满屏皆是却与脚注无关的数字。
    wanted = {x["num"] for x in items} - marks
    seen, kept = set(), []
    for ln, kind, n, ctx in suspects:
        if int(n) not in wanted:
            continue
        key = (ln, n)
        if key in seen:
            continue
        seen.add(key)
        kept.append((ln, kind, n, ctx))
    suspects = kept

    report_path = os.path.join(args.outdir, f"{stem}_脚注体检.md")
    ok, missing_defs, missing_marks = write_report(
        report_path, os.path.basename(args.pdf or args.text or "—"),
        args.md, backend, pages, items, gaps, marks, defs, suspects, drop, wanted)

    print(f"PDF 检出脚注 {len(items)} 条；MinerU 标记 {len(marks)} 个、定义 {len(defs)} 条")
    print(f"  缺失定义 {len(missing_defs)} 条，正文缺标记 {len(missing_marks)} 处，可疑位置 {len(suspects)} 处")
    print(f"  报告 {report_path}")
    print(f"  CSV   {csv_path}")
    if args.patch:
        n, fixed = patch_markdown(md, items, defs, wanted, args.auto_mark, args.patch)
        print(f"  已写出补回稿 {args.patch}（新增 {n} 条定义，自动补 {fixed} 个标记）")
    print("结论：" + ("PASS" if ok else "FAIL"))
    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
