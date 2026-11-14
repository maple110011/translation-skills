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
supplied) source terms that were left in English or rendered two ways.

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

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
QUOTE = re.compile(r"^(\s*)>\s?")
TABLE_ROW = re.compile(r"^\s*\|")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
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

# 中文排版惯用全角括号包引用串（（Shaikh 2016: 42）），跟半角是同一条东西。
# 只认半角的话，整篇用全角写的译文会被判「引用全部缺失」——这是误报，不是漏译。
CITE_PAREN = re.compile(
    r"(?:\uFF08|\()[A-Z][^()\uFF08\uFF09]{0,90}?\b(?:19|20)\d{2}[a-z]?\b[^()\uFF08\uFF09]{0,40}?(?:\uFF09|\))")
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


def blocks(text, with_text=False):
    """Flatten the document into an ordered list of structural blocks.

    Yields ``(kind, detail)``; ``detail`` carries what must stay identical
    (heading level, list marker shape, quote depth, image target). Paragraph
    blocks carry an empty detail unless ``with_text`` is set, in which case
    the paragraph body is returned — ``semantic_audit.py`` pairs paragraphs
    by this sequence, so it must be the same definition as the reconcile step.
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
                result.append(("p", body if with_text else ""))
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
    return [m.group(1).strip() for m in IMAGE.finditer(text)]


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


def paragraphs(text):
    """Collect prose paragraphs, skipping code, display math, and structure."""
    out, buf = [], []
    in_fence = in_math = in_bracket = False
    for line in text.split("\n"):
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


def check_glossary(target, path):
    warnings = []
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            src = (r.get("src") or "").strip()
            dst = (r.get("dst") or "").strip()
            alt = (r.get("alt") or "").strip()
            kind = (r.get("kind") or "").strip()
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
            if v in clean and v != dst:
                variants.append(f"{src}：出现异译「{v}」，应为「{dst}」")
    if untranslated:
        warnings.append("疑似未译术语：\n    " + "\n    ".join(untranslated[:15])
                        + (f"\n    …共 {len(untranslated)} 条" if len(untranslated) > 15 else ""))
    if variants:
        warnings.append("术语异译：\n    " + "\n    ".join(variants[:15])
                        + (f"\n    …共 {len(variants)} 条" if len(variants) > 15 else ""))
    return warnings


MARKUP = re.compile(r"</?(?:table|tr|td|th|thead|tbody|img|div|span|figure)\b", re.I)


def length_outliers(src, tgt):
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
    ps, pt = paragraphs(src), paragraphs(tgt)
    if len(ps) != len(pt) or len(ps) < 6:
        return []
    ratios, rows = [], []
    for i, (a, b) in enumerate(zip(ps, pt)):
        if MARKUP.search(a) or MARKUP.search(b) or a.count("|") >= 2 or b.count("|") >= 2:
            continue
        words = len(re.findall(r"[A-Za-z\u00C0-\u024F]+", a))
        chars = len(CJK.findall(b))
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


def check_footnotes(tgt_full, work_dir, skip=False):
    """交付门禁：脚注清单 ↔ 译文 `## 脚注` 节逐条核对。

    MinerU 的 full.md 整类过滤 page_footnote，块级对账查不出来；统一脚本
    footnote_recover.py 负责恢复与补回，这里在交付前再验一次编号、页码、
    链接与是否还有英文待译。两个 skill 用同一实现。
    """
    if skip:
        print("  （已显式跳过脚注核对）")
        return []
    csv_path = os.path.join(work_dir, "脚注.csv")
    if not os.path.isfile(csv_path):
        return ["第 1 步未做脚注恢复：找不到 %s/脚注.csv。先跑 "
                "`python scripts/footnote_recover.py _work/extract -o _work "
                "--source 原文.md --target 译文.md --apply --check`；"
                "确无 MinerU 结果包时显式加 --skip-footnote-check" % work_dir]
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    needed = [r for r in rows if r.get("category") == "footnote"
              and (r.get("marker") or "").isdigit()]
    if not needed:
        print("✓ 脚注核对：清单 0 条需补")
        return []
    m = re.search(r"(?m)^##\s*脚注\s*$(.*?)(?=^##\s|\Z)", tgt_full, re.S)
    if not m:
        return ["译文缺 `## 脚注` 节：清单有 %d 条页底脚注要补，"
                "原文与译文必须同步补回" % len(needed)]
    defs = {mm.group(1): mm.group(2)
            for mm in re.finditer(r"(?m)^\[\^(\w+)\]:\s*(.*)$", m.group(1))}
    out = []
    for r in needed:
        n = r["marker"]
        page = str(r.get("page", ""))
        if n not in defs:
            out.append("译文脚注节缺 `[^%s]:` 定义（第 %s 页）" % (n, page))
            continue
        line = defs[n]
        if page not in line:
            out.append("译文 `[^%s]` 页码不符：应为第 %s 页" % (n, page))
        for u in re.findall(r"https?://[^\s<>'，。；]+", r.get("plain", "")):
            if u not in line:
                out.append("译文 `[^%s]` 丢了链接 %s" % (n, u[:60]))
        if "<!-- 待译" in line or "TODO" in line:
            out.append("译文 `[^%s]` 还是英文待译：填 _work/脚注_待译.csv 的 zh 列后重跑 --apply" % n)
    if re.search(r"<sup>\s*\d", tgt_full):
        out.append("译文仍有字面 `<sup>n</sup>`：交付形态只能是 `[^n]`")
    if out:
        return out
    print("✓ 脚注核对：清单 %d 条需补，译文脚注节 %d 条编号定义；"
          "逐条页码/链接/中文齐备" % (len(needed), len(defs)))
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description="对照原文检查译文的保真度。")
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--glossary", help="术语表 CSV（src,dst[,alt]），可选")
    ap.add_argument("--strict", action="store_true", help="有硬性失败时返回码 1")
    ap.add_argument("--allow-block-drift", action="store_true",
                    help="允许段落块数不同（不推荐，等于放弃规则 1 的机械校验）")
    ap.add_argument("--skip-footnote-check", action="store_true",
                    help="仅在没有 MinerU 结果包（纯 Markdown 输入）时使用：跳过脚注交付门禁")
    args = ap.parse_args(argv)

    with open(args.source, "r", encoding="utf-8") as fh:
        src = strip_frontmatter(fh.read())
    with open(args.target, "r", encoding="utf-8") as fh:
        tgt = strip_frontmatter(fh.read())

    hard_fail, soft = [], []

    work_dir = (os.path.dirname(args.glossary) if args.glossary
                else os.path.join(os.path.dirname(args.target), "_work"))
    fn_fail = check_footnotes(tgt, work_dir, args.skip_footnote_check)
    for m in fn_fail:
        print("✗ " + m)
    hard_fail.extend(fn_fail)

    bsrc, btgt = blocks(src), blocks(tgt)
    ok, msg = compare_sequence(bsrc, btgt, "块级结构")
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
    t_src = sum(1 for x in bsrc if x[0] == "tr")
    t_tgt = sum(1 for x in btgt if x[0] == "tr")
    if t_src == t_tgt:
        print(f"✓ 表格行：{t_src} 行，一致")
    else:
        m = f"表格行：源 {t_src} 行，译 {t_tgt} 行"
        print("✗ " + m)
        hard_fail.append(m)

    im_src, im_tgt = images(src), images(tgt)
    if [x.split("/")[-1] for x in im_src] == [x.split("/")[-1] for x in im_tgt]:
        print(f"✓ 图片：{len(im_src)} 张，路径一致")
    else:
        m = (f"图片：源 {len(im_src)} 张，译 {len(im_tgt)} 张；"
             f"路径不一致 {set(im_src) ^ set(im_tgt) or '（顺序不同）'}")
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
        x = re.sub(r"(?<=[A-Za-z])\s*,\s*(?=\d{4})", " ", x)
        # 引用尾部的著者补注（emphasis added / 着重号为引者所加，translated
        # by…）属译者说明，不是文献标签；译文往往改写而非逐字对应，比中英文
        # 措辞只会误报"必须逐字保留"。比对时剥掉，前面那串著者-年份-页码仍
        # 逐字校验。
        x = re.sub(r",\s*(?:emphasis\s+(?:added|is\s+added)|translation\s+(?:is\s+)?"
                   r"(?:modified|amended)|着重号[^()]{0,12})\s*(?=\))", "", x)
        return re.sub(r"\s+", " ", x).strip()

    tgt_c = norm_cite(tgt_norm)
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

    # untranslated paragraphs
    sus = []
    for i, p in enumerate(paragraphs(tgt), 1):
        ratio, total = latin_ratio(p)
        if total >= 40 and ratio > 0.6:
            sus.append(f"第 {i} 段（拉丁字母占 {ratio:.0%}）：{p[:70]}…")
    if sus:
        m = "疑似未译段落：\n    " + "\n    ".join(sus[:8])
        print("! " + m)
        soft.append(m)
    else:
        print("✓ 未发现整段未译")

    # paragraph length outliers: catches a sentence dropped inside a paragraph
    out = length_outliers(src, tgt)
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
