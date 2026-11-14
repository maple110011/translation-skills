#!/usr/bin/env python3
"""Mine candidate terms from an English source document.

Why a script
------------
Terminology consistency fails in a predictable way: the translator decides a
rendering on page 2 and forgets it by page 20. The fix is to decide *before*
translating, which means having a candidate list first. Reading a 40-page paper
looking for terms is slow and unreliable; counting n-grams is neither.

This script does not translate and does not guess renderings. It produces a
short list of strings that behave like terms, marks the ones already covered by
the glossary, and leaves the deciding to the translator.

What counts as term-like
------------------------
* repeated noun phrases (n-grams whose edges are content words)
* words the author emphasises with *italics* or "quotes"
* `the X of Y` constructions, which in this literature are almost always terms
* morphological markers: -ism, -ization, -ation, -tion, -ness, -ity
* capitalised names not already in the glossary (for consistency, not translation)

Usage
-----
    python extract_terms.py paper_en.md -o _work/
    python extract_terms.py paper_en.md -o _work/ --min-count 3 --top 120
    python extract_terms.py paper_en.md -o _work/ --write-project _work/proj.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

STOP = set("""
a an the and or but if then than that this these those of in on at to for from by with
without within into onto upon about above below over under between among through during
before after since until while as is are was were be been being am do does did doing have
has had having will would shall should can could may might must not no nor so such very
more most much many few less least other another same own only just also both each either
neither all any some none one two three four five six seven eight nine ten first second
it its they them their we us our you your he him his she her i me my who whom whose which
what when where why how there here thus hence therefore however moreover furthermore
because although though unless whereas whether both per via etc ibid cf p pp vol no ed eds
""".split())

# Words that appear everywhere in academic prose and carry no terminological weight
# on their own. A candidate made only of these is discarded.
GENERIC = set("""
study studies paper article chapter book work works argument approach analysis analyses
result results finding findings evidence data case cases point points question questions
issue issues problem problems view views sense term terms word words way ways part parts
time times year years number numbers example examples fact facts idea ideas notion notion
account accounts model models theory theories concept concepts process processes system
systems form forms kind kinds type types level levels group groups role roles effect
effects change changes development developments increase decrease growth rise decline
""".split())

VERB = set("""is are was were be been being am has have had do does did can could
will would may might must should shall""".split())

SUFFIX = re.compile(r"(ism|ization|isation|ation|ition|tion|ness|ity|ment|ship|hood)$", re.I)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
TOKEN = re.compile(r"[A-Za-z][A-Za-z\u00C0-\u024F'\u2019\-\u2010-\u2015]*")
ITALIC = re.compile(r"(?<!\*)\*([^*\n]{3,60})\*(?!\*)")
QUOTE = re.compile(r"[\"“]([^\"”\n]{3,60})[\"”]")
THE_OF = re.compile(r"\bthe\s+([a-z][a-z\- ]{2,40}?)\s+of\b", re.I)
CITE_PAREN = re.compile(r"\([A-Z][^()]{0,90}?\b(?:19|20)\d{2}[a-z]?\b[^()]{0,40}?\)")
CITE_BRACKET = re.compile(r"\[\d+(?:\s*[,–\-]\s*\d+)*\]")
CITE_NARR = re.compile(r"\b[A-Z][A-Za-z\u00C0-\u024F'’\-]+(?:\s+(?:et al\.?|and|&)\s+"
                       r"[A-Za-z\u00C0-\u024F'’\-]+)?\s*\((?:19|20)\d{2}[a-z]?\)")


def clean(text):
    """Strip everything that would pollute term counts."""
    out, fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            fence = not fence
            continue
        if fence:
            continue
        out.append(line)
    t = "\n".join(out)
    t = re.sub(r"\$\$.+?\$\$", " ", t, flags=re.S)
    t = re.sub(r"\\\[.+?\\\]", " ", t, flags=re.S)
    t = re.sub(r"(?<!\\)\$.+?(?<!\\)\$", " ", t, flags=re.S)
    t = re.sub(r"\\\(.+?\\\)", " ", t, flags=re.S)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^{}]*\})?", " ", t)   # \mathrm{ln}, \text{...}
    t = re.sub(r"[{}]", " ", t)
    t = re.sub(r"`[^`\n]*`", " ", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    for rx in (CITE_PAREN, CITE_BRACKET, CITE_NARR):
        t = rx.sub(" ", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"[*_]{1,3}", "", t)
    return t


def norms(tok):
    return tok.lower().replace("\u2019", "'").strip("'-")


def candidates(text, max_n=4):
    """Count n-grams whose first and last tokens are content words."""
    counts = Counter()
    for line in text.split("\n"):
        toks = TOKEN.findall(line)
        if not toks:
            continue
        for i in range(len(toks)):
            for n in range(1, max_n + 1):
                span = toks[i:i + n]
                if len(span) < n:
                    break
                first, last = norms(span[0]), norms(span[-1])
                if not first or not last:
                    break
                if first in STOP or last in STOP:
                    continue          # a phrase must start and end on a content word
                inner = [norms(t) for t in span]
                if all(t in STOP or t in GENERIC for t in inner):
                    continue
                if any(t in ("and", "or", "vs", "versus") for t in inner):
                    continue      # a conjunction makes a phrase, not a term
                if any(t in VERB for t in inner):
                    continue      # "the system is stable" is a clause, not a term
                if max(len(t) for t in inner) < 4:
                    continue
                phrase = " ".join(inner)
                if len(phrase) < 4:
                    continue
                counts[phrase] += 1
    return counts


def signals_for(phrase, text):
    sig = []
    if re.search(rf"(?<!\*)\*\s*{re.escape(phrase)}\s*\*(?!\*)", text, re.I):
        sig.append("italic")
    if re.search(rf"[\"“]\s*{re.escape(phrase)}\s*[\"”]", text, re.I):
        sig.append("quoted")
    if SUFFIX.search(phrase.split()[-1]):
        sig.append("suffix")
    if re.search(rf"\bthe\s+{re.escape(phrase)}\s+of\b", text, re.I):
        sig.append("the_of")
    return sig


def load_known(paths):
    known = {}
    for p in paths or []:
        files = [p] if os.path.isfile(p) else [
            os.path.join(p, n) for n in sorted(os.listdir(p)) if n.endswith(".csv")]
        for f in files:
            try:
                with open(f, "r", encoding="utf-8-sig", newline="") as fh:
                    for r in csv.DictReader(fh):
                        s = (r.get("src") or "").strip()
                        d = (r.get("dst") or "").strip()
                        if s and d:
                            known.setdefault(s.lower(), (d, os.path.basename(f)))
            except (OSError, UnicodeDecodeError, csv.Error):
                continue
    return known


def cap_names(text, min_count):
    """Capitalised tokens that look like surnames, ignoring sentence starts."""
    counts = Counter()
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z\u00C0-\u024F]{2,})\b",
                         text, re.M):
        counts[m.group(1)] += 1
    return {k: v for k, v in counts.items() if v >= min_count}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="从英文原文挖掘候选术语，标注已有译法，供翻译前锁定术语。")
    ap.add_argument("source", help="英文 Markdown 原文")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--glossary", "-g", nargs="*", default=None,
                    help="已有术语表（文件或目录），用于标注 known")
    ap.add_argument("--min-count", type=int, default=2, help="最低出现次数（默认 2）")
    ap.add_argument("--top", type=int, default=150, help="输出前 N 条（默认 150）")
    ap.add_argument("--max-n", type=int, default=4, help="最长短语词数（默认 4）")
    ap.add_argument("--allow-single", action="store_true",
                    help="也输出单词候选（默认只保留被强调的单词）")
    ap.add_argument("--write-project", default=None,
                    help="额外写一份项目术语表模板（dst 留空待填）")
    args = ap.parse_args(argv)

    with open(args.source, "r", encoding="utf-8") as fh:
        raw = fh.read()
    text = clean(raw)
    if len(text) < 500:
        sys.exit("清洗后正文过短，检查输入是否为可读的 Markdown。")

    known = load_known(args.glossary)
    counts = candidates(text, args.max_n)

    # Suppress fragments: if a phrase is a contiguous part of a longer phrase
    # that occurs nearly as often, the short one is a piece of the long one,
    # not a term of its own ("production function" inside "aggregate production
    # function", "douglas" inside "cobb-douglas").
    kept = {p: n for p, n in counts.items() if n >= args.min_count}
    # Fold plurals into the singular so "production functions" does not compete
    # with "production function" for the same glossary row.
    for phrase in list(kept):
        if phrase.endswith("s") and len(phrase) > 5:
            singular = phrase[:-1]
            if singular in kept:
                kept[singular] += kept.pop(phrase)
        if phrase.endswith("ies"):
            singular = phrase[:-3] + "y"
            if singular in kept:
                kept[singular] += kept.pop(phrase)
    tokenised = {p: tuple(p.split()) for p in kept}
    drop = set()
    for phrase, toks in tokenised.items():
        for size in range(1, len(toks)):
            for start in range(0, len(toks) - size + 1):
                sub = toks[start:start + size]
                sub_p = " ".join(sub)
                if sub_p in kept and kept[sub_p] <= kept[phrase] / 0.55:
                    drop.add(sub_p)
    rows = []
    for phrase, n in kept.items():
        if phrase in drop:
            continue
        sig = signals_for(phrase, text)
        if " " not in phrase and not args.allow_single \
                and not ("quoted" in sig or "italic" in sig):
            continue          # a bare word is a component, not a term
        score = n * (1 + 0.35 * (phrase.count(" "))) \
            + 3 * sig.count("quoted") + 3 * sig.count("italic") \
            + 2 * sig.count("suffix") + 1 * sig.count("the_of")
        hit = known.get(phrase)
        rows.append({
            "type": "term",
            "src": phrase,
            "count": n,
            "score": round(score, 1),
            "signals": ";".join(sig),
            "status": "known" if hit else "new",
            "existing_dst": hit[0] if hit else "",
            # 种子表里查不到既有译法的候选，默认保留英文原文（kind=keep）。
            # 这不是替译者做判断，而是把"边译边造词"的入口堵住：有依据才改。
            "keep_default": "no" if hit else "yes",
        })

    for name, n in cap_names(text, args.min_count).items():
        key = name.lower()
        if any(key in r["src"] for r in rows):
            continue
        hit = known.get(key)
        rows.append({
            "type": "name", "src": name, "count": n,
            "score": round(n * 0.8, 1), "signals": "capitalised",
            "status": "known" if hit else "new",
            "existing_dst": hit[0] if hit else "",
            "keep_default": "no",   # 专名走 kind=name，不进保留英文术语表
        })

    rows.sort(key=lambda r: (-r["score"], r["src"]))
    rows = rows[:args.top]

    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.source))[0]
    out = os.path.join(args.outdir, f"{stem}_候选术语.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "type", "src", "count", "score", "signals", "status",
            "existing_dst", "keep_default"])
        w.writeheader()
        w.writerows(rows)

    if args.write_project:
        new = [r for r in rows if r["status"] == "new" and r["type"] == "term"]
        path = args.write_project
        header = ["src", "dst", "alt", "kind", "status", "note"]
        exists = os.path.isfile(path)
        if exists:
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                first = fh.readline()
            cols = [c.strip() for c in first.split(",")] if first else header
        else:
            cols = header
        wide = "kind" in cols
        with open(path, "a" if exists else "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            if not exists:
                w.writerow(cols)
            for r in new:
                if wide:
                    w.writerow([r["src"], "@keep", "", "keep", "已定",
                                "种子表无既有译法，默认保留英文原文"])
                else:
                    w.writerow([r["src"], "@keep", "默认保留英文原文（kind=keep）"])

    terms_new = [r for r in rows if r["type"] == "term" and r["status"] == "new"]
    terms_known = [r for r in rows if r["type"] == "term" and r["status"] == "known"]
    names_new = [r for r in rows if r["type"] == "name" and r["status"] == "new"]

    print(f"原文：{args.source}")
    print(f"  候选术语 {len(terms_new) + len(terms_known)} 条"
          f"（已收录 {len(terms_known)}，新增 {len(terms_new)}）")
    print(f"  未收录专名 {len(names_new)} 条")
    print("\n最值得先定的 20 条（新增）：")
    for r in terms_new[:20]:
        sig = f"  [{r['signals']}]" if r["signals"] else ""
        print(f"  {r['count']:>3}×  {r['src']}{sig}")
    if names_new:
        print("\n未收录专名示例：" + "、".join(r["src"] for r in names_new[:10]))
    print(f"\n已写出：{out}")
    if args.write_project:
        print(f"项目术语表模板：{args.write_project}（新增术语已预填 @keep）")
    keep_n = sum(1 for r in rows if r.get("keep_default") == "yes")
    print(f"\n新增候选中 {keep_n} 条标记为 keep_default=yes：种子表查不到既有译法，"
          "默认保留英文原文、不造中文词。")
    print("下一步：逐条核对——查到权威译名的改 dst；其余保持 @keep，"
          "抄进译文开头的「保留英文术语一览」。不要边译边定。")


if __name__ == "__main__":
    main()
