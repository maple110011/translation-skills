#!/usr/bin/env python3
"""Audit a translated Markdown against its source.

The five rules this translation workflow promises are mostly not verifiable by
reading the output — a translator (human or model) cannot see its own dropped
sentence. This script turns four of them into counts:

======================  ==================================================
rule                    what is measured
======================  ==================================================
不得增删信息             block-kind sequence must match one-to-one; block
                        counts per kind must match
保留 Markdown 结构       heading levels, list markers, quote depth, table
                        rows, image targets
引用保留原文样式         every citation string found in the source must
                        appear verbatim in the target
公式格式统一             no `\\[` / `\\(` may survive; display blocks counted
======================  ==================================================

It also reports paragraphs that look untranslated, and (when a glossary is
supplied) source terms that were left in English or rendered two ways. Glossary
rows with ``kind=keep`` / ``dst=@keep`` are audited in reverse: the English
string must appear and the banned Chinese coinages in ``alt`` must not.

``--float-reflow`` is for translations whose figures/tables have been moved
next to their first citation by ``figures.py relocate``. Body blocks are still
compared one-to-one; floats are stripped from the sequence and audited instead
as multisets of image paths, caption numbers and table rows.

None of this replaces reading the output. It catches the mechanical failures
so that human attention can go to meaning.

Usage
-----
    python fidelity_check.py source.md target.md
    python fidelity_check.py source.md target.md --glossary g.csv --strict
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathscan import (FIGURE_END, FIGURE_SENTINEL, FIGURE_START,  # noqa: E402
                      collapse_figures, count_figure_blocks, strip_notation)

try:                                    # console may be cp936: never die on ✓
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
QUOTE = re.compile(r"^(\s*)>\s?")
TABLE_ROW = re.compile(r"^\s*\|")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
IMG_HTML = re.compile(r"<img[^>]*\bsrc=[\"\']([^\"\']+)", re.I)
DISPLAY_OPEN = re.compile(r"^\s*\$\$")
# A source that has not been through normalize_math.py may still use \[ ... \].
BRACKET_OPEN = re.compile(r"^\s*\\\[\s*$")
BRACKET_CLOSE = re.compile(r"^\s*\\\]\s*$")
BRACKET_ONELINE = re.compile(r"^\s*\\\[.*\\\]\s*$")
LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]")
CJK = re.compile(r"[\u4e00-\u9fff]")
FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)


def strip_frontmatter(text):
    """Drop a YAML front matter block before reconciling.

    The block carries paper metadata, not prose. If it were left in, the target
    would appear to have one extra block and every downstream comparison would
    shift by one — the kind of failure that reads as "the translation lost a
    paragraph" when nothing was lost.
    """
    m = FRONT.match(text)
    return text[m.end():] if m else text

# --------------------------------------------------------------------------
# 浮动对象识别（`--float-reflow` 用）
#
# PDF 把图/表挪到页顶页底，Markdown 里已按首次引用重定位。这些块的**位置**
# 不再与原文一致，但内容、编号、数量必须一致。剥离时只认明确的浮动行，
# 不认普通段落，否则「正文段落被挪走」也会被放过。
# --------------------------------------------------------------------------
FLOAT_MARK = re.compile(r"<!--\s*float:(?:moved|end)\b[^>]*-->", re.I)
IMG_ONLY = re.compile(r"^\s*(?:!\[[^\]]*\]\([^)]*\)|<img[^>]*>)\s*$", re.I)
# 图注/表注行。编号后必须跟标点、全角空格或行尾，否则 "图 2 表明…" 这类
# 正文段落会被误当成图注剥掉。
CAP_ANY = re.compile(
    r"^\s*(?:\*\*)?(?:图|表|Figure|Fig\.|Table)\s*(\d+(?:\.\d+)?)(?:\*\*)?"
    r"(?:\s*[:：.．、]|\s*　|\s*$)", re.I)
SUBCAP = re.compile(r"^\s*[-*+]\s*\([a-z]\)\s", re.I)
TABLE_LINE = re.compile(r"^\s*\|")

CITE_PAREN = re.compile(r"\([A-Z][^()]{0,90}?\b(?:19|20)\d{2}[a-z]?\b[^()]{0,40}?\)")
# 中文译文里的括号引用一律是全角：`（Shaikh, 2016, p. 42）`。不认这一形态，
# 每一条都会报成"缺失"，而实际上译文把引用完整保留了。
CITE_PAREN_W = re.compile(r"（[A-Z][^（）()]{0,90}?\b(?:19|20)\d{2}[a-z]?\b[^（）()]{0,40}?）")
CITE_BRACKET = re.compile(r"\[\d+(?:\s*[,–\-\u2013]\s*\d+)*\]")
CITE_NARRATIVE = re.compile(
    r"\b[A-Z][A-Za-z\u00C0-\u024F'’\-]+"
    r"(?:\s+(?:et\s+al\.?|and|&)\s+[A-Za-z\u00C0-\u024F'’\-]+)?"
    r"\s*\((?:19|20)\d{2}[a-z]?\)")


# --------------------------------------------------------------------------
def strip_code_and_math(text):
    """Blank out fenced code and math so citation/term scans do not hit them."""
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        out.append(line)
    joined = "\n".join(out)
    joined = re.sub(r"\$\$.+?\$\$", " ", joined, flags=re.S)
    joined = re.sub(r"(?<!\\)\$.+?(?<!\\)\$", " ", joined, flags=re.S)
    joined = re.sub(r"`[^`\n]*`", " ", joined)
    return joined


def is_float_line(line, in_fig=False):
    """Whether a line belongs to a relocatable figure/table object.

    Deliberately conservative: only images, captions, sub-caption list items,
    table rows, and the two marker comments. A prose paragraph that happens to
    mention 图 3 is *not* a float and must stay in the block sequence.
    """
    if in_fig or FIGURE_SENTINEL in line:
        return True
    if FLOAT_MARK.search(line):
        return True
    if IMG_ONLY.match(line) or CAP_ANY.match(line) or SUBCAP.match(line):
        return True
    return bool(TABLE_LINE.match(line))


def strip_float_lines(text):
    """Blank out float lines so the *body* block sequence can be compared.

    Both documents go through this in --float-reflow mode. Floats themselves
    are audited separately by count, by image path multiset and by caption
    number, so blanking them here does not hide a lost figure.
    """
    out, in_fig = [], False
    for line in text.split("\n"):
        if FIGURE_START.search(line):
            in_fig = True
            out.append("")
            continue
        if FIGURE_END.search(line):
            in_fig = False
            out.append("")
            continue
        out.append("" if is_float_line(line, in_fig) else line)
    return "\n".join(out)


def cap_numbers(text):
    """Caption numbers in document order, as strings ('1', '2', 'A.1')."""
    nums = []
    for line in text.split("\n"):
        m = CAP_ANY.match(line)
        if m:
            nums.append(m.group(1))
    return nums


def blocks(text):
    """Flatten the document into an ordered list of structural blocks.

    Yields ``(kind, detail)``; ``detail`` carries what must stay identical
    (heading level, list marker shape, quote depth, image target).
    """
    result = []
    lines = text.split("\n")
    i, in_fence, in_math, in_bracket = 0, False, False, False
    para = []

    def flush():
        nonlocal para
        if para:
            body = " ".join(x.strip() for x in para).strip()
            if body:
                result.append(("p", ""))
            para = []

    while i < len(lines):
        line = lines[i]
        if FENCE.match(line):
            flush()
            in_fence = not in_fence
            result.append(("code", ""))
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        if in_bracket:
            if BRACKET_CLOSE.match(line):
                in_bracket = False
                result.append(("math", ""))
            i += 1
            continue
        if in_math:
            if line.strip().startswith("$$"):
                in_math = False
                result.append(("math", ""))
            i += 1
            continue
        if BRACKET_OPEN.match(line):
            flush()
            in_bracket = True
            i += 1
            continue
        if BRACKET_ONELINE.match(line):
            flush()
            result.append(("math", ""))
            i += 1
            continue
        if DISPLAY_OPEN.match(line):
            flush()
            s = line.strip()
            if s == "$$" or s.count("$$") < 2:
                in_math = True          # opening delimiter, body follows
            else:
                result.append(("math", ""))   # single-line $$...$$
            i += 1
            continue
        m = HEADING.match(line)
        if m:
            flush()
            result.append(("h", len(m.group(1))))
            i += 1
            continue
        m = LIST_ITEM.match(line)
        if m:
            flush()
            ordered = m.group(2)[0].isdigit()
            depth = len(m.group(1).expandtabs(4)) // 2
            result.append(("li", (depth, ordered)))
            i += 1
            continue
        m = QUOTE.match(line)
        if m:
            flush()
            result.append(("q", len(m.group(1).expandtabs(4)) // 2))
            i += 1
            continue
        if TABLE_ROW.match(line):
            flush()
            result.append(("tr", ""))
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()
    return result


def images(text):
    """Image targets in either syntax, minus the 并排图块 sentinel.

    A target may carry its figures as `<img>` inside a marked figure block
    (that is how multi-panel figures are laid out side by side); both syntaxes
    count, and the block itself is counted separately so that one logical
    figure with four panels does not look like four extra figures.
    """
    out = [m.group(1).strip() for m in IMAGE.finditer(text)]
    out += [m.group(1).strip() for m in IMG_HTML.finditer(text)]
    return [x for x in out if FIGURE_SENTINEL not in x]


def citations(text):
    """Split citations into two kinds, because they are checked differently.

    ``verbatim`` — parenthetical and numeric markers such as ``(Shaikh, 2016,
    p. 42)`` or ``[12]``. These are literature *labels*, so rule 4 requires them
    to survive character for character.

    ``narrative`` — ``Solow (1959)`` forms, where the name is the subject of a
    translated sentence and only the year must survive. Requiring the whole
    string would flag the perfectly normal rendering 索洛（Solow, 1959）.
    """
    clean = strip_code_and_math(text)
    verbatim, narrative = [], []
    for rx in (CITE_BRACKET, CITE_PAREN):
        verbatim += [re.sub(r"\s+", " ", m.group(0)).strip() for m in rx.finditer(clean)]
    verbatim += [re.sub(r"\s+", " ", m.group(0)).strip().replace("（", "(").replace("）", ")")
                 for m in CITE_PAREN_W.finditer(clean)]
    narrative += [re.sub(r"\s+", " ", m.group(0)).strip()
                  for m in CITE_NARRATIVE.finditer(clean)]

    def dedupe(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return dedupe(verbatim), dedupe(narrative)


def paragraphs(text, drop_floats=False):
    """Collect prose paragraphs, skipping code, display math, and structure.

    With drop_floats the relocatable objects are skipped too. That keeps the
    remaining paragraphs aligned by position even after a figure has been
    moved next to its first citation, so length_outliers does not fire on
    every paragraph after the move.
    """
    out, buf = [], []
    in_fence = in_math = in_bracket = False
    for line in text.split("\n"):
        if drop_floats and is_float_line(line):
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            buf = []
            continue
        if in_fence:
            continue
        if in_bracket:
            if BRACKET_CLOSE.match(line):
                in_bracket = False
            continue
        if in_math:
            if line.strip().startswith("$$"):
                in_math = False
            continue
        if BRACKET_OPEN.match(line) or BRACKET_ONELINE.match(line):
            if buf:
                out.append(" ".join(buf))
                buf = []
            if BRACKET_OPEN.match(line):
                in_bracket = True
            continue
        if DISPLAY_OPEN.match(line):
            if buf:
                out.append(" ".join(buf))
                buf = []
            if line.strip().count("$$") < 2:
                in_math = True
            continue
        if not line.strip() or HEADING.match(line) or LIST_ITEM.match(line) \
                or TABLE_ROW.match(line) or QUOTE.match(line):
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        buf.append(line.strip())
    if buf:
        out.append(" ".join(buf))
    return out


# --------------------------------------------------------------------------
def compare_sequence(a, b, label):
    """Compare two block sequences and report the first divergence."""
    ka = [x[0] for x in a]
    kb = [x[0] for x in b]
    if ka == kb:
        return True, f"{label}：{len(a)} 块，结构一致"
    n = min(len(ka), len(kb))
    at = next((i for i in range(n) if ka[i] != kb[i]), n)
    detail = []
    if at < n:
        detail.append(f"第 {at + 1} 个块：源为 {ka[at]}，译为 {kb[at]}")
    detail.append(f"源 {len(ka)} 块，译 {len(kb)} 块")
    # show neighbourhood
    lo = max(0, at - 2)
    detail.append("源：" + " ".join(ka[lo:at + 3]))
    detail.append("译：" + " ".join(kb[lo:at + 3]))
    return False, f"{label}：结构不一致\n    " + "\n    ".join(detail)


def compare_detail(a, b, kind, label, show=3):
    va = [x[1] for x in a if x[0] == kind]
    vb = [x[1] for x in b if x[0] == kind]
    if va == vb:
        return True, f"{label}：{len(va)} 项，一致"
    diffs = [i for i in range(min(len(va), len(vb))) if va[i] != vb[i]]
    msg = [f"{label}：不一致（源 {len(va)}，译 {len(vb)}）"]
    for i in diffs[:show]:
        msg.append(f"    第 {i + 1} 项：源 {va[i]!r} ≠ 译 {vb[i]!r}")
    return False, "\n".join(msg)


def latin_ratio(text):
    """Share of Latin letters among all letters, ignoring math and code.

    A paragraph of pure LaTeX scores 100% Latin and would otherwise be reported
    as untranslated, so math is stripped before measuring.
    """
    cleaned = re.sub(r"\$\$.+?\$\$", " ", text, flags=re.S)
    cleaned = re.sub(r"(?<!\\)\$.+?(?<!\\)\$", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    l, c = len(LATIN.findall(cleaned)), len(CJK.findall(cleaned))
    total = l + c
    return (l / total if total else 0.0), total


KEEP_VALUES = ("@keep", "keep", "保留英文", "保留原文")


def check_glossary(target, path):
    warnings = []
    rows, keeps = [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            src = (r.get("src") or "").strip()
            dst = (r.get("dst") or "").strip()
            alt = (r.get("alt") or "").strip()
            kind = (r.get("kind") or "").strip()
            # kind=keep（或 dst=@keep）是「保留英文原文、不造中文词」的裁定。
            # 它不该被当成漏译；反过来要查英文串在不在、有没有偷偷译成中文。
            if kind.lower() == "keep" or dst.lower() in KEEP_VALUES:
                if src:
                    keeps.append((src, alt))
                continue
            # The accumulated master table is mostly proper nouns. Flagging a
            # name left in Latin script is not a terminology error — `Shaikh`
            # inside a parenthetical citation is correct — so skip them.
            if kind in ("name", "place", "uncertain"):
                continue
            if src and dst:
                rows.append((src, dst, alt))
    # Literature citations keep author names in Latin script by rule, so scan
    # for terms on text with the citations removed.
    clean = strip_code_and_math(target)
    for rx in (CITE_BRACKET, CITE_PAREN, CITE_NARRATIVE):
        clean = rx.sub(" ", clean)
    untranslated, variants = [], []
    for src, dst, alt in rows:
        # Only concept-like entries are worth checking: short lowercase phrases.
        if not re.fullmatch(r"[a-z][a-z\-\s]{2,40}", src):
            continue
        if re.search(rf"(?<![A-Za-z]){re.escape(src)}(?![A-Za-z])", clean, re.I) \
                and dst not in clean:
            untranslated.append(f"{src}（应译作「{dst}」）")
        for v in [x.strip() for x in re.split(r"[／/|]", alt) if x.strip()]:
            # `局部化` 与 `局部化的` 是同一个词的名词/形容词形态，不是异译；
            # 只有两种写法互不包含时才值得提醒。
            if v in clean and v != dst and v not in dst and dst not in v:
                variants.append(f"{src}：出现异译「{v}」，应为「{dst}」")
    if untranslated:
        warnings.append("疑似未译术语：\n    " + "\n    ".join(untranslated[:15])
                        + (f"\n    …共 {len(untranslated)} 条" if len(untranslated) > 15 else ""))
    if variants:
        warnings.append("术语异译：\n    " + "\n    ".join(variants[:15])
                        + (f"\n    …共 {len(variants)} 条" if len(variants) > 15 else ""))

    # 保留英文的条目反向检查：英文串必须在正文出现；alt 里列的是禁止出现的
    # 中文写法（自造译名），见一个报一个。这是「同一术语不得一处英文一处中文」
    # 的机械部分。
    missing_keep, translated_keep = [], []
    for src, alt in keeps:
        if not re.search(rf"(?<![A-Za-z]){re.escape(src)}(?![A-Za-z])", clean, re.I):
            missing_keep.append(f"{src}（正文里找不到这个英文串）")
        for banned in [x.strip() for x in re.split(r"[／/|]", alt) if x.strip()]:
            if banned in clean:
                translated_keep.append(f"{src}：出现了禁止的中文写法「{banned}」")
    if missing_keep:
        warnings.append("保留英文术语缺失：\n    " + "\n    ".join(missing_keep[:15]))
    if translated_keep:
        warnings.append("保留英文术语被译成中文：\n    " + "\n    ".join(translated_keep[:15]))
    if keeps and not missing_keep and not translated_keep:
        print(f"✓ 保留英文术语：{len(keeps)} 条，英文串齐全、无自造中文译名")
    return warnings


MARKUP = re.compile(r"</?(?:table|tr|td|th|thead|tbody|img|div|span|figure)\b", re.I)

ENV_NAMES = {
    "Theorem": "定理", "Lemma": "引理", "Proposition": "命题", "Corollary": "推论",
    "Definition": "定义", "Assumption": "假设", "Claim": "断言", "Conjecture": "猜想",
    "Remark": "注", "Example": "例", "Algorithm": "算法", "Proof": "证明",
}
_ENV_TAIL = r"\s*\.?\s*(?:\d+(?:\.\d+)*|[A-Z])(?![\w])"


def theorem_counts(src, tgt):
    """Numbered theorem-like environments, counted per label.

    A dropped Lemma 3 or a Proposition promoted to Theorem is a change in what
    the paper claims, and it leaves no trace in the block structure — the
    paragraph is still there, it is just labelled differently. Counting the
    labels is the cheapest way to catch it.
    """
    def count(text, labels):
        c = Counter()
        pat = re.compile(r"(?m)^[\s>#*+\-]*(" + "|".join(labels) + r")" + _ENV_TAIL)
        for m in pat.finditer(text):
            c[labels[m.group(1)]] += 1
        return c

    en = {k: k for k in ENV_NAMES}
    zh = {v: v for v in ENV_NAMES.values()}
    return count(src, en), count(tgt, zh)



def length_outliers(src, tgt, drop_floats=False):
    """Flag paragraphs whose translated length is far off the document norm.

    Structural checks cannot see a sentence dropped *inside* a paragraph, which
    is the most common silent failure. Length is a crude proxy: compute
    Chinese-characters-per-English-word for every aligned paragraph, take the
    document median, and report paragraphs far below or above it.

    This is a heuristic and it does produce false positives — a paragraph that
    is mostly a table, a list of names, or dense notation has a legitimate
    ratio far from the median. Those shapes are skipped, and the remaining
    warnings are advisory: confirm each one against the source before acting.
    """
    ps, pt = paragraphs(src, drop_floats), paragraphs(tgt, drop_floats)
    if len(ps) != len(pt) or len(ps) < 6:
        return []
    ratios, rows = [], []
    for i, (a, b) in enumerate(zip(ps, pt)):
        if MARKUP.search(a) or MARKUP.search(b) or a.count("|") >= 2 or b.count("|") >= 2:
            continue
        a_clean = strip_code_and_math(a)
        b_clean = strip_code_and_math(b)
        # 括号引用在译文里按规则逐字保留，不产生中文字符。计「需要翻译的
        # 英文词」时先剥掉，否则「一串应用领域 + 十条引文」这类段落的
        # 字/词比会低得像漏译。
        a_clean = re.sub(r"\([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*\)", " ", a_clean)
        words = len(re.findall(r"[A-Za-z\u00C0-\u024F]+", a_clean))
        chars = len(CJK.findall(b_clean))
        if words < 15 or chars < 40:
            continue
        r = chars / words
        ratios.append(r)
        rows.append((i, r, words, chars, b))
    if len(ratios) < 6:
        return []
    ratios_sorted = sorted(ratios)
    median = ratios_sorted[len(ratios_sorted) // 2]
    if median <= 0:
        return []
    out = []
    for i, r, words, chars, b in rows:
        if r < median * 0.6:
            out.append(f"第 {i + 1} 段偏短（{chars} 字 / {words} 词 = {r:.2f}，"
                       f"中位数 {median:.2f}）：{b[:60]}…")
        elif r > median * 1.8:
            out.append(f"第 {i + 1} 段偏长（{chars} 字 / {words} 词 = {r:.2f}，"
                       f"中位数 {median:.2f}）：{b[:60]}…")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="对照原文检查译文的保真度。")
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--glossary", help="术语表 CSV（src,dst[,alt]），可选")
    ap.add_argument("--strict", action="store_true", help="有硬性失败时返回码 1")
    ap.add_argument("--allow-block-drift", action="store_true",
                    help="允许段落块数不同（不推荐，等于放弃规则 1 的机械校验）")
    ap.add_argument("--float-reflow", action="store_true",
                    help="浮动对象（图/表/图注/表注）已按正文首次引用重定位："
                         "正文块仍逐块比对，浮动对象改为按多重集合核对")
    args = ap.parse_args(argv)

    with open(args.source, "r", encoding="utf-8") as fh:
        raw_src = strip_frontmatter(fh.read())
        # 源文也可能含并排图块：抽取器把一张图拆成多个面板时，或按
        # <figures> 规范与译文同步整理时。两侧都必须折叠成「一个逻辑图」，
        # 否则源文按面板物理张数计、译文按图块计，图片数会恒差 1。
        n_src_blocks = count_figure_blocks(raw_src)
        src = collapse_figures(raw_src)
    with open(args.target, "r", encoding="utf-8") as fh:
        # The 符号一览 block is added by this workflow and has no counterpart
        # in the source; leaving it in would look like an invented heading plus
        # N invented table rows. A 并排图块 is collapsed to one line so that it
        # counts as one figure, not as an HTML table plus two comments.
        raw_tgt = strip_notation(strip_frontmatter(fh.read()))
        n_fig_blocks = count_figure_blocks(raw_tgt)
        tgt = collapse_figures(raw_tgt)

    hard_fail, soft = [], []

    src_struct = strip_float_lines(src) if args.float_reflow else src
    tgt_struct = strip_float_lines(tgt) if args.float_reflow else tgt
    bsrc, btgt = blocks(src_struct), blocks(tgt_struct)
    label = "正文块级结构（浮动对象位置无关）" if args.float_reflow else "块级结构"
    if args.float_reflow:
        n_src_f = sum(1 for l in src.split("\n") if is_float_line(l))
        n_tgt_f = sum(1 for l in tgt.split("\n") if is_float_line(l))
        print(f"  浮动对象行：源 {n_src_f} 行、译 {n_tgt_f} 行"
              "（位置不参与一一对应，下面单独核对数量/编号/路径）")
    ok, msg = compare_sequence(bsrc, btgt, label)
    if not ok and not args.float_reflow:
        # 若剥掉浮动对象后正文完全一致，说明差异只来自图表搬位置，
        # 不是漏段。明确提示补参数，别让人去改一段本来正确的译文。
        if [x[0] for x in blocks(strip_float_lines(src))] == \
           [x[0] for x in blocks(strip_float_lines(tgt))]:
            print("  ↳ 差异只来自图/表的位置；若已按首次引用重定位，"
                  "请加 --float-reflow 重新校验")
    if not ok and args.allow_block_drift:
        soft.append("【忽略】" + msg)
    elif ok:
        print("✓ " + msg)
    else:
        print("✗ " + msg)
        hard_fail.append(msg)

    for kind, label in (("h", "标题层级"), ("li", "列表项"), ("q", "引用块")):
        ok, msg = compare_detail(bsrc, btgt, kind, label)
        print(("✓ " if ok else "✗ ") + msg)
        if not ok:
            hard_fail.append(msg)

    # table rows and images
    if args.float_reflow:
        # 表行已从块序列里剥离，改用全文计数：搬位置不该让行数变化。
        t_src = sum(1 for l in src.split("\n") if TABLE_LINE.match(l))
        t_tgt = sum(1 for l in tgt.split("\n") if TABLE_LINE.match(l))
    else:
        t_src = sum(1 for x in bsrc if x[0] == "tr")
        t_tgt = sum(1 for x in btgt if x[0] == "tr")
    if t_src == t_tgt:
        print(f"✓ 表格行：{t_src} 行，一致"
              + ("（位置无关）" if args.float_reflow else ""))
    else:
        m = f"表格行：源 {t_src} 行，译 {t_tgt} 行"
        print("✗ " + m)
        hard_fail.append(m)

    im_src, im_tgt = images(src), images(tgt)
    # 两侧都折叠过并排图块后，剩下的裸图路径 + 逻辑图块数 = 逻辑图总数。
    # 这样「源文与译文同步整理成并排块」和「源文一张图、译文合成并排块」
    # 两种情形都能对上，而真的丢图/多图仍会被抓到。
    n_src = len(im_src) + n_src_blocks
    n_tgt = len(im_tgt) + n_fig_blocks
    base = lambda xs: [x.split("/")[-1].split("\\")[-1] for x in xs]
    # 重定位后图片顺序可能变；按多重集合核对比按位置逐个比更正确，
    # 且照样能抓到「丢了一张图」或「换了路径」。
    paths_ok = (sorted(base(im_src)) == sorted(base(im_tgt))) if args.float_reflow \
        else (base(im_src) == base(im_tgt))
    # 任一侧有并排图块时，面板名与原文的单张图对不上是正常的（一张图被
    # 拆成了四块）；面板文件是否存在由 figures.py audit 负责。
    panels = n_src_blocks or n_fig_blocks
    if n_src == n_tgt and (panels or paths_ok):
        tail = (f"，其中源 {n_src_blocks} / 译 {n_fig_blocks} 个并排图块"
                "（面板路径不逐字比对）" if panels else "")
        tail += "（多重集合核对，位置无关）" if args.float_reflow else ""
        print(f"✓ 图片：{n_src} 处，路径一致{tail}")
    elif n_src == n_tgt:
        m = (f"图片：数量一致（源 {n_src} = {len(im_src)} 裸图 + {n_src_blocks} 块，"
             f"译 {n_tgt} = {len(im_tgt)} 裸图 + {n_fig_blocks} 块），"
             f"但路径对不上 {set(base(im_src)) ^ set(base(im_tgt)) or '（顺序不同）'}")
        print("✗ " + m)
        hard_fail.append(m)
    else:
        m = (f"图片：源 {n_src} 处（{len(im_src)} 裸图 + {n_src_blocks} 并排块），"
             f"译 {n_tgt} 处（{len(im_tgt)} 裸图 + {n_fig_blocks} 并排块）；数量不一致")
        print("✗ " + m)
        hard_fail.append(m)

    # 图注/表注编号：重定位最容易丢的就是这一行，单独按多重集合核对
    if args.float_reflow:
        cs, ct = cap_numbers(src), cap_numbers(tgt)
        if sorted(cs) == sorted(ct):
            print(f"✓ 图注/表注编号：{len(ct)} 条，与原文一致（位置无关）")
        else:
            m = f"图注/表注编号：源 {sorted(cs)}，译 {sorted(ct)}"
            print("✗ " + m)
            hard_fail.append(m)

    # citations
    v_src, n_src = citations(src)
    tgt_norm = re.sub(r"\s+", " ", tgt)

    def norm_cite(x):
        """引用比对前先归一标点：全角括号、作者与年份之间的逗号都属体例，
        不是对原文的改写。中文译文常写成 (Campbell, 1998: 140)，源文是
        (Campbell 1998: 140)，逐字符比会全部误报"缺失"。"""
        x = x.replace("（", "(").replace("）", ")").replace("，", ",")
        x = re.sub(r"\s+(?=[,;])", "", x)          # `et al. , 2023` -> `et al., 2023`
        x = re.sub(r"\s+(?=\))", "", x)           # `Theorem 1.11.1 )` -> `Theorem 1.11.1)`
        x = re.sub(r"(?<=[A-Za-z])\s*,\s*(?=\d{4})", " ", x)
        x = re.sub(r"\s+", " ", x).strip()
        # 引用里的"定位语"（Chapters 8–9 / 第 8–9 章 / pp. 12–18）是内容，不是引用
        # 本身：译文把它译成中文不算漏引。比对前把年份之后的部分截掉。
        m = re.search(r"(.*(?:19|20)\d{2}[a-z]?)([^()]*)\)$", x)
        if m and not re.search(r"(?:19|20)\d{2}", m.group(2)):
            x = m.group(1) + ")"
        return x

    # 逐条比对，不能拿 `norm_cite` 去处理整篇：它的"截掉定位语"规则带了
    # `\\)$` 锚点，作用在全文上会从某一年份一路截到文末，把后面所有引用都吃掉。
    tgt_c = [norm_cite(c) for c in citations(tgt)[0]]
    missing = [c for c in v_src if norm_cite(c) not in tgt_c]
    # A narrative citation survives if its year survives; the author name around
    # it may legitimately be transliterated, and the surrounding parentheses may
    # be full-width in Chinese typography.
    missing_n = []
    for c in n_src:
        yr = re.search(r"(?:19|20)\d{2}", c)
        if yr and not re.search(rf"(?<!\d){yr.group(0)}(?!\d)", tgt_norm):
            missing_n.append(c)

    total_cites = len(v_src) + len(n_src)
    if missing or missing_n:
        m = f"引用：源 {total_cites} 条（逐字 {len(v_src)}、叙述式 {len(n_src)}），译文缺失 {len(missing) + len(missing_n)} 条"
        for c in missing:
            m += f"\n    [必须逐字保留] {c}"
        for c in missing_n:
            m += f"\n    [年份缺失] {c}"
        print("✗ " + m)
        hard_fail.append(m)
    else:
        print(f"✓ 引用：源 {total_cites} 条（逐字 {len(v_src)}、叙述式 {len(n_src)}），全部保留")

    # math delimiters
    left_b = len(re.findall(r"(?<!\\)\\\[", strip_code_and_math(src)))
    left_p = len(re.findall(r"(?<!\\)\\\(", strip_code_and_math(src)))
    rem = re.findall(r"(?<!\\)\\\[|(?<!\\)\\\(", strip_code_and_math(tgt))
    if rem:
        m = f"公式：译文中仍有 {len(rem)} 处 \\( 或 \\[ 未改为 $ / $$"
        print("✗ " + m)
        soft.append(m)
    else:
        print(f"✓ 公式定界符：统一（源中 \\[ {left_b} 处、\\( {left_p} 处已处理）")

    # theorem-like environments: a relabelled result changes the claim
    ecs, ect = theorem_counts(src, tgt)
    if ecs or ect:
        pairs = [(en, zh, ecs.get(en, 0), ect.get(zh, 0)) for en, zh in ENV_NAMES.items()]
        diff = [(zh, a, b) for en, zh, a, b in pairs if a != b]
        line_s = "、".join(f"{zh}{a}" for en, zh, a, b in pairs if a)
        line_t = "、".join(f"{zh}{b}" for en, zh, a, b in pairs if b)
        if diff:
            m = (f"定理类环境数量不一致：源 {line_s or '无'} / 译 {line_t or '无'}\n    "
                 + "；".join(f"{zh} 源 {a} → 译 {b}" for zh, a, b in diff))
            print("✗ " + m)
            soft.append(m)
        else:
            print(f"✓ 定理类环境：{line_s}，标签与条数一致")

    # untranslated paragraphs
    sus = []
    for i, p in enumerate(paragraphs(tgt), 1):
        # 作者行（姓名 + <sup>1</sup> 机构编号）整行拉丁字母且没有中文，
        # 不是漏译；跳过，否则几乎每篇论文都要误报一次「整段未译」。
        if "<sup>" in p and not CJK.search(p):
            continue
        # 图片行（`![](images/…)`、`<img src=…>`）天然全是拉丁字母，不是漏译；
        # 致谢、参考文献里的人名也一样。判据要求中文少于 15 字才算"整段没译"。
        # 公式也要先剥掉：证明段里一行可能只有「令 … 与 …，使得 …」几个汉字，
        # 拉丁字母全在公式里，按原样算会一律判成"整段没译"。
        probe = strip_code_and_math(IMAGE.sub(" ", IMG_HTML.sub(" ", p)))
        # 括号里的引用按规则逐字保留，两种语言里都长一样，不能算"没译"的证据。
        probe = re.sub(r"（[^（）]{0,120}）", " ", probe)
        probe = re.sub(r"\([^()]{0,120}\)", " ", probe)
        ratio, total = latin_ratio(probe)
        if total >= 40 and ratio > 0.6 and len(CJK.findall(probe)) < 15:
            sus.append(f"第 {i} 段（拉丁字母占 {ratio:.0%}）：{p[:70]}…")
    if sus:
        m = "疑似未译段落：\n    " + "\n    ".join(sus[:8])
        print("! " + m)
        soft.append(m)
    else:
        print("✓ 未发现整段未译")

    # paragraph length outliers: catches a sentence dropped inside a paragraph
    out = length_outliers(src, tgt, args.float_reflow)
    if out:
        m = "段落长度异常（可能有段内增删）：\n    " + "\n    ".join(out[:8])
        print("! " + m)
        soft.append(m)
    else:
        print("✓ 段落长度分布正常")

    if args.glossary:
        for w in check_glossary(tgt, args.glossary):
            print("! " + w)
            soft.append(w)
        if not soft:
            print("✓ 术语表检查无异常")

    print("\n" + "=" * 50)
    if hard_fail:
        print(f"结论：{len(hard_fail)} 项硬性失败，必须修好再交付。")
    elif soft:
        print(f"结论：机械校验通过，{len(soft)} 项需人工判断。")
    else:
        print("结论：机械校验全部通过。仍需人工通读一遍。")
    if args.strict and hard_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
