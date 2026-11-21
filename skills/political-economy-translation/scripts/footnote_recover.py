#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""统一脚注恢复 / 就地锚定 / 核验（两个翻译 skill 共用同一实现）。

主检出源是 MinerU 的 ``content_list.json``（``type=page_footnote``）：版面识别
认得出页底脚注，只是服务端生成 ``full.md`` 时按类型白名单把它们整类过滤了。
PDF 文字层只作**交叉验证**——双栏期刊的脚注排在栏底而非页底，缩进特征会失效，
不能当主源；这一步用来发现「提取包本身被污染」或跨页续文被截断。

交付形态（唯一）
----------------
脚注**不是**文末一节编号列表，而是 Markdown 标准脚注：

* 正文：``[^n]`` 紧跟被注内容、位于句末标点之后；
* 文末：``[^n]: 脚注正文``，**没有** ``## 脚注`` 标题，也**不带**
  「第 N 页脚注 n：」这类页面前缀（页码只留在 ``_work/脚注.csv`` 里）。

这样 ``md2tex.py`` 才能把每个 ``[^n]`` 排成 LaTeX 页底 ``\footnote{}``；
带图文排版分支的 skill 也靠它把脚注挂到所注段落之后（没有该分支就只作 PDF）。
历史稿里那种「文末补一节」的写法会被本脚本迁移掉：``## 脚注`` 标题删除、
页面前缀剥离、「对应「…」处」提示语用来把标记自动插回正文。

典型用法
--------
第 1 步，提取后立刻恢复并锚定原文 / 译文两侧::

    python scripts/footnote_recover.py _work/extract -o _work \
        --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

填好 ``_work/脚注_待译.csv`` 的 ``zh`` 列后回填（也可直接在 md 里写中文）::

    python scripts/footnote_recover.py _work/extract -o _work \
        --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check

脚本判不出位置的脚注会列进 ``_work/脚注_待锚.csv``：把正文里紧邻标记前的
一句原话填进 ``anchor`` 列，再回灌::

    python scripts/footnote_recover.py _work/extract -o _work \
        --target <stem>_zh.md --apply --place _work/脚注_待锚.csv --check

交付前连 PDF 文本层一起验::

    python scripts/footnote_recover.py _work/extract -o _work \
        --source <stem>_原文.md --target <stem>_zh.md --check --pdf-out <stem>_zh.pdf

只用 Python 标准库；``pdftotext``（poppler / TeX Live）可选，用于交叉验证与 PDF
验收。``--apply`` 会写回 Markdown，写回前自动生成 ``*.bak_footnotes`` 备份。
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys

AFFIL_KEYS = ("University", "Institute", "Department", "Correspondence",
              "Correspondance", "Copyright", "Proceedings", "PMLR", "@")

# 只剥真正的排版标签；`<t.nagler@lmu.de>` 这类邮箱必须保留，否则补回去会丢信息。
TAG_RE = re.compile(r"</?(?:sup|sub|i|b|em|strong|br|span|p|div|u|small)\b[^>]*>", re.I)

# 旧稿的「## 脚注」节：只为迁移而识别，交付稿里不许再有。
# 只认脚注／尾注这两个明确的标题——`## 注释`、`## Notes` 在别的稿子里可能是
# 正经的正文注，自动摘走等于删内容。
SECTION_RE = re.compile(r"(?m)^#{2,6}[ \t]*(?:页底)?(?:脚注|尾注|Footnotes?|Endnotes?)[ \t]*$",
                        re.I)
ANY_HEAD_RE = re.compile(r"(?m)^#{1,6}\s")
DEF_RE = re.compile(r"(?m)^\[\^(\w+)\]:[ \t]*(.*)$")
SUP_NUM_RE = re.compile(r"<sup>\s*(\d{1,3})\s*</sup>")
# MinerU 会把正文里的脚注号塞进行内公式：`^ { 7 }`。只在显式要求时才动它——
# `$x ^ { 2 }$` 和「脚注 2」长得一模一样，自动改会把平方改成脚注。
MATH_SUP_RE = re.compile(r"(\$[^$\n]*?)\s*\^\s*\{\s*(\d{1,3})\s*\}\s*\$")
URL_RE = re.compile(r"https?://[^\s<>\"')，。；]+")
REF_HEAD_RE = re.compile(r"(?m)^##\s*(?:参考文献|REFERENCES|References)\s*$")
PENDING = "<!-- 待译：请填入中文脚注译文 -->"
DEF_NOTE = ("<!-- 脚注定义：Markdown 标准脚注语法，正文中的引用标记渲染为页底脚注；"
            "页码与分类见 _work/脚注.csv -->")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
CSV_FIELDS = ["page", "marker", "category", "text", "plain", "bbox",
              "in_full_md", "in_target", "zh", "in_pdf"]
ANCHOR_FIELDS = ["page", "marker", "en", "zh", "anchor", "range_hint"]

# 旧稿定义行里的「（对应「与 Thickstun (2021) 类似」处）」——这句话就是锚点。
LEGACY_HINT_RE = re.compile(r"[（(]\s*(?:对应|相对应|参见|见)?\s*[「『\"](.+?)[」』\"]\s*处?\s*[)）]")
LEGACY_HINT_RE2 = re.compile(r"(?:对应|参见|见)\s*[「『\"](.+?)[」』\"]")


# ------------------------------------------------------------------ 工具

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def plain(s):
    return norm(TAG_RE.sub(" ", s or ""))


def page_of(x):
    """page_idx 在不同 MinerU 版本里可能是 int、字符串或缺失。"""
    try:
        return int(x.get("page_idx", 0) or 0) + 1
    except (TypeError, ValueError):
        return 1


def find_content_list(src):
    p = pathlib.Path(src)
    if p.is_file():
        return p
    fs = sorted(f for f in p.rglob("*content_list*.json")
                if "v2" not in f.name.lower())
    if not fs:
        fs = sorted(f for f in p.rglob("*content_list*.json"))
    if not fs:
        raise SystemExit("找不到 content_list.json：%s" % src)
    return fs[0]


def read_content_list(cl):
    data = json.loads(cl.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("content_list", "pages", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
        raise SystemExit("content_list.json 结构不认识：%s" % cl.name)
    return data


def parse_footnotes(data):
    rows = []
    for x in data:
        if not isinstance(x, dict) or x.get("type") != "page_footnote":
            continue
        text = str(x.get("text", "") or "")
        m = re.match(r"\s*<sup>\s*(\w{1,4})\s*</sup>\s*", text)
        if m:
            marker = m.group(1).strip()
            body = text[m.end():].strip()
        else:
            # 有的期刊（Sage 的 RRPE 等）页底脚注不带 <sup>，编号是裸数字：'1 In section 5.6…'。
            # 只认 1–2 位数字紧跟空格或点，避免把 '2020 was…' 这类年份当成编号。
            m = re.match(r"\s*(\d{1,2})[\.\s]\s*", text)
            marker = m.group(1) if m else ""
            body = text[m.end():].strip() if m else text.strip()
        # 机构注里常有多个 <sup>2</sup>；转成纯文本，别把 HTML 字面带进 Markdown/TeX。
        body = norm(TAG_RE.sub(" ", re.sub(r"<sup>\s*(\w{1,4})\s*</sup>", r" \1 ", body)))
        p = plain(body)
        if any(k in p for k in AFFIL_KEYS) and len(p) >= 40:
            category = "affiliation"
        elif marker.isdigit() and len(p) >= 30:
            category = "footnote"
        elif len(p) < 30:
            category = "noise"
        else:
            category = "other"
        rows.append({
            "page": page_of(x),
            "marker": marker,
            "category": category,
            "text": body,
            "plain": p,
            "bbox": json.dumps(x.get("bbox", []), ensure_ascii=False),
            "in_full_md": "no",
            "in_target": "no",
            "zh": "",
            "in_pdf": "",
        })
    rows.sort(key=lambda r: (r["page"], int(r["marker"]) if r["marker"].isdigit() else 999))
    return rows


def load_zh(csv_path, translations):
    """保留已经人工填过的中文译文，重复运行不丢。"""
    out = {}
    for f in (csv_path, translations):
        if not f or not pathlib.Path(f).is_file():
            continue
        with open(f, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                zh = (r.get("zh") or "").strip()
                if zh and zh not in ("TODO", "待译"):
                    out[(str(r.get("page", "")), str(r.get("marker", "")))] = zh
    return out


def write_outputs(rows, outdir, cl):
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "脚注.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})

    lines = ["# MinerU 页底脚注（content_list.json / page_footnote）", "",
             "来源：`%s`" % cl.name,
             "主源为提取包；`--pdf` 的 PDF 文字层仅作交叉验证。", ""]
    for r in rows:
        lines += ["## 第 %s 页 · 脚注 %s · %s" %
                  (r["page"], r["marker"] or "—", r["category"]), "",
                  r["text"], ""]
    (outdir / "脚注_原文.md").write_text("\n".join(lines), encoding="utf-8")

    # 机构／版权注不占 [^n] 编号、也不进正文（交付稿里只留真脚注），单列一份备查。
    affil = [r for r in rows if r["category"] == "affiliation"]
    if affil:
        a = ["# 原刊机构／版权信息（不占脚注编号，未写入译稿）", ""]
        for r in affil:
            a += ["## 第 %s 页 · 脚注 %s" % (r["page"], r["marker"] or "—"), "",
                  r["text"], ""]
        (outdir / "脚注_原刊信息.md").write_text("\n".join(a), encoding="utf-8")

    todo = outdir / "脚注_待译.csv"
    with open(todo, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["page", "marker", "category", "en", "zh"])
        w.writeheader()
        for r in rows:
            # 机构/版权注按原刊信息保留英文，不占 [^n] 编号，也无需中文译文。
            if r["category"] == "footnote":
                w.writerow({"page": r["page"], "marker": r["marker"],
                            "category": r["category"], "en": r["text"],
                            "zh": r["zh"]})
    return csv_path, todo


# ------------------------------------------------------- PDF 文字层交叉验证

def pdf_text(pdf, text_file):
    if text_file:
        return pathlib.Path(text_file).read_text(encoding="utf-8-sig", errors="replace")
    if not pdf:
        return None
    exe = shutil.which("pdftotext")
    if not exe:
        print("  （没有 pdftotext，跳过 PDF 文字层交叉验证）")
        return None
    try:
        r = subprocess.run([exe, "-layout", "-enc", "UTF-8", str(pdf), "-"],
                           capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        print("  （pdftotext 调用失败，跳过交叉验证：%s）" % e)
        return None
    if r.returncode:
        print("  （pdftotext 退出码 %d，跳过交叉验证）" % r.returncode)
        return None
    return r.stdout.decode("utf-8", errors="replace")


def cross_check(rows, raw, outdir):
    if raw is None:
        return
    pages = [norm(p) for p in raw.split("\f")]
    found, missing = [], []
    for r in rows:
        if r["category"] not in ("footnote", "affiliation") or not r["plain"]:
            continue
        key = norm(r["plain"])[:25]
        idx = max(0, r["page"] - 1)
        nearby = " ".join(pages[max(0, idx - 1):idx + 2])
        if key and key in nearby:
            found.append(r)
        else:
            missing.append(r)
    lines = ["# 脚注交叉验证（PDF 文字层）", "",
             "主源 `content_list.json` 共 %d 条内容脚注；PDF 文字层在对应页±1 页内"
             "确认 %d 条。" % (len(found) + len(missing), len(found)), "",
             "> 双栏期刊的脚注排在栏底，`pdftotext -layout` 的缩进特征会变，"
             "未确认**不等于**提取包有错；这一层只用来发现文字层污染、跨页续文截断。", ""]
    if missing:
        lines += ["## 文字层未确认（逐条对照 PDF 目视）", ""]
        for r in missing:
            lines.append("- 第 %s 页脚注 %s：%s" % (r["page"], r["marker"], r["plain"][:90]))
        lines.append("")
    (outdir / "脚注_交叉验证.md").write_text("\n".join(lines), encoding="utf-8")
    print("交叉验证：%d/%d 条在 PDF 文字层确认；未确认 %d 条（见 脚注_交叉验证.md）"
          % (len(found), len(found) + len(missing), len(missing)))


# ------------------------------------------------------------ Markdown 结构

def split_defs(text):
    """摘出全文的 ``[^n]: ...`` 定义（含续行），返回 (正文, [(n, 内容), ...])。"""
    body, defs, cur = [], [], None
    last = None
    for ln in (text or "").split("\n"):
        m = DEF_RE.match(ln)
        if m:
            defs.append([m.group(1), m.group(2).strip()])
            cur = defs[-1]
            last = len(body)
            continue
        if cur is not None:
            if ln.strip() and re.match(r"^(?:[ \t]{2,}|\t)", ln):
                cur[1] = (cur[1] + " " + ln.strip()).strip()
                continue
            cur = None
        body.append(ln)
    # 定义行摘走后可能留下连续空行，压回单个空行
    out, blank = [], 0
    for ln in body:
        if not ln.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(ln)
    return "\n".join(out), [(n, c) for n, c in defs]


def pop_section(text):
    """摘掉旧稿的 ``## 脚注`` 节，返回 (剩余正文, 该节内容)。"""
    m = SECTION_RE.search(text)
    if not m:
        return text, ""
    nxt = ANY_HEAD_RE.search(text[m.end():])
    stop = m.end() + (nxt.start() if nxt else len(text) - m.end())
    return text[:m.start()] + text[stop:], text[m.end():stop]


def strip_legacy_label(s):
    """剥掉历史稿塞进定义里的「**第 6 页脚注 1**（对应「…」处）：」标签。

    返回 (干净的脚注正文, 旧稿给的定位提示语)。提示语是脚注标记该插在
    正文哪句之后——迁移旧稿时用它把标记自动插回去。
    """
    s = (s or "").strip()
    hint = ""
    m = LEGACY_HINT_RE.search(s) or LEGACY_HINT_RE2.search(s)
    if m:
        hint = m.group(1).strip()
        s = (s[:m.start()] + s[m.end():]).strip()
    if re.match(r"^\**\s*第\s*\d+\s*页", s):
        cut = [i for i in (s.find("："), s.find(":")) if i >= 0]
        if cut:
            s = s[min(cut) + 1:].strip()
    else:
        s = re.sub(r"^\**\s*(?:页底)?(?:脚注|注释|尾注|注)\s*\w{0,4}\s*\**\s*[：:]\s*", "", s)
    return s.strip(), hint


META_LINE_RE = re.compile(r"^\*\*?第\s*\d+\s*页"
                          r"(?:作者|机构|单位|会议|版权|通讯|通信|原刊|基金|致谢)")


def legacy_leftovers(block):
    """旧节里认不出来的行。有剩行就说明这一节不全是脚注条目，不能整节摘走。"""
    out = []
    for raw in (block or "").split("\n"):
        ln = raw.strip()
        if not ln or ln.startswith(">") or ln.startswith("<!--"):
            continue
        if DEF_RE.match(ln) or re.match(r"^\[\^(\w+)\][ \t]*[：:]", ln):
            continue
        if re.match(r"^(?:\*\*)?第\s*\d+\s*页\s*脚注\s*\d{1,3}(?:\*\*)?", ln):
            continue
        if META_LINE_RE.match(ln):
            # 旧版把作者机构／版权注一并写在这一节里，现在它们单列到
            # `脚注_原刊信息.md`，可以安全丢弃（提取包里有原文，会重新生成）。
            continue
        if re.match(r"^(?:\d{1,3}[.、)]|[-*]\s*注\s*\d{1,3}|注\s*\d{1,3})[\s、.）]*", ln):
            continue
        out.append(ln)
    return out


def parse_legacy_block(block):
    """把旧 ``## 脚注`` 节拆成 [(n, 内容, 提示语)]；认 [^n]:、**第 p 页…**：、N.、- 注 n。"""
    out = []
    for raw in (block or "").split("\n"):
        ln = raw.strip()
        if not ln or ln.startswith(">"):
            continue          # 引用块是旧稿里的机构／版权说明，不占编号
        m = DEF_RE.match(ln) or re.match(r"^\[\^(\w+)\][ \t]*[：:][ \t]*(.*)$", ln)
        if m:
            content, hint = strip_legacy_label(m.group(2))
            out.append((m.group(1), content, hint))
            continue
        m = re.match(r"^(?:\*\*)?第\s*\d+\s*页\s*脚注\s*(\d{1,3})(?:\*\*)?", ln)
        if m:
            content, hint = strip_legacy_label(ln)
            out.append((m.group(1), content, hint))
            continue
        m = re.match(r"^(?:\d{1,3}[.、)]|[-*]\s*注\s*\d{1,3}|注\s*\d{1,3})[\s、.）]*", ln)
        if m and m.group(0).strip():
            content, hint = strip_legacy_label(ln[m.end():])
            n = re.search(r"\d{1,3}", m.group(0))
            out.append((n.group(0) if n else "", content, hint))
    return out


# ------------------------------------------------------------------ 锚定

# 标记只跳过引号／括号这类「属于被注词句」的收尾符号，不跳过句读——
# 原刊的脚注号就落在被注词句之后、逗号句号之前。
CLOSERS = "」』”’\"'）)]】"


def anchor_after_quote(body, n, quote):
    """在正文里找到 quote，把 ``[^n]`` 插在它后面（跳过紧随的句末标点）。

    返回 (新正文, 是否成功)。找不到原话就原样返回，绝不硬塞到别处——
    脚注落错位置比缺一条更坏。
    """
    q = (quote or "").strip().strip("「」『』\"' ")
    if not q or len(q) < 4:
        return body, False
    idx = body.find(q)
    if idx < 0:
        # 原文里常有空格抖动（英文抽取尤甚），退一步按空白折叠后的正文再找一次
        flat = re.sub(r"[ \t]+", "", body)
        qf = re.sub(r"\s+", "", q)
        j = flat.find(qf)
        if j < 0:
            return body, False
        # 把 flat 的下标映射回原文
        pos, count = 0, 0
        while pos < len(body) and count < j:
            if body[pos] in " \t":
                pos += 1
                continue
            pos += 1
            count += 1
        end = pos
        need = len(qf)
        got = 0
        while end < len(body) and got < need:
            if body[end] not in " \t":
                got += 1
            end += 1
    else:
        end = idx + len(q)
    m = re.match(r"[%s]*" % re.escape(CLOSERS), body[end:])
    end += m.end()
    if f"[^{n}]" in body[max(0, end - 12):end + 6]:
        return body, True
    return body[:end] + "[^%s]" % n + body[end:], True


def used_markers(body):
    """正文里真正出现的引用标记；HTML 注释里的示例文字不算。"""
    return {m.group(1) for m in re.finditer(r"\[\^(\w+)\](?!:)",
                                            COMMENT_RE.sub(" ", body or ""))}


def bare_candidates(body, rows):
    """句末标点后的裸编号：MinerU 把上标降级成普通数字时的候选。"""
    out = []
    want = [r["marker"] for r in rows
            if r["category"] == "footnote" and r["marker"].isdigit()]
    for n in want:
        for m in re.finditer(r"[。！？；.!?;][ \t]*%s(?![0-9])" % re.escape(n), body):
            out.append((n, body[max(0, m.start() - 30):m.start() + 1]))
            break
    return out


def math_candidates(body, rows):
    out = []
    want = {r["marker"] for r in rows
            if r["category"] == "footnote" and r["marker"].isdigit()}
    for m in MATH_SUP_RE.finditer(body):
        if m.group(2) in want:
            out.append((m.group(2), m.group(0)[-40:]))
    return out


def range_hint(body, n, used):
    """给未锚定的脚注一条区间提示：应落在哪两个已知标记之间。"""
    nums = sorted(int(x) for x in used if x.isdigit())
    prev = max([x for x in nums if x < int(n)], default=None)
    nxt = min([x for x in nums if x > int(n)], default=None)
    left = right = ""
    if prev is not None:
        m = re.search(r"\[\^%d\]" % prev, body)
        if m:
            left = norm(body[max(0, m.start() - 40):m.start()])
    if nxt is not None:
        m = re.search(r"\[\^%d\]" % nxt, body)
        if m:
            right = norm(body[m.end():m.end() + 40])
    if prev is None and nxt is None:
        return "正文里还没有任何引用标记，请按原刊位置自行插入"
    lo = "[^%s]" % prev if prev is not None else "文首"
    hi = "[^%s]" % nxt if nxt is not None else "文末"
    return "应位于 %s 之后、%s 之前：…%s ↔ %s…" % (lo, hi, left, right)


# ------------------------------------------------------------ 原文 / 译文补全

def build_defs(rows, side, old, want_zh):
    """生成 ``[^n]: 内容`` 行。页码、分类只进 CSV，不写进脚注正文。"""
    out, order = {}, []
    for r in rows:
        n = r["marker"]
        if r["category"] != "footnote" or not n.isdigit():
            continue
        content = ""
        if side == "target":
            content = (want_zh.get((str(r["page"]), n)) or "").strip()
            if not content:
                prev = strip_legacy_label(old.get(n, ""))[0] if old.get(n) else ""
                if prev and PENDING not in prev and re.search(r"[\u4e00-\u9fff]", prev):
                    content = prev          # 人已经在 md 里写好中文，别覆盖
        if not content:
            content = r["text"]
        if side == "target" and not want_zh.get((str(r["page"]), n)) \
                and not re.search(r"[\u4e00-\u9fff]", content):
            content = content + " " + PENDING
        out[n] = "[^%s]: %s" % (n, norm(content))
        order.append(n)
    return out, order


def apply_md(path, rows, side, place_rows=None, anchor_bare=False,
             anchor_math=False, want_zh=None):
    """把脚注落成正文内联 ``[^n]`` + 文末定义；返回 (错误, 统计)。"""
    p = pathlib.Path(path)
    want_zh = want_zh or {}
    stat = {"defs": 0, "anchored": 0, "pending_anchor": [], "migrated": 0}
    if not p.is_file():
        return "找不到 %s（%s）" % (p, side), stat
    text = p.read_text(encoding="utf-8")
    # 先摘旧节再拆定义：旧节的 `[^n]:` 行要先被 parse_legacy_block 读到，
    # 才能拿到「对应「…」处」这条定位提示。
    body0, legacy_block = pop_section(text)
    left = legacy_leftovers(legacy_block)
    if left:
        return ("`## 脚注` 节里有 %d 行不是脚注条目（如「%s」），未自动迁移——"
                "整节摘走会连正文一起删掉；请人工把该节拆成正文 `[^n]` + 文末定义"
                % (len(left), left[0][:40])), stat
    body, defs = split_defs(body0)
    legacy = parse_legacy_block(legacy_block)

    old = {}
    for n, c, _h in legacy:
        if n:
            old[n] = c
    for n, c in defs:
        old.setdefault(n, c)          # 现存定义优先于旧节（更可能是人工改过的）

    # 1) 确定性的形态归一
    body = SUP_NUM_RE.sub(lambda m: "[^%s]" % m.group(1), body)
    if anchor_math:
        body = MATH_SUP_RE.sub(lambda m: "%s$[^%s]" % (m.group(1), m.group(2)), body)
    if anchor_bare:
        used = used_markers(body)
        for r in rows:
            n = r["marker"]
            if r["category"] != "footnote" or not n.isdigit() or n in used:
                continue
            mm = re.search(r"([。！？；.!?;])[ \t]*%s(?![0-9])" % re.escape(n), body)
            if mm:
                body = body[:mm.start(1) + 1] + "[^%s]" % n + body[mm.end(1) + 1:]
                used.add(n)

    # 2) 旧稿「对应「…」处」提示语 → 自动锚定
    for n, _c, hint in legacy:
        if not n or not hint:
            continue
        if n in used_markers(body):
            continue
        body, ok = anchor_after_quote(body, n, hint)
        stat["anchored"] += 1 if ok else 0
        stat["migrated"] += 1

    # 3) --place 指定的手工锚点
    for row in (place_rows or []):
        n = (row.get("marker") or "").strip()
        a = (row.get("anchor") or "").strip()
        if not n or not a or n in used_markers(body):
            continue
        body, ok = anchor_after_quote(body, n, a)
        stat["anchored"] += 1 if ok else 0
        if not ok:
            print("  [!] `--place` 里脚注 %s 的 anchor 在正文中找不到：%s" % (n, a[:40]))

    # 4) 定义
    desired, order = build_defs(rows, side, old, want_zh)
    stat["defs"] = len(desired)
    used = used_markers(body)
    stat["pending_anchor"] = [(r["marker"], r["page"]) for r in rows
                              if r["category"] == "footnote" and r["marker"].isdigit()
                              and r["marker"] not in used]
    stat["_body"] = body

    clean = "\n".join(ln for ln in body.split("\n")
                      if not ln.strip().startswith("<!-- 脚注定义")).rstrip()
    if order:
        block = "\n\n".join([DEF_NOTE] + [desired[n] for n in order])
        new_text = clean + "\n\n" + block + "\n"
    else:
        # 清单里没有内容脚注：只把旧节/旧定义清干净，不要凭空塞一行说明注释。
        new_text = clean + "\n"

    if new_text != text:
        bak = p.with_name(p.name + ".bak_footnotes")
        if not bak.exists():
            bak.write_text(text, encoding="utf-8")
        p.write_text(new_text, encoding="utf-8")
        moved = "（旧稿 `## 脚注` 节已迁为正文内联标记）" if legacy_block else ""
        print("  已写回 %s（备份 %s）；%d 条定义、本次新锚定 %d 条%s"
              % (p.name, bak.name, len(desired), stat["anchored"], moved))
    else:
        print("  %s 无需改动（%d 条定义）" % (p.name, len(desired)))
    return None, stat


def write_anchor_report(rows, body, outdir):
    """把没锚定的脚注写成人可填的清单：anchor 列填正文里紧邻标记前的一句原话。

    已经填过的 anchor 会原样保留——`--apply` 和 `--check` 都调这个函数，
    随手跑一次核对就把人填好的定位原话冲掉，等于白填。
    """
    path = pathlib.Path(outdir) / "脚注_待锚.csv"
    kept = {}
    if path.is_file():
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                a = (row.get("anchor") or "").strip()
                if a:
                    kept[str(row.get("marker", ""))] = a
    todo = [r for r in rows if r["category"] == "footnote" and r["marker"].isdigit()
            and r["marker"] not in used_markers(body)]
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ANCHOR_FIELDS)
        w.writeheader()
        for r in todo:
            w.writerow({"page": r["page"], "marker": r["marker"],
                        "en": r["text"], "zh": r.get("zh", ""),
                        "anchor": kept.get(r["marker"], ""),
                        "range_hint": range_hint(body, r["marker"], used_markers(body))})
    return todo


def scaffold(rows, path):
    out = ["# 待补脚注（按原刊位置插到正文相应句末之后）", "",
           "每条脚注的标记要写成正文里的 `[^n]`，定义写在文末，"
           "**不要**再另起 `## 脚注` 节。", ""]
    for r in rows:
        if r["category"] != "footnote" or not r["marker"].isdigit():
            continue
        out += ["## 第 %s 页脚注 %s" % (r["page"], r["marker"]), "",
                "原文：" + r["text"], "", "正文位置：" + (r["zh"] or "TODO"), ""]
    pathlib.Path(path).write_text("\n".join(out), encoding="utf-8")
    print("待补骨架：%s" % path)


# ------------------------------------------------------------------ 内容级验收

def check_all(rows, source, target, pdf_out, allow_pending, skip, anchor_report_dir=None):
    problems, warns = [], []
    if skip:
        print("  （已显式跳过脚注核对）")
        return [], []
    if not rows:
        print("✓ 脚注核对：清单 0 条")
        return [], []
    needed = [r for r in rows if r["category"] == "footnote"
              and r["marker"].isdigit()]
    print("清单：%d 条内容脚注需补（另有 %d 条机构／版权注不入稿）"
          % (len(needed), len(rows) - len(needed)))
    if not source and not target:
        warns.append("未指定 --source / --target：只核了清单，没核 Markdown 的落位结果；"
                     "交付前务必补上这两个参数")

    for side, path in (("原文", source), ("译文", target)):
        if not path:
            continue
        p = pathlib.Path(path)
        if not p.is_file():
            problems.append("%s侧文件不存在：%s" % (side, path))
            continue
        text = p.read_text(encoding="utf-8")
        body0, legacy_block = pop_section(text)
        body, defs = split_defs(body0)
        if legacy_block.strip():
            problems.append("%s仍有 `## 脚注` 节：脚注必须是正文内联 `[^n]` + 文末定义，"
                            "不能是单独一节（跑 --apply 会自动迁移）" % side)
        defmap = {}
        for n, c, _h in parse_legacy_block(legacy_block):
            if n:
                defmap.setdefault(n, c)
        for n, c in defs:
            defmap.setdefault(n, c)
        used = used_markers(body)
        for r in needed:
            n = r["marker"]
            line = defmap.get(n)
            if line is None:
                problems.append("%s缺 `[^%s]:` 定义（第 %s 页脚注 %s）"
                                % (side, n, r["page"], n))
            else:
                if re.match(r"^\**\s*第\s*\d+\s*页", strip_legacy_label(line)[0]) \
                        or re.search(r"第\s*\d+\s*页\s*脚注", line[:30]):
                    problems.append("%s `[^%s]` 定义里还留着「第 N 页脚注 n：」页面前缀，"
                                    "脚注正文只能是正文本身" % (side, n))
                for u in URL_RE.findall(r["plain"]):
                    if u not in line:
                        problems.append("%s `[^%s]` 丢了链接 %s" % (side, n, u[:60]))
                if side == "译文":
                    if PENDING in line or "TODO" in line:
                        if not allow_pending:
                            problems.append("译文 `[^%s]` 还是英文待译：填 _work/脚注_待译.csv "
                                            "的 zh 列（或直接在 md 里写中文）后重跑 --apply" % n)
                    elif not re.search(r"[\u4e00-\u9fff]", line):
                        warns.append("译文 `[^%s]` 没有汉字，确认是否为纯链接/代码" % n)
            if n not in used:
                # 交付物是译文；原文提取稿只是中间件，缺锚点提醒即可（两侧块级
                # 对账靠定义行，不靠正文标记）。译文缺锚点才是硬失败。
                if side == "译文":
                    problems.append("%s正文没有 `[^%s]` 引用：第 %s 页脚注 %s 尚未锚定，"
                                    "PDF 里会掉成文末列表" % (side, n, r["page"], n))
                else:
                    warns.append("%s正文没有 `[^%s]` 引用（第 %s 页脚注 %s）："
                                 "原文侧只要求定义齐全，但补上锚点便于逐句对照"
                                 % (side, n, r["page"], n))
        orphan = sorted(used - set(defmap), key=lambda x: (not x.isdigit(), x))
        if orphan:
            problems.append("%s正文有 `[^%s]` 却没有对应定义（孤儿标记）"
                            % (side, "、".join(orphan)))
        # 脚注编号在正文里必须按升序首次出现，否则说明锚点插错了句子
        seen = []
        for m in re.finditer(r"\[\^(\w+)\](?!:)", COMMENT_RE.sub(" ", body)):
            if m.group(1).isdigit() and int(m.group(1)) not in seen:
                seen.append(int(m.group(1)))
        order = seen
        if len(seen) > 1 and seen != sorted(seen):
            problems.append("%s正文 `[^n]` 首次出现顺序不是升序（实际 %s）：锚点插错了位置"
                            % (side, "→".join(str(x) for x in seen)))
        if re.search(r"<sup>\s*\d", text):
            problems.append("%s仍有字面 `<sup>n</sup>`：交付形态只能是 `[^n]`" % side)
        missing = [n for n in (r["marker"] for r in needed) if n not in used]
        if missing:
            cand_b = bare_candidates(body, rows)
            cand_m = math_candidates(body, rows)
            if cand_b:
                warns.append("%s有 %d 条句末裸编号疑似丢标的脚注（如脚注 %s）："
                             "确认后可加 --anchor-bare 自动锚定"
                             % (side, len(cand_b), "、".join(n for n, _ in cand_b)))
            if cand_m:
                warns.append("%s有 %d 个行内公式末尾的 `^{n}` 疑似脚注号（脚注 %s）："
                             "确认后可加 --anchor-math" % (side, len(cand_m),
                                                          "、".join(n for n, _ in cand_m)))
            if anchor_report_dir and (side == "译文" or not target):
                todo = write_anchor_report(rows, body, anchor_report_dir)
                if todo:
                    warns.append("未锚定脚注已写入 %s/脚注_待锚.csv：把正文里紧邻标记前的"
                                 "一句原话填进 anchor 列，再 --apply --place 回灌"
                                 % pathlib.Path(anchor_report_dir).as_posix())
        print("  %s：%d 条定义、%d 条正文引用，未锚定 %d 条"
              % (side, len(defmap), len(used & {r["marker"] for r in needed}), len(missing)))

    if pdf_out:
        raw = pdf_out_text(pdf_out)
        if raw is None:
            problems.append("拿不到译文 PDF 文本层：%s" % pdf_out)
        else:
            # 中文长句在 PDF 文本层里常跨行断开（甚至断在词中间），
            # 两边都去掉所有空白再比对，避免「内容明明在却报丢失」。
            big = re.sub(r"\s+", "", raw)
            for tag in ("[^1]", "[^n]", "<sup>"):
                if tag in raw:
                    problems.append("PDF 文本层残留字面 %s：脚注没被正确渲染" % tag)
            for r in needed:
                key = re.sub(r"\s+", "",
                             re.sub(r"<[^>]+>", "", (r["zh"] or r["plain"])[:14]))
                if key and key not in big:
                    problems.append("PDF 文本层找不到脚注 %s 的内容（%s…）"
                                    % (r["marker"], key))
            print("  PDF 文本层：%d 字符，逐条核 %d 条脚注" % (len(raw), len(needed)))
    return problems, warns


def pdf_out_text(pdf_out):
    exe = shutil.which("pdftotext")
    if not pdf_out or not pathlib.Path(pdf_out).is_file():
        return None
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-enc", "UTF-8", str(pdf_out), "-"],
                           capture_output=True, timeout=300)
        if r.returncode:
            return None
        return r.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None


# ----------------------------------------------------------------------- main

def read_place(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return []
    with open(p, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser(description="统一脚注恢复 / 就地锚定 / 核验（content_list.json）")
    ap.add_argument("src", help="MinerU 提取目录，或 *_content_list.json")
    ap.add_argument("-o", "--outdir", default=None, help="清单输出目录")
    ap.add_argument("--md", default=None, help="兼容旧用法：等同 --source")
    ap.add_argument("--source", default=None, help="原文提取稿 Markdown")
    ap.add_argument("--target", default=None, help="译文 Markdown")
    ap.add_argument("--pdf", default=None, help="原 PDF，仅作文字层交叉验证")
    ap.add_argument("--text", default=None, help="已导出的 PDF 文字层（代替 --pdf）")
    ap.add_argument("--pdf-out", default=None, help="编译后的译文 PDF，验收脚注是否进文本层")
    ap.add_argument("--apply", action="store_true",
                    help="把 `[^n]` 锚定进正文、定义写到文末（不再插 `## 脚注` 节）")
    ap.add_argument("--place", default=None,
                    help="待锚清单 CSV（脚注_待锚.csv），按 anchor 列把 [^n] 插回正文")
    ap.add_argument("--anchor-bare", action="store_true",
                    help="把句末标点后的裸编号当成丢失的上标自动锚定（有误判风险）")
    ap.add_argument("--anchor-math", action="store_true",
                    help="把行内公式末尾的 `^{n}` 当成脚注号自动锚定（有误判风险）")
    ap.add_argument("--translations", default=None, help="填好 zh 列的 CSV（默认读 _work/脚注_待译.csv）")
    ap.add_argument("--check", action="store_true", help="内容级硬门禁，有缺失返回 1")
    ap.add_argument("--scaffold", default=None, help="另写一份可粘贴的待补脚注清单")
    ap.add_argument("--allow-pending", action="store_true", help="允许译文侧留英文待译（不推荐）")
    ap.add_argument("--skip-footnote-check", action="store_true",
                    help="仅纯 Markdown 输入、没有 MinerU 结果包时显式跳过")
    args = ap.parse_args(argv)

    cl = find_content_list(args.src)
    rows = parse_footnotes(read_content_list(cl))
    outdir = pathlib.Path(args.outdir) if args.outdir else cl.parent
    outdir.mkdir(parents=True, exist_ok=True)
    # 必须先读回已填过的中文，再写清单；否则 write_outputs 会把待译 CSV 清空。
    zh_map = load_zh(outdir / "脚注.csv",
                     args.translations or (outdir / "脚注_待译.csv"))
    for r in rows:
        r["zh"] = zh_map.get((str(r["page"]), str(r["marker"])), "")
    csv_path, todo = write_outputs(rows, outdir, cl)

    full = cl.parent / "full.md"
    full_text = norm(full.read_text(encoding="utf-8")) if full.exists() else ""
    src_text = norm(pathlib.Path(args.source or args.md).read_text(encoding="utf-8")) \
        if (args.source or args.md) and pathlib.Path(args.source or args.md).is_file() else ""
    tgt_text = norm(pathlib.Path(args.target).read_text(encoding="utf-8")) \
        if args.target and pathlib.Path(args.target).is_file() else ""
    for r in rows:
        key = norm(r["plain"])[:30]
        r["in_full_md"] = "yes" if key and key in full_text else "no"
        r["in_target"] = "yes" if key and (key in src_text or key in tgt_text) else "no"
    print("提取包：%s" % cl.name)
    counts = {}
    for r in rows:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print("page_footnote 共 %d 条：%s" %
          (len(rows), "、".join("%s %d" % kv for kv in sorted(counts.items()))))
    print("清单：%s / %s" % (csv_path, todo))

    raw = pdf_text(args.pdf, args.text)
    cross_check(rows, raw, outdir)

    if args.scaffold:
        scaffold(rows, args.scaffold)

    place_rows = read_place(args.place) if args.place else []

    if args.apply:
        print("落地：正文内联 [^n] + 文末定义")
        for side, path in (("source", args.source or args.md), ("target", args.target)):
            if path:
                err, stat = apply_md(path, rows, side, place_rows,
                                     args.anchor_bare, args.anchor_math, zh_map)
                if err:
                    print("  [!] " + err)
                    continue
                if stat["pending_anchor"]:
                    print("  [!] %d 条脚注还没锚定：%s"
                          % (len(stat["pending_anchor"]),
                             "、".join("第%s页脚注%s" % (p, n)
                                      for n, p in stat["pending_anchor"][:12])))
                    write_anchor_report(rows, stat["_body"], outdir)
                    print("      已写 %s/脚注_待锚.csv——填 anchor 列后 "
                          "--apply --place 回灌" % outdir.as_posix())
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    elif not args.check:
        print("（只出了清单，没有改动 Markdown；落位加 --apply）")

    problems, warns = [], []
    if args.check:
        problems, warns = check_all(rows, args.source or args.md, args.target,
                                    args.pdf_out, args.allow_pending,
                                    args.skip_footnote_check, outdir)
        for w in warns:
            print("  [!] " + w)
        if problems:
            print("\n[FAIL] 脚注核对 %d 项不通过：" % len(problems))
            for p in problems[:20]:
                print("    - " + p)
            if len(problems) > 20:
                print("    ... 另有 %d 项" % (len(problems) - 20))
        else:
            print("\n[PASS] 脚注核对通过")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
