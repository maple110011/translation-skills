#!/usr/bin/env python3
"""Mine term pairs from aligned source/translation documents.

Why this exists
---------------
A glossary built from frequency alone records how a word *could* be translated.
A glossary built from a translator's own finished work records how it *was*
translated. The second kind is evidence; the first is a guess with a number
attached.

Alignment
---------
Paragraph counts never match across a pair — translations drop reference lists,
figure captions and table markup — so alignment uses numerals instead. Years,
percentages and page numbers keep their order on both sides and survive
translation unchanged. An LCS over the two numeral sequences yields anchors;
sentences between two anchors are paired by relative position. This is the
Gale-Church idea with numerals as the anchor type, which works because these
texts are dense with citations and figures.

What it produces, and what it does not
--------------------------------------
Chinese has no word delimiter, and character n-grams cannot settle a boundary:
`劳动过程理论` legitimately yields `程理论`. The output is therefore a ranked
list of candidates *with a bilingual snippet for each*, meant to be read and
corrected. `dst` is a proposal; the evidence column is the basis for accepting
or rejecting it. This script is the recall stage, not the decision stage.

Usage
-----
    python mine_terms_from_pairs.py --pairs pairs.csv -o _work
    python mine_terms_from_pairs.py --auto -o _work --min-count 4
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

CJK = re.compile(r"[\u4e00-\u9fff]")
NUM = re.compile(r"\d+(?:[.,]\d+)*%?")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z\u00C0-\u024F'\u2019\-]*")

# Function characters never occur inside a term, so any n-gram containing one
# is discarded. This substitutes for Chinese word segmentation, which we cannot
# do without a dictionary — and does not need: terms are short and dense.
# A term never starts or ends with one of these, but they occur freely inside
# real terms: `过程`, `时间`, `所有制`, `有效需求`, `等价交换`. Filtering on
# interior characters as well is what makes `劳动过程` disappear.
FUNC_EDGE = set("的了着过是在和与及或也都就而但其这那个被把向于将很更最又再还只仅"
                "并不没无此该些每各某们我你他她它之然而并")

# Discourse markers that co-occur with terms without being terms.
ZH_JUNK = set("""即使 甚至 然而 因此 所以 但是 而且 并且 或者 由于 以及 他们 我们 这些 那些
这种 那种 一个 不是 没有 已经 正在 如果 因为 虽然 而是 就是 也是 都是 可能 可以 需要
应该 必须 常常 往往 通常 一般 例如 比如 包括 通过 对于 关于 根据 按照 不同 各种 一些
许多 大量 主要 重要 基本 具体 实际 相关 相应 以上 以下 之间 之后 之前 之中 之内 之外
一方面 另一方面 与此同时""".split())

MEDIAL = {"of", "for", "to", "in", "on"}

EN_STOP = set("""
a an the and or but if then than that this these those of in on at to for from by with
without within into onto upon about above below over under between among through during
before after since until while as is are was were be been being am do does did doing have
has had having will would shall should can could may might must not no nor so such very
more most much many few less least other another same own only just also both each either
neither all any some none one two three four five six seven eight nine ten first second
it its they them their we us our you your he him his she her i me my who whom whose which
what when where why how there here thus hence therefore however moreover furthermore
because although though unless whereas whether per via etc ibid cf p pp vol no ed eds
even given rather quite still yet already almost often usually always never just
thing things way ways part parts fact facts case cases point points kind kinds sort sorts
""".split())

# Sentence-level indexes are shared with evidence() and divergence().
ZH_S: list = []
EN_S: list = []
ZH_IDX: list = []


def read(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def sentences(text):
    parts = re.split(r"(?<=[。！？；])|(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and len(p.strip()) > 12]


def numerals(seq):
    return [NUM.findall(s) for s in seq]


def lcs_pairs(a, b):
    """LCS over (value, position) tuples; returns index pairs into the lists."""
    n, m = len(a), len(b)
    if not n or not m:
        return []
    if n * m > 4_000_000:          # keep the table bounded
        step = int((n * m / 4_000_000) ** 0.5) + 1
        a, b = a[::step], b[::step]
        n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        row, nxt, ai = dp[i], dp[i + 1], a[i][0]
        for j in range(m):
            nxt[j + 1] = row[j] + 1 if ai == b[j][0] else max(nxt[j], row[j + 1])
    out, i, j = [], n, m
    while i > 0 and j > 0:
        if a[i - 1][0] == b[j - 1][0]:
            out.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return out[::-1]


def align(src_text, tgt_text):
    """Return sentence-level (source, target) pairs plus alignment stats."""
    ss, ts = sentences(src_text), sentences(tgt_text)
    a = [(v[0], i) for i, v in enumerate(numerals(ss)) if v]
    b = [(v[0], i) for i, v in enumerate(numerals(ts)) if v]
    pairs = lcs_pairs(a, b)
    if len(pairs) < 5:
        return [], len(ss), len(ts), len(pairs)

    anchors = [(a[i][1], b[j][1]) for i, j in pairs]
    clean = [anchors[0]]
    for p in anchors[1:]:
        if p != clean[-1]:
            clean.append(p)

    out = []
    prev_s, prev_t = 0, 0
    for s_i, t_i in clean[1:] + [(len(ss), len(ts))]:
        en_seg = ss[prev_s:s_i]
        zh_seg = ts[prev_t:t_i]
        if en_seg and zh_seg:
            # Pair by relative position inside the anchor interval. Intervals
            # hold one to three sentences, so this is near 1:1 in practice.
            for k, e in enumerate(en_seg):
                j = min(len(zh_seg) - 1, int(k * len(zh_seg) / len(en_seg)))
                out.append((e, zh_seg[j]))
        prev_s, prev_t = s_i, t_i
    return out, len(ss), len(ts), len(pairs)


KEEP_PLURAL = {"means", "goods", "economics", "politics", "series", "species", "works", "services"}


def singular(t):
    """Fold plurals so `labour processes` counts towards `labour process`.

    Without this, a term used mostly in the plural looks rare: the singular and
    the plural compete for the same glossary row and neither clears the floor.
    Irregular `means` and `goods` are left alone — `mean of production` is not a
    term and `good` is a different word.
    """
    if t in KEEP_PLURAL:
        return t
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if t.endswith(("ses", "xes", "zes", "ches", "shes")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is", "as", "os")):
        return t[:-1]
    return t


def en_ngrams(text, max_n=3):
    toks = [singular(w.lower().strip("'-")) for w in LATIN_WORD.findall(text)]
    out = set()
    for i in range(len(toks)):
        for n in range(1, max_n + 1):
            span = toks[i:i + n]
            if len(span) < n:
                break
            if span[0] in EN_STOP or span[-1] in EN_STOP:
                continue
            # `rate of profit` is the standard shape of a term here, so a medial
            # preposition must not disqualify a phrase.
            if any(t in EN_STOP and t not in MEDIAL for t in span[1:-1]):
                continue
            if all(len(t) < 4 for t in span):
                continue
            out.add(" ".join(span))
    return out


def zh_ngrams(text, lo=2, hi=8):
    """Character n-grams inside a run of Chinese, never across a break.

    Deleting non-Chinese characters rather than splitting on them welds `第3节`
    into `第节` and `古典（classical）政治经济学` into a fake compound. Runs keep
    the boundaries the original text actually had.
    """
    out = set()
    for s in re.findall(r"[\u4e00-\u9fff]+", text):
        for n in range(lo, hi + 1):
            for i in range(len(s) - n + 1):
                g = s[i:i + n]
                if g[0] in FUNC_EDGE or g[-1] in FUNC_EDGE:
                    continue
                out.add(g)
    return out


def nesting_trim(cand, min_c=3, cap=8):
    """Drop a fragment when a longer containing string keeps its support.

    Dice alone prefers rare substrings — `余价值` scores above `剩余价值` because
    it is less common overall, so the denominator is smaller.
    """
    keep = {g: c for g, c in cand.items() if c >= min_c and len(g) <= cap}
    drop = set()
    for g in keep:
        for h in keep:
            if len(h) > len(g) and g in h and keep[h] >= keep[g] * 0.9:
                drop.add(g)
                break
    return {g: c for g, c in keep.items() if g not in drop}


def load_known(paths):
    known = {}
    for p in paths or []:
        files = ([p] if os.path.isfile(p) else
                 [os.path.join(p, n) for n in sorted(os.listdir(p)) if n.endswith(".csv")])
        for f in files:
            try:
                with open(f, encoding="utf-8-sig", newline="") as fh:
                    for r in csv.DictReader(fh):
                        s = (r.get("src") or "").strip().lower()
                        if s:
                            known.setdefault(s, (r.get("dst") or "").strip())
            except (OSError, csv.Error):
                continue
    return known


def evidence(pos, dst, width=60):
    for pi in sorted(pos, key=lambda p: -ZH_S[p].count(dst)):
        if dst in ZH_S[pi]:
            z = ZH_S[pi]
            k = z.find(dst)
            z = z[max(0, k - width): k + len(dst) + width]
            return f"{EN_S[pi][:width * 2]}  ‖  {z}"
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="从对齐的中英文档对挖掘实证术语表")
    ap.add_argument("--pairs", help="CSV：zh_path,en_path（每行一对）")
    ap.add_argument("--auto", action="store_true", help="从 MinerU输出 + 译介存档 自动配对")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--min-count", type=int, default=4, help="英文候选最低出现句数")
    ap.add_argument("--min-score", type=float, default=0.90,
                    help="最低关联分（P(中文|英文)×逆频率）")
    ap.add_argument("--max-n", type=int, default=3, help="英文候选最长词数")
    ap.add_argument("--max-zh", type=int, default=8, help="中文候选最长字数")
    ap.add_argument("--top", type=int, default=0, help="只输出前 N 条（0 为全部）")
    ap.add_argument("--known", nargs="*", default=None, help="已有术语表，用于补足低频核心词")
    args = ap.parse_args(argv)

    pairs = auto_pairs() if args.auto else read_pairs(args.pairs)
    if not pairs:
        sys.exit("没有可用文档对。检查 --pairs 或 --auto 的路径。")

    doc_of = []
    stats = []
    doc_names = []
    for di, (zp, ep) in enumerate(pairs):
        doc_names.append(os.path.basename(zp).replace(".md", ""))
        aligned, ns, nt, na = align(read(ep), read(zp))
        stats.append((os.path.basename(zp), ns, nt, na, len(aligned)))
        for e, z in aligned:
            EN_S.append(e)
            ZH_S.append(z)
            doc_of.append(di)
    print(f"文档对 {len(pairs)}，对齐句对 {len(EN_S)}")
    for name, ns, nt, na, nc in stats:
        flag = "" if nc > ns * 0.25 else "  ← 锚点过少，该篇质量可疑"
        print(f"  {name[:38]:40} 原{ns:>4}句 译{nt:>4}句 锚{na:>4} 句对{nc:>4}{flag}")

    for s in ZH_S:
        ZH_IDX.append(zh_ngrams(s))
    zh_df = Counter()
    for s in ZH_IDX:
        zh_df.update(s)

    term_pos = defaultdict(set)
    for i, s in enumerate(EN_S):
        for t in en_ngrams(s, args.max_n):
            term_pos[t].add(i)

    known = load_known(args.known)

    rows = []
    for term, pos in term_pos.items():
        n = len(pos)
        if n < args.min_count and term not in known:
            continue
        cand = Counter()
        for pi in pos:
            cand.update(g for g in ZH_IDX[pi] if zh_df[g] >= 3)
        if not cand:
            continue
        cand = nesting_trim(cand, min_c=max(2, min(8, n // 10)), cap=args.max_zh)
        scored = []
        for g, c in cand.items():
            if g in ZH_JUNK:
                continue
            sc = association(c, n, zh_df[g], len(EN_S))
            if sc >= args.min_score:
                scored.append((round(sc, 2), c, g))
        if not scored:
            continue
        scored.sort(key=lambda x: (-x[0], -x[1]))
        best = head_word(term, scored)
        grown = extend(best[2], pos)
        if grown != best[2] and grown in cand:
            best = (best[0], cand[grown], grown)
        rows.append({
            "src": term, "dst": best[2], "count": n, "dice": best[0],
            "docs": len({doc_of[p] for p in pos}),
            "alt": " | ".join(f"{g}({c})" for _, c, g in scored[1:4]),
            "pos": pos, "scored": scored[:4], "doc": doc_of,
        })

    rows.sort(key=lambda r: (-r["count"], -r["dice"]))
    if args.top:
        rows = rows[:args.top]

    os.makedirs(args.outdir, exist_ok=True)
    out = os.path.join(args.outdir, "实证术语表.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "dst", "count", "dice", "docs", "alt", "status",
                    "doc_split", "evidence"])
        for r in rows:
            w.writerow([r["src"], r["dst"], r["count"], r["dice"], r["docs"], r["alt"],
                        status(r), doc_split(r, doc_names),
                        evidence(r["pos"], r["dst"])])

    write_divergence(rows, doc_names, os.path.join(args.outdir, "分歧明细.csv"))
    n_div = sum(1 for r in rows if status(r) != "一致")
    print(f"\n候选术语 {len(rows)} 条，其中分歧/低频 {n_div} 条")
    print(f"已写出：{out}")
    return rows


def extend(g, pos, max_rounds=2):
    """Grow a candidate to the string actually written, one character at a time.

    Character n-grams truncate: `古典政治经济学` shows up as `典政治经济学`, and
    `商品束` as `品束`. When one neighbouring character is present in most of the
    occurrences and the longer string keeps its support, it is part of the term.
    """
    text = "\x00".join(ZH_S[pi] for pi in pos)
    cur = g
    for _ in range(max_rounds):
        base = text.count(cur)
        if base < 2:
            break
        for side in ("left", "right"):
            chars = Counter()
            start = 0
            while True:
                i = text.find(cur, start)
                if i < 0:
                    break
                j = i - 1 if side == "left" else i + len(cur)
                if 0 <= j < len(text) and CJK.match(text[j]) \
                        and text[j] not in FUNC_EDGE:
                    chars[text[j]] += 1
                start = i + 1
            if not chars:
                continue
            ch, c = chars.most_common(1)[0]
            if c / base < 0.6:
                continue
            cand = ch + cur if side == "left" else cur + ch
            if len(cand) > 10:
                continue
            if text.count(cand) >= base * 0.9:
                cur = cand
                break
    return cur


def association(c, n, df, total):
    """P(rendering | term) weighted by how specific the rendering is.

    Dice under-scores a correct rendering when the translation paraphrases:
    `labour process` turns up as `劳动过程` in 20 of 44 sentences, which Dice
    reads as weak because `劳动过程` also occurs elsewhere. Conditional
    probability is the right question — when the term appears, does this string
    appear — and the inverse frequency keeps generic strings from winning.
    """
    import math
    return (c / n) * (1 + math.log((total + 1) / (df + 1)))


def head_word(term, scored):
    """Prefer the head rendering over a compound that happens to co-occur more.

    `profit` surfaces as `利润率` because the text says `profit rate` constantly;
    the head is `利润`. For a single-word source the shorter rendering is the
    head; for a phrase the longer one is the full term (`surplus value` is
    `剩余价值`, not `剩余`). Candidates within 15% of the top score are treated
    as tied before this rule applies.
    """
    top = scored[0][0]
    pool = [s for s in scored if s[0] >= top * 0.85]
    if len(term.split()) == 1:
        pool.sort(key=lambda x: (len(x[2]), -x[0]))
    else:
        pool.sort(key=lambda x: (-len(x[2]), -x[0]))
    return pool[0]


def doc_split(r, doc_names, limit=3):
    """Per-document counts for the top renderings, so a real split is visible."""
    per_doc = defaultdict(Counter)
    for pi in r["pos"]:
        for _, _, g in r["scored"][:limit]:
            if g in ZH_IDX[pi]:
                per_doc[r["doc"][pi]][g] += 1
    parts = []
    for doc, cnt in sorted(per_doc.items(), key=lambda kv: -sum(kv[1].values())):
        if sum(cnt.values()) < 3:
            continue
        cell = "/".join(f"{g}×{c}" for g, c in cnt.most_common(limit))
        parts.append(f"{doc_names[doc][:18]}:{cell}")
    return " ; ".join(parts[:6])


def write_divergence(rows, doc_names, path):
    """List every term a document rendered differently, with the split by source.

    This is the part that matters: a glossary can record one rendering, but the
    translator needs to know they used another one somewhere, and where.
    """
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "主译法", "另译", "分歧篇目", "总次数"])
        for r in rows:
            per_doc = defaultdict(Counter)
            for pi in r["pos"]:
                for _, _, g in r["scored"]:
                    if g in ZH_IDX[pi]:
                        per_doc[r["doc"][pi]][g] += 1
            stray = []
            for doc, cnt in per_doc.items():
                total = sum(cnt.values())
                if total < 5:
                    continue
                for g, c in cnt.items():
                    if g != r["dst"] and c / total >= 0.4:
                        stray.append(f"{g}×{c}（{doc_names[doc][:26]}）")
            if stray:
                w.writerow([r["src"], r["dst"], " | ".join(stray), len(per_doc), r["count"]])


def status(r):
    """Flag a rendering that a single document preferred against the others."""
    if r["count"] < 4:
        return "低频"
    top = r["dst"]
    per_doc = defaultdict(Counter)
    for pi in r["pos"]:
        for _, _, g in r["scored"]:
            if g in ZH_IDX[pi]:
                per_doc[r["doc"][pi]][g] += 1
    for doc, cnt in per_doc.items():
        total = sum(cnt.values())
        if total < 5:
            continue
        for g, c in cnt.items():
            if g != top and c / total >= 0.4:
                return f"分歧:{g}"
    return "一致"


def read_pairs(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.reader(fh):
            if len(r) >= 2 and os.path.exists(r[0]) and os.path.exists(r[1]):
                out.append((r[0], r[1]))
    return out


def auto_pairs():
    """Pair 译介存档 translations with MinerU outputs by surname overlap."""
    import glob

    SUR = re.compile(r"\b([A-Z][a-z]{2,15})\b")

    def surs(t):
        t = re.sub(r"\((?:19|20)\d{2}[a-z]?\)", " ", t)
        return {w for w in SUR.findall(t) if len(w) > 3}

    pool = []
    for d in glob.glob("MinerU输出/*/"):
        md = os.path.join(d, "full.md")
        if os.path.exists(md):
            pool.append((md, surs(read(md)[:600000])))
    out = []
    for f in sorted(os.listdir("译介存档")):
        if not f.endswith(".md") or f.startswith("_"):
            continue
        p = os.path.join("译介存档", f)
        ts = surs(read(p))
        if len(ts) < 8:
            continue
        md, cs = max(pool, key=lambda x: len(ts & x[1]))
        if len(ts & cs) / len(ts) > 0.55:
            out.append((p, md))
    return out


if __name__ == "__main__":
    main()
