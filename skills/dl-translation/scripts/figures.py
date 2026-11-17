#!/usr/bin/env python3
"""Audit — and repair — the figures of a translated paper.

Why figures need their own script
---------------------------------
Markdown's image syntax is inline: `![]()` has no notion of width, of a
caption, or of a panel. A paper figure is a composite object — image, caption,
sub-captions, a number the text refers to — so a naive extraction produces the
three failure modes this script looks for:

* **拆散** a four-panel figure arrives as four separate images, one per line,
  rendered full width and stacked vertically. The panel order is guessable, the
  ratios are wrong, and the caption ends up somewhere in the middle.
* **游离** the caption paragraph lands above the image, or three paragraphs
  later, because the extractor emits text in reading order.
* **裸图** an image with no caption at all (the caption was absorbed into the
  image, or lost), so `图 3` in the running text points at nothing.

`audit` counts and reports those; `group` rewrites a run of consecutive bare
images into one side-by-side HTML figure block, which is the only way to place
panels next to each other in Markdown. The block is wrapped in
`<!-- figure:start -->` / `<!-- figure:end -->` so that `fidelity_check.py` can
collapse it back to a single logical figure and keep auditing structure.

A fourth failure mode is not structural: **a float parked far from the words
that cite it**. A two-column PDF pushes a figure to the top of the next page;
Markdown has no pages and no floats, so `relocate` moves each figure/table
(with its caption and table note) to just after the paragraph that first cites
it. Only the position changes. `fidelity_check.py --float-reflow` then compares
the body block sequence position-by-position while auditing floats as a
multiset (paths, caption numbers, table rows).

Usage
-----
    python figures.py audit 原文.md 译文_zh.md
    python figures.py audit 原文.md 译文_zh.md --csv _work/图目录.csv
    python figures.py group 译文_zh.md            # 只报告，不改文件
    python figures.py group 译文_zh.md --apply    # 真的合成为并排图块
    python figures.py relocate 译文_zh.md         # 就近重定位计划，不改文件
    python figures.py relocate 译文_zh.md --apply --csv _work/图表重定位.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathscan import FIGURE_END, FIGURE_START, strip_notation  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

IMG_MD = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)")
# The whole line must be the image, not text containing one.
LONE_MD = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
LONE_HTML = re.compile(r"<img[^>]*>", re.I)
IMG_HTML = re.compile(r"<img[^>]*\bsrc=[\"']([^\"']+)", re.I)
ALT_HTML = re.compile(r"<img[^>]*\balt=[\"']([^\"']*)", re.I)
# 图注必须满足「编号后跟标点／全角空格／行尾」。否则以「图 2 中的结果…」
# 开头的正文段落会被当成图注：既虚增图注数，又让 relocate 找不到引用锚点。
_CAP_TAIL = r"(?:\*\*)?(?:\s*[:：.．、]|\s*　|\s*$)"
CAP_ZH = re.compile(r"^\s*(?:\*\*)?图\s*(\d+)" + _CAP_TAIL)
CAP_EN = re.compile(r"^\s*(?:\*\*)?(?:Figure|Fig\.)\s*(\d+)" + _CAP_TAIL, re.I)
REF_ZH = re.compile(r"图\s*(\d+)")
REF_EN = re.compile(r"(?:Figure|Fig\.)\s*(\d+)")

# --- 浮动对象就近重定位 -------------------------------------------------
# PDF 把图/表浮到页顶页底，Markdown 里应移到正文首次引用它们的段落之后。
# 识别只认「图片/表格 + 紧跟的图注/表注」这样的完整块，绝不把正文段落
# 当浮动对象——搬错一段正文比不搬更糟。
FLOAT_MOVED = re.compile(r"<!--\s*float:moved\b[^>]*-->", re.I)
FLOAT_ENDTAG = re.compile(r"<!--\s*float:end\b[^>]*-->", re.I)
CAP_TAB_ZH = re.compile(r"^\s*(?:\*\*)?表\s*(\d+)" + _CAP_TAIL)
CAP_TAB_EN = re.compile(r"^\s*(?:\*\*)?Table\s*(\d+)" + _CAP_TAIL, re.I)
REF_TAB_ZH = re.compile(r"表\s*(\d+)")
REF_TAB_EN = re.compile(r"(?:Table|Tab\.)\s*(\d+)")
SUBCAP_LINE = re.compile(r"^\s*[-*+]\s*\([a-z]\)", re.I)
TABLE_LINE = re.compile(r"^\s*\|")
# Markdown 表格的分隔行；用来把「| a | ≤ | b |」这种被抽取成竖线开头的
# 数学公式排除在浮动表格之外。
TABLE_SEP = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|){1,}\s*$")
# 围栏代码块。代码里的 | 对齐行、字符串 "Table 2"、注释 "# 图 3" 都不是表格
# 或图注，识别浮动对象前先整块换成占位符（行数不变，下标仍对得上原文件）。
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
CODE_MASK = "\x00code"

# YAML front matter 里常写 title/keywords，可能含 "Figure 1" 之类的字样。
# 那不是正文引用；找锚点时要把这些行排除，否则 relocate 会把图搬到文件开头。
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)


def frontmatter_line_count(text):
    m = FRONT_MATTER.match(text)
    return len(m.group(0).splitlines()) if m else 0


def mask_code(lines):
    """Replace fenced code blocks (fences included) with a placeholder line.

    Length is preserved, so line indices still address the original file. The
    placeholder is non-blank on purpose: a blanked block would let a caption
    lookahead jump over the code and attach a caption from the far side.
    """
    out, in_fence = [], False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(CODE_MASK)
            continue
        out.append(CODE_MASK if in_fence else line)
    return out


def read(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def lone_image(line):
    """A line that holds one image and nothing else."""
    s = line.strip()
    if not s:
        return None
    m = LONE_MD.fullmatch(s)
    if m:
        return {"alt": m.group(1), "src": m.group(2), "syntax": "md"}
    m = LONE_HTML.fullmatch(s)
    if m:
        src = IMG_HTML.search(s)
        if src:
            alt = ALT_HTML.search(s)
            return {"alt": alt.group(1) if alt else "",
                    "src": src.group(1), "syntax": "html"}
    return None


def scan(text):
    """Walk the body and return figures, captions and their line numbers."""
    entries, in_block, block_start = [], False, 0
    for i, line in enumerate(mask_code(text.split("\n")), 1):
        if FIGURE_START.search(line):
            in_block, block_start = True, i
            continue
        if FIGURE_END.search(line):
            in_block = False
            continue
        if in_block:
            continue
        cap = CAP_ZH.match(line) or CAP_EN.match(line)
        if cap:
            entries.append({"kind": "caption", "line": i, "num": cap.group(1),
                            "text": line.strip()[:60]})
            continue
        img = lone_image(line)
        if img:
            entries.append({"kind": "image", "line": i, "num": None, **img})
    return entries


def _table_run(lines, i):
    j = i
    while j < len(lines) and TABLE_LINE.match(lines[j]):
        j += 1
    return j


def _looks_like_table(lines, i, j):
    """A real Markdown table, not a formula extraction that starts with |."""
    if j - i < 2:
        return False
    if any(TABLE_SEP.match(x) for x in lines[i:j]):
        return True
    k = j
    while k < len(lines) and not lines[k].strip():
        k += 1
    return bool(k < len(lines)
                and (CAP_TAB_ZH.match(lines[k]) or CAP_TAB_EN.match(lines[k])))


def detect_floats(lines):
    """Find whole relocatable objects: image/table + caption + sub-captions.

    Returns dicts with kind ('fig'/'tab'), num, start/end line indices
    (inclusive) and whether the block already carries our marker.

    围栏代码块先整块换成占位符再找：伪代码里常有以 | 开头的对齐行、字符串
    `Table 2`、`# 图 3` 注释，不抹掉就会被当成表格/图注搬走，代码块就此搬散。
    占位符与原文行数一一对应，所以返回的下标对原始 lines 仍然有效。
    """
    lines = mask_code(lines)
    floats, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        start, marked = i, False
        if FLOAT_MOVED.search(line):
            marked = True
            j = i + 1
            while j < n and not FLOAT_ENDTAG.search(lines[j]):
                j += 1
            end = min(j, n - 1)
            i = end + 1
        elif FIGURE_START.search(line):
            j = i + 1
            while j < n and not FIGURE_END.search(lines[j]):
                j += 1
            end = min(j, n - 1)
            i = end + 1
        elif lone_image(line):
            j = i
            while j < n and lone_image(lines[j]):
                j += 1
            end = j - 1
            i = j
        elif TABLE_LINE.match(line):
            j = _table_run(lines, i)
            if not _looks_like_table(lines, i, j):
                i = j
                continue
            end = j - 1
            i = j
        else:
            i += 1
            continue

        # A caption may sit one blank line below the image/table. Take it into
        # the block, then any immediately following (a)(b)(c) sub-caption list.
        k = end + 1
        if k < n and not lines[k].strip():
            k += 1
        num, kind = None, None
        if k < n:
            m = CAP_ZH.match(lines[k]) or CAP_EN.match(lines[k])
            mt = CAP_TAB_ZH.match(lines[k]) or CAP_TAB_EN.match(lines[k])
            if m:
                num, kind = m.group(1), "fig"
            elif mt:
                num, kind = mt.group(1), "tab"
            if num:
                end = k
                i = k + 1
                while i < n and SUBCAP_LINE.match(lines[i]):
                    end = i
                    i += 1
        if num is None and marked:
            mm = re.search(r"\b(?:fig|tab)=([^\s>]+)", line)
            if mm:
                num = mm.group(1)
                kind = "tab" if re.search(r"\btab=", line) else "fig"
        if num is None:
            continue                    # 无编号图：不猜位置，交给人工
        floats.append({"kind": kind, "num": num, "start": start,
                       "end": end, "marked": marked})
    return floats


def body_ref_lines(lines, floats, num, kind, skip_before=0):
    """Lines of prose that first mention 图 N / Table N, outside any float.

    ``skip_before`` blanks the YAML front matter (which is metadata, not prose)
    without shifting line numbers used for insertion.
    """
    inside = set()
    for f in floats:
        inside.update(range(f["start"], f["end"] + 1))
    rx_a = REF_ZH if kind == "fig" else REF_TAB_ZH
    rx_b = REF_EN if kind == "fig" else REF_TAB_EN
    out = []
    for i, line in enumerate(mask_code(lines)):
        if i < skip_before or i in inside:
            continue
        if (CAP_ZH.match(line) or CAP_EN.match(line)
                or CAP_TAB_ZH.match(line) or CAP_TAB_EN.match(line)):
            continue
        if num in rx_a.findall(line) or num in rx_b.findall(line):
            out.append(i)
    return out


def proximity_advice(text, tol=4):
    """Report floats that are not next to their first citation."""
    lines = text.split("\n")
    floats = detect_floats(lines)
    head = frontmatter_line_count(text)
    out = []
    for f in floats:
        label = "图" if f["kind"] == "fig" else "表"
        refs = body_ref_lines(lines, floats, f["num"], f["kind"], skip_before=head)
        if not refs:
            out.append(f"{label} {f['num']} 正文没有引用，无法判断就近；"
                       "保持原位并在交付报告中列为「未就近对象」")
            continue
        d = f["start"] - refs[0]
        if d < 0 or d > tol:
            where = "在引用之前" if d < 0 else "在引用之后"
            out.append(f"{label} {f['num']} 距首次引用 {abs(d)} 行（{where}），"
                       "用 `figures.py relocate --apply` 移到引用段落之后")
    return out


def block_ranges(text):
    out = []
    pos = 0
    while True:
        m = FIGURE_START.search(text, pos)
        if not m:
            return out
        e = FIGURE_END.search(text, m.end())
        if not e:
            out.append((m.start(), len(text)))
            return out
        out.append((m.start(), e.end()))
        pos = e.end()


def check_files(entries, base_dir, labels, require_alt=True):
    """Missing files are listed one by one; empty alt is aggregated.

    A figure usually has no alt text after extraction, so listing it per image
    turns one habit into twenty identical lines and buries the real problems.
    """
    problems, no_alt = [], []
    for e in entries:
        if e["kind"] != "image":
            continue
        src = e["src"]
        if not e.get("alt"):
            no_alt.append(e["line"])
        if re.match(r"^[a-z]+://", src, re.I):
            continue
        p = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.exists(p):
            problems.append(f"{labels} 第 {e['line']} 行：图片文件不存在 `{src}`")
    # alt 是译文侧的要求：抽取出来的原文图本来就没有 alt，对它报这一条只是噪声。
    if no_alt and require_alt:
        problems.append(f"{labels} 有 {len(no_alt)} 张图的 alt 为空（第 "
                        + "、".join(str(x) for x in no_alt[:8])
                        + ("…" if len(no_alt) > 8 else "")
                        + " 行）：alt 写成「图 N + 一句描述」，检索和转 docx 时都用得上")
    return problems


def cmd_audit(args):
    src_text = strip_notation(read(args.source))
    tgt_text = strip_notation(read(args.target))
    s_entries, t_entries = scan(src_text), scan(tgt_text)

    s_caps = [e for e in s_entries if e["kind"] == "caption"]
    t_caps = [e for e in t_entries if e["kind"] == "caption"]
    s_imgs = [e for e in s_entries if e["kind"] == "image"]
    t_imgs = [e for e in t_entries if e["kind"] == "image"]
    blocks = block_ranges(tgt_text)

    tgt_dir = os.path.dirname(os.path.abspath(args.target))
    src_dir = os.path.dirname(os.path.abspath(args.source))

    print(f"原文：{args.source}（图注 {len(s_caps)} 条，图片 {len(s_imgs)} 张）")
    print(f"译文：{args.target}（图注 {len(t_caps)} 条，图片 {len(t_imgs)} 张，"
          f"并排图块 {len(blocks)} 个）")

    issues, advice = [], []

    # 1) 图注：译文的图注数与源文比，是"图有没有丢"最可靠的锚
    if len(t_caps) == len(s_caps):
        print(f"  [OK] 图注 {len(t_caps)} 条，与原文一致")
    else:
        issues.append(f"图注数不一致：原文 {len(s_caps)} 条，译文 {len(t_caps)} 条")

    # 2) 图号序列：缺号、重号
    for name, caps in (("原文", s_caps), ("译文", t_caps)):
        nums = [int(re.sub(r"\D", "", c["num"])) for c in caps if re.sub(r"\D", "", c["num"])]
        if len(nums) >= 2:
            dup = sorted({n for n in nums if nums.count(n) > 1})
            gaps = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
            if dup:
                issues.append(f"{name}图号重复：{dup}")
            if gaps:
                issues.append(f"{name}图号跳号：{gaps}")
    nums_t = sorted(int(re.sub(r"\D", "", c["num"])) for c in t_caps if re.sub(r"\D", "", c["num"]))
    if nums_t and not any("图号" in x for x in issues):
        print(f"  [OK] 图号无缺号：{nums_t[0]}–{nums_t[-1]}（共 {len(nums_t)} 条）")

    # 3) 连续裸图：拆散的多面板图
    runs, cur = [], []
    for e in t_entries:
        if e["kind"] == "image":
            cur.append(e)
            continue
        if len(cur) >= 2:
            runs.append(cur)
        cur = []
    if len(cur) >= 2:
        runs.append(cur)
    for r in runs:
        advice.append(f"第 {r[0]['line']}–{r[-1]['line']} 行连续 {len(r)} 张图，中间没有文字："
                      "疑似被拆散的多面板图，用 `figures.py group --apply` 合成并排图块（或回 PDF 整块重裁）")

    # 4) 图注是否紧跟图片
    for e in t_imgs:
        nxt = next((c for c in t_caps if c["line"] > e["line"]), None)
        if nxt is None:
            advice.append(f"第 {e['line']} 行的图后面没有图注")
        elif nxt["line"] - e["line"] > 8:
            advice.append(f"第 {e['line']} 行的图与第 {nxt['line']} 行的图注相隔 {nxt['line'] - e['line']} 行，"
                          "中间可能插进了别的段落")

    # 5) 文件是否存在、alt 是否为空
    issues += check_files(t_entries, tgt_dir, "译文")
    issues += [p.replace("译文", "原文")
               for p in check_files(s_entries, src_dir, "原文", require_alt=False)]
    # 并排图块整块被 scan() 折叠，块内的 <img> 不会进 entries；单独查一次，
    # 否则图块里的断图、空 alt 完全查不出来。
    for name, txt, base in (("译文", tgt_text, tgt_dir), ("原文", src_text, src_dir)):
        for a, b in block_ranges(txt):
            block = txt[a:b]
            ln = txt[:a].count("\n") + 1
            for tag in re.finditer(r"<img[^>]*>", block, re.I):
                sm, am = IMG_HTML.search(tag.group(0)), ALT_HTML.search(tag.group(0))
                if sm and not re.match(r"^[a-z]+://", sm.group(1), re.I):
                    p = sm.group(1)
                    fp = p if os.path.isabs(p) else os.path.join(base, p)
                    if not os.path.exists(fp):
                        issues.append(f"{name} 第 {ln} 行并排图块：图片文件不存在 `{p}`")
                if name == "译文" and (not am or not am.group(1).strip()):
                    advice.append(f"{name} 第 {ln} 行并排图块内有 <img> 的 alt 为空")

    # 6) 正文引用 vs 图注
    body_lines = [l for l in tgt_text.split("\n")
                  if not CAP_ZH.match(l) and not CAP_EN.match(l)]
    refs = set()
    for l in body_lines:
        refs.update(int(n) for n in REF_ZH.findall(l))
        refs.update(int(n) for n in REF_EN.findall(l))
    cap_nums = {int(re.sub(r"\D", "", c["num"])) for c in t_caps if re.sub(r"\D", "", c["num"])}
    dangling = sorted(refs - cap_nums)
    if dangling:
        issues.append(f"正文引用了不存在的图号：{dangling}（译文图注只有 {sorted(cap_nums)}）")
    elif refs & cap_nums:
        print(f"  [OK] 正文引用的 {len(refs & cap_nums)} 个图号都能找到图注")

    # 7) 就近性：PDF 的浮动位置不该带进 Markdown
    advice += proximity_advice(tgt_text, args.tol)

    if issues:
        print(f"\n  问题 {len(issues)} 条：")
        for x in issues:
            print(f"    - {x}")
    if advice:
        print(f"\n  排版建议 {len(advice)} 条：")
        for x in advice:
            print(f"    - {x}")
    if not issues and not advice:
        print("\n  图的编号、图注、路径都对得上。图的版式仍需扫一眼：宽图会不会被压小、"
              "多面板会不会被拆开。")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["类型", "位置", "说明"])
            for x in issues:
                w.writerow(["问题", "", x])
            for x in advice:
                w.writerow(["建议", "", x])
            for c in t_caps:
                w.writerow(["图注", f"第 {c['line']} 行", f"图 {c['num']}｜{c['text']}"])
        print(f"\n图目录：{os.path.abspath(args.csv)}")

    return 1 if (args.strict and issues) else 0


def cmd_relocate(args):
    """Move each float next to the paragraph that first cites it.

    Only the position changes. The block (image, caption, sub-captions, table,
    table note) is moved as one unit, and the two marker comments make the
    operation idempotent and give fidelity_check.py something to strip.
    """
    path = args.target
    text = read(path)
    lines = text.split("\n")
    floats = detect_floats(lines)
    head = frontmatter_line_count(text)

    plan = []
    for f in floats:
        label = "图" if f["kind"] == "fig" else "表"
        refs = body_ref_lines(lines, floats, f["num"], f["kind"], skip_before=head)
        if not refs:
            plan.append((f, None, "无引用",
                         f"{label} {f['num']} 正文没有引用，保持原位（列进交付报告）"))
            continue
        anchor = refs[0]
        d = f["start"] - anchor
        if 0 <= d <= args.tol:
            act = "已在锚点附近" if f["marked"] else "原本就近"
            plan.append((f, anchor, act,
                         f"{label} {f['num']} 距首次引用 {d} 行，无需移动"))
            continue
        plan.append((f, anchor, "移动",
                     f"{label} {f['num']} 从第 {f['start'] + 1} 行移到"
                     f"第 {anchor + 1} 行引用段之后（原距离 {d} 行）"))

    print(f"译文：{path}")
    print(f"识别到 {len(floats)} 个浮动对象；就近阈值 {args.tol} 行")
    for _f, _a, act, desc in plan:
        print(f"  [{act}] {desc}")
    moves = [(f, a) for f, a, act, _ in plan if act == "移动"]
    if not moves:
        print("没有需要搬动的块。")

    if args.apply and moves:
        moved_lines = set()
        for f, _ in moves:
            moved_lines.update(range(f["start"], f["end"] + 1))
        keep = [(i, l) for i, l in enumerate(lines) if i not in moved_lines]
        pos_of = {orig: p for p, (orig, _) in enumerate(keep)}
        insertions = {}
        for f, anchor in moves:
            p = pos_of.get(anchor)
            if p is not None:
                insertions.setdefault(p, []).append((f, anchor))
        out = []
        for p, (_orig, line) in enumerate(keep):
            out.append(line)
            for f, anchor in insertions.get(p, []):
                block = [l for l in lines[f["start"]:f["end"] + 1]
                         if not FLOAT_MOVED.search(l) and not FLOAT_ENDTAG.search(l)]
                out.append("")          # 引用段与图块之间留空行，否则渲染会连成一段
                out.append(f"<!-- float:moved {f['kind']}={f['num']} "
                           f"anchor=L{anchor + 1} -->")
                out.extend(block)
                out.append("<!-- float:end -->")
                out.append("")
        # 搬走后原位置会留下一串空行；压成一个，别把阅读版弄出大段空白。
        cleaned, blanks = [], 0
        for line in out:
            if not line.strip():
                blanks += 1
                if blanks >= 2:
                    continue
            else:
                blanks = 0
            cleaned.append(line)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(cleaned))
        print(f"\n已搬动 {len(moves)} 个浮动对象，写回 {path}")
        print("提醒：重跑 fidelity_check.py --float-reflow 与 figures.py audit。")
    elif not args.apply and moves:
        print("\n只做报告，未改文件。确认后加 --apply 写回。")

    if args.csv:
        csv_path = os.path.abspath(args.csv)
        os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["类型", "编号", "原行号", "锚段落行号", "动作", "说明"])
            for f, anchor, act, desc in plan:
                w.writerow(["图" if f["kind"] == "fig" else "表", f["num"],
                            f["start"] + 1, anchor + 1 if anchor is not None else "",
                            act, desc])
        print(f"重定位清单：{csv_path}")
    return 0


def cmd_group(args):
    """Rewrite a run of consecutive bare images as one side-by-side block."""
    path = args.target
    text = read(path)
    lines = text.split("\n")

    in_block = False
    runs, cur = [], []
    for i, line in enumerate(lines):
        if FIGURE_START.search(line):
            in_block = True
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
            continue
        if FIGURE_END.search(line):
            in_block = False
            continue
        if in_block:
            continue
        img = lone_image(line)
        if img:
            cur.append((i, img))
            continue
        if line.strip() and cur:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    runs = [r for r in runs if len(r) >= args.min]

    if not runs:
        print("没有找到连续的裸图，不需要合成。")
        return 0

    print(f"找到 {len(runs)} 组连续裸图：")
    for r in runs:
        print(f"  第 {r[0][0] + 1}–{r[-1][0] + 1} 行，{len(r)} 张："
              + "、".join(os.path.basename(x[1]["src"]) for x in r[:4])
              + ("…" if len(r) > 4 else ""))

    if not args.apply:
        print("\n只做报告，未改文件。确认后加 --apply 合成并排图块。")
        print("合成后每行 " + str(args.per_row) + " 张，宽度 " + args.width
              + "；图注保持原位置不动。")
        return 0

    for r in reversed(runs):       # 从后往前改，行号不会错位
        start = r[0][0]
        end = r[-1][0]
        rows = [r[k:k + args.per_row] for k in range(0, len(r), args.per_row)]
        block = ["<!-- figure:start -->", "<table>"]
        for row in rows:
            # alt 只在原文本来就有的时候保留：自动拼一个「图 fig2a.png」比空着更糟，
            # 它会变成一个假的中文说明，还会被误当成已填。
            cells = "".join(
                f'<td><img src="{e["src"]}"'
                + (f' alt="{e["alt"]}"' if e["alt"] else "")
                + f' width="{args.width}"></td>' for _, e in row)
            block.append(f"<tr>{cells}</tr>")
        block += ["</table>", "<!-- figure:end -->"]
        lines[start:end + 1] = block

    out = "\n".join(lines)
    if args.dry_run:
        print("\n--- 预览 ---")
        print(out[:1200])
        return 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    print(f"\n已合成 {len(runs)} 个并排图块，写回 {path}")
    print("提醒：合成后重跑 fidelity_check.py 与 figures.py audit，确认图数与图注仍然对得上。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="审计与整理译文中的图。")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="核对图注、图号、路径、正文引用与就近性")
    a.add_argument("source")
    a.add_argument("target")
    a.add_argument("--csv", default="")
    a.add_argument("--strict", action="store_true")
    a.add_argument("--tol", type=int, default=4,
                   help="图块距首次引用多少行内算就近（默认 4）")
    a.set_defaults(func=cmd_audit)

    r = sub.add_parser("relocate", help="把浮动对象移到正文首次引用段落之后")
    r.add_argument("target")
    r.add_argument("--apply", action="store_true", help="真的写回文件")
    r.add_argument("--csv", default="", help="重定位清单 CSV")
    r.add_argument("--tol", type=int, default=4,
                   help="块首距锚段落多少行内算就近（默认 4）")
    r.set_defaults(func=cmd_relocate)

    g = sub.add_parser("group", help="把连续裸图合成为并排图块")
    g.add_argument("target")
    g.add_argument("--apply", action="store_true", help="真的写回文件")
    g.add_argument("--dry-run", action="store_true", help="打印结果但不写回")
    g.add_argument("--min", type=int, default=2, help="连续几张才算一组")
    g.add_argument("--per-row", type=int, default=2, help="每行放几张")
    g.add_argument("--width", default="48%", help="每张图宽度")
    g.set_defaults(func=cmd_group)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
