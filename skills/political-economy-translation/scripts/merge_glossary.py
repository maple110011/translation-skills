#!/usr/bin/env python3
"""Merge many `src,dst` glossary CSVs into one de-duplicated master table,
flag conflicting translations, and emit a human review sheet.

The glossaries produced by machine translation tools are usually *flat*
name/term pairs accumulated paper by paper, with the same entity translated
several ways across files. This script answers two questions:

1. What is the single canonical translation for each source string?
2. Which entries are still contested and therefore need a human decision?

Only the standard library is required.

Usage
-----
    python merge_glossary.py <dir-or-csv> [<dir-or-csv> ...] -o <outdir>
        [--min-count N] [--no-markdown] [--keep-kind term|name|place|other]

Outputs (in <outdir>)
---------------------
    glossary_master.csv     one row per canonical entry, with variants + counts
    glossary_conflicts.csv  only the entries with >=2 competing translations
    glossary_review.md      Markdown review sheet, conflicts first
    merge_report.txt        console summary, saved for the record
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

# --------------------------------------------------------------------------
# Column aliases: the same pair of columns has been labelled many ways.
# --------------------------------------------------------------------------
SRC_ALIASES = {"src", "source", "original", "term", "en", "english", "原文", "原词", "英文"}
DST_ALIASES = {"dst", "dest", "target", "translation", "zh", "cn", "中文", "译文", "译名"}

# Words that make a source string look like a concept rather than a name.
# Used only to attach a *hint* to each row; never used to drop data.
CONCEPT_HINTS = {
    "value", "labour", "labor", "capital", "surplus", "profit", "wage", "rent",
    "commodity", "production", "productive", "unproductive", "exploitation",
    "accumulation", "circulation", "turnover", "organic composition",
    "abstract", "concrete", "use-value", "exchange-value", "means of production",
    "relations of production", "forces of production", "mode of production",
    "division of labour", "labor process", "labour process", "valorization",
    "realization", "primitive accumulation", "tendency of the rate of profit",
    "transformation problem", "socially necessary labour time", "dead labour",
    "living labour", "variable capital", "constant capital", "fixed capital",
    "circulating capital", "fictitious capital", "finance capital",
    "financialization", "global value chain", "value chain", "precarity",
    "precarious", "informalization", "neoliberalism", "fordism", "post-fordism",
    "regulation school", "social structure of accumulation", "long wave",
    "monopoly capital", "class struggle", "labour aristocracy",
    "skilled", "deskilling", "Taylorism", "scientific management",
}

PLACE_SUFFIXES = ("州", "市", "省", "国", "岛", "湾", "郡", "区", "港", "大学", "学院")

_INITIALS = re.compile(r"^(?:[A-Za-z]\.\s*)+$")
_HAS_PERIOD = re.compile(r"(?:^|\s)[A-Za-z]\.(?:\s|$)")

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LAT_TOKEN = re.compile(r"^(?:[A-Za-z]\.?)+$")
NAME_SEP = re.compile(r"\s*[·,，、]\s*")
# A combining mark stranded after a space means the source text was broken
# during extraction: "Dr ̆agulescu" should be "Drăgulescu".
STRANDED_MARK = re.compile(r"\s+([\u0300-\u036f])")


def normalize_name(dst):
    """Drop Latin initials from a Chinese rendering, returning (value, changed).

    Chinese academic prose refers to `Marx`, not `K. Marx`. Machine translation
    tools, however, emit `马克思·K`, `K. 马克思`, `弗利, D. K.` and half a dozen
    other arrangements for the same person. All of them are the same entry once
    the initials go, and collapsing them is what makes a name table usable —
    it also dissolves most of the "conflicts" that are really just formatting.

    A rendering with no Chinese at all is left alone: `MELT`, `TSSI`, `GVC` are
    abbreviations that must survive, and deciding they are errors is a human
    call, not a regex call.
    """
    if not re.search(r"[A-Za-z]", dst):
        return dst, False
    if not CJK_RE.search(dst):
        return dst, False

    kept = []
    for seg in NAME_SEP.split(dst):
        seg = seg.strip()
        if not seg or not CJK_RE.search(seg):
            continue          # a segment made only of initials carries no name
        tokens = []
        for tok in seg.split():
            if LAT_TOKEN.match(tok):
                continue      # bare initials: "D. K.", "H.D.", "GR"
            tok = re.sub(r"^(?:[A-Za-z]\.?)+", "", tok)   # "K.福利" -> "福利"
            tok = re.sub(r"(?:[A-Za-z]\.?)+$", "", tok)   # "库尔茨 H" -> "库尔茨"
            tok = tok.strip(" .,，·、")
            if tok:
                tokens.append(tok)
        if tokens:
            kept.append(" ".join(tokens))
    if not kept:
        return dst, False
    new = re.sub(r"·{2,}", "·", "·".join(kept)).strip("·")
    return (new, True) if new != dst else (dst, False)


def name_key(s):
    """Matching key that ignores punctuation, case, and initials order.

    ``smith, a.``, ``a. smith`` and ``Smith A`` all collapse to ``("smith","a")``,
    so a verified entry can be found however the extractor happened to write the
    name.
    """
    t = _clean(s).lower().replace("’", "'")
    t = re.sub(r"[.,·，、()]", " ", t)
    initials, words = [], []
    for tok in t.split():
        if len(tok) == 1 and tok.isalpha():
            initials.append(tok)
        elif tok:
            words.append(tok)
    return (" ".join(words), "".join(sorted(initials)))


def clean_src(src):
    """Repair extraction damage in the source string itself."""
    s = STRANDED_MARK.sub(r"\1", src)
    s = s.replace("，", ",").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def load_verified(path):
    """Read verified_names.csv into {name_key: (dst, confidence, basis)}."""
    index = {}
    if not path or not os.path.isfile(path):
        return index
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            dst = (r.get("dst") or "").strip()
            src = (r.get("src") or "").strip()
            if not src or not dst:
                continue
            conf = (r.get("confidence") or "medium").strip()
            basis = (r.get("basis") or "").strip()
            form = (r.get("form") or "surname").strip()
            forms = [src] + [x.strip() for x in (r.get("alias") or "").split("|") if x.strip()]
            for f in forms:
                index[name_key(f)] = (dst, conf, basis, form)
    return index


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _sniff_encoding(path):
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(path, "r", encoding=enc, newline="") as fh:
                fh.read(4096)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8-sig"


def _clean(s):
    """Normalise whitespace and invisible characters without changing meaning."""
    if s is None:
        return ""
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\u00a0", " ")
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip().strip("﻿").strip()


def norm_key(src):
    """Aggressive key used to recognise the *same entity* across files.

    Lowercase, drop a trailing period, drop a leading `the`, collapse spaces.
    Deliberately conservative: it does not strip punctuation inside the string,
    so `marx, k.` and `marx k` stay distinct here and are reported separately
    as *near duplicates* rather than silently merged.
    """
    k = _clean(src).lower()
    k = re.sub(r"^the\s+", "", k)
    k = k.rstrip(" .;:,")
    k = re.sub(r"\s+", " ", k)
    return k


def loose_key(src):
    """Even more aggressive: also drops all punctuation. Used for near-dup report."""
    k = norm_key(src)
    k = re.sub(r"[^\w\u4e00-\u9fff ]", "", k, flags=re.UNICODE)
    return re.sub(r"\s+", " ", k).strip()


def read_csv_pairs(path):
    """Yield (src, dst) pairs from one glossary CSV, tolerating header variants."""
    enc = _sniff_encoding(path)
    with open(path, "r", encoding=enc, newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(fh, dialect)
        rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return
    header = [_clean(c).lower() for c in rows[0]]
    src_i = next((i for i, c in enumerate(header) if c in SRC_ALIASES), None)
    dst_i = next((i for i, c in enumerate(header) if c in DST_ALIASES), None)
    if src_i is None or dst_i is None:
        # No usable header: assume the first two columns are src/dst.
        src_i, dst_i, body = 0, 1, rows
    else:
        body = rows[1:]
    for r in body:
        if len(r) <= max(src_i, dst_i):
            continue
        src, dst = _clean(r[src_i]), _clean(r[dst_i])
        if not src or not dst:
            continue
        if norm_key(src) in SRC_ALIASES or norm_key(dst) in DST_ALIASES:
            continue  # repeated header
        yield src, dst


def collect(paths, normalize=True):
    """Walk directories/files and accumulate observations per normalised key."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith((".csv", ".tsv")):
                    files.append(os.path.join(p, name))
        elif os.path.isfile(p):
            files.append(p)
    if not files:
        sys.exit("没有找到任何 .csv / .tsv 术语表。")

    obs = defaultdict(list)          # norm_key -> [(dst, file, was_normalized)]
    display = {}                     # norm_key -> first-seen original spelling
    per_file = OrderedDict()
    touched = 0
    for f in files:
        n = 0
        for src, dst in read_csv_pairs(f):
            src = clean_src(src)
            changed = False
            if normalize:
                dst, changed = normalize_name(dst)
                if changed:
                    touched += 1
            k = norm_key(src)
            if not k:
                continue
            obs[k].append((dst, os.path.basename(f), changed))
            display.setdefault(k, src)
            n += 1
        per_file[os.path.basename(f)] = n
    return files, obs, display, per_file, touched


# --------------------------------------------------------------------------
# Classification (hint only)
# --------------------------------------------------------------------------
def classify(src, dst):
    """Attach a *hint* about what kind of entry this is.

    The order matters. Concept words are checked first so that a term such as
    `value` is not swallowed by the capitalised-word rule; place suffixes are
    checked before the person-name rule because `剑桥（马萨诸塞州）` contains a
    middle dot nowhere but is obviously a place.
    """
    s, d = src.strip(), dst.strip()
    low = s.lower().strip(" .")
    if low in CONCEPT_HINTS or low.replace("-", " ") in CONCEPT_HINTS:
        return "term"
    if any(suf in d for suf in PLACE_SUFFIXES):
        return "place"
    if "·" in d or "•" in d:
        return "name"
    if _HAS_PERIOD.search(s) or _INITIALS.match(s):
        return "name"
    tokens = [t for t in re.split(r"[\s\-]+", s) if t]
    if tokens and len(tokens) <= 5 and all(
            t[:1].isupper() for t in tokens if t[:1].isalpha()):
        return "name"
    if len(tokens) == 1 and re.fullmatch(r"[A-Z][A-Za-z'\-]+", s):
        return "name"
    if d and not re.search(r"[A-Za-z]", d) and len(tokens) == 1 and s[:1].islower():
        # Single lowercase English word: usually a surname, sometimes a term.
        return "uncertain"
    return "other"


_INITIAL_TAIL = re.compile(r"(?:[·,，]\s*[A-Z]\.?|[A-Z]\.)\s*$")


def flag(src, dst):
    """Mark entries whose *pairing* looks like a machine artefact, not a decision.

    These are the rows a reviewer should open first, independent of whether the
    entry is contested: `marx k -> 马克思·K` is not a translation choice, it is a
    name and an initial glued together by the extractor.
    """
    flags = []
    if _INITIAL_TAIL.search(dst):
        flags.append("initials_merged")
    if re.search(r"[A-Za-z]", dst) and not _INITIAL_TAIL.search(dst):
        flags.append("mixed_latin")
    if len([t for t in re.split(r"\s+", src.strip()) if t]) > 6:
        flags.append("long_src")
    if len(dst) > 30:
        flags.append("long_dst")
    return ";".join(flags)


def pick_best(variants):
    """variants: Counter dst -> count. Prefer frequency, then completeness."""
    ranked = sorted(
        variants.items(),
        key=lambda kv: (-kv[1], -len(kv[0]), kv[0]),
    )
    return ranked[0][0], ranked


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="合并多份术语表 CSV，检测多译法冲突，输出待校对清单。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("inputs", nargs="+", help="术语表目录或 CSV 文件，可多个")
    ap.add_argument("-o", "--outdir", required=True, help="输出目录")
    ap.add_argument("--min-count", type=int, default=1,
                    help="只输出出现次数 >= N 的条目（默认 1，即全部）")
    ap.add_argument("--no-markdown", action="store_true", help="不生成 review.md")
    ap.add_argument("--verified", default=None,
                    help="权威译名表 verified_names.csv；缺省时使用内置那份")
    ap.add_argument("--no-normalize", action="store_true",
                    help="不做姓名规范化（保留 K. 马克思 这类原样）")
    args = ap.parse_args(argv)

    verified_path = args.verified
    if verified_path is None:
        bundled = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "references", "glossary", "verified_names.csv")
        verified_path = bundled if os.path.isfile(bundled) else None
    verified = load_verified(verified_path)

    files, obs, display, per_file, touched = collect(args.inputs,
                                                     normalize=not args.no_normalize)
    os.makedirs(args.outdir, exist_ok=True)

    rows = []
    overrides = []
    for k, items in obs.items():
        src = display[k]
        counts = Counter(d for d, _, _ in items)
        total = sum(counts.values())
        freq_best, ranked = pick_best(counts)
        conflict = len(counts) > 1

        v = verified.get(name_key(src))
        if v:
            dst, conf, vbase, vform = v
            status, basis, note = "已定", f"verified:{conf}", vbase
            if dst != freq_best:
                overrides.append({
                    "src": src, "freq_dst": freq_best, "freq_count": counts[freq_best],
                    "verified_dst": dst, "confidence": conf,
                    "basis": vbase, "variants": " | ".join(
                        f"{d}×{c}" for d, c in ranked),
                })
        else:
            dst = freq_best
            note = ""
            if conflict:
                # Several renderings compete; a human has to pick one.
                status, basis = "待裁决", "freq"
            elif flag(src, dst):
                status, basis = "待人工", "residual"
            else:
                # Single rendering, no contest. Usable as-is; whether it is the
                # *best* rendering is a different question the table cannot answer.
                status = "一致"
                basis = "normalize" if any(n for _, _, n in items) else "freq"

        residual = flag(src, dst)
        # A verified entry's kind is known from its form, and that beats the
        # capitalisation heuristic ("marx" alone looks like a bare lowercase word).
        kind = ("place" if v and v[3] == "place" else "name") if v else classify(src, dst)
        rows.append({
            "src": src,
            "dst": dst,
            "kind": kind,
            "status": status,
            "basis": basis,
            "flag": residual,
            "count": total,
            "n_variants": len(counts),
            "note": note,
            "variants": " | ".join(f"{d}×{c}" for d, c in ranked),
            "files": " | ".join(sorted({f for _, f, _ in items})),
        })

    sort_rank = {"待人工": 0, "待裁决": 1, "一致": 2, "已定": 3}
    rows.sort(key=lambda r: (sort_rank.get(r["status"], 4), -r["n_variants"],
                             -r["count"], r["src"].lower()))
    rows = [r for r in rows if r["count"] >= args.min_count]

    master = os.path.join(args.outdir, "glossary_master.csv")
    fields = ["src", "dst", "kind", "status", "basis", "flag", "count",
              "n_variants", "note", "variants", "files"]
    with open(master, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})

    conflicts = [r for r in rows if r["status"] == "待裁决"]
    todo = [r for r in rows if r["status"] == "待人工"]
    conf_path = os.path.join(args.outdir, "glossary_conflicts.csv")
    with open(conf_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "src", "dst", "kind", "n_variants", "count", "variants"])
        w.writeheader()
        for r in conflicts:
            w.writerow({k: r[k] for k in w.fieldnames})

    over_path = os.path.join(args.outdir, "glossary_overrides.csv")
    with open(over_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "src", "freq_dst", "freq_count", "verified_dst",
            "confidence", "basis", "variants"])
        w.writeheader()
        for r in overrides:
            w.writerow(r)

    # Near duplicates: same entity spelled slightly differently in the source.
    loosemap = defaultdict(list)
    for r in rows:
        loosemap[loose_key(r["src"])].append(r)
    near = {k: v for k, v in loosemap.items() if len(v) > 1}

    stats = {
        "files": len(files),
        "total_observations": sum(per_file.values()),
        "unique_keys": len(obs),
        "normalized": touched,
        "verified": sum(1 for r in rows if r["basis"].startswith("verified")),
        "settled": sum(1 for r in rows if r["status"] == "已定"),
        "consistent": sum(1 for r in rows if r["status"] == "一致"),
        "to_decide": len(conflicts),
        "to_manual": len(todo),
        "overrides": len(overrides),
        "near_duplicate_groups": len(near),
    }

    report = [
        "术语表合并报告",
        "=" * 40,
        f"输入文件数          {stats['files']}",
        f"原始条目总数        {stats['total_observations']}",
        f"规范化改写译法      {stats['normalized']} 处",
        f"去重后唯一条目      {stats['unique_keys']}",
        "",
        "处置结果：",
        f"  已定（权威译名）    {stats['settled']}",
        f"  一致（唯一译法）    {stats['consistent']}",
        f"  待裁决（多译法）    {stats['to_decide']}",
        f"  待人工（结构异常）  {stats['to_manual']}",
        "",
        f"权威译名覆盖频次推荐  {stats['overrides']} 处 → glossary_overrides.csv",
        f"近似重复分组          {stats['near_duplicate_groups']}",
        "",
        "各文件条目数：",
    ]
    for name, n in per_file.items():
        report.append(f"  {n:>6}  {name}")
    report += ["", "按类别统计："]
    kc = Counter(r["kind"] for r in rows)
    for kind, n in kc.most_common():
        report.append(f"  {n:>6}  {kind}")
    with open(os.path.join(args.outdir, "merge_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    print("\n".join(report))

    if not args.no_markdown:
        md = os.path.join(args.outdir, "glossary_review.md")
        still_conflict = conflicts
        flagged = [r for r in rows if r["status"] == "待人工"]
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("# 术语表待校对清单\n\n")
            fh.write(f"共 {stats['unique_keys']} 条：**已定 {stats['settled']}**、"
                     f"**一致 {stats['consistent']}**、"
                     f"**待裁决 {stats['to_decide']}**、"
                     f"**待人工 {stats['to_manual']}**。\n\n")
            fh.write("状态含义：「已定」有权威译名作依据；「一致」全表只有一个译法、"
                     "没有竞争，可直接用；「待裁决」有多种译法并存，必须挑一个；"
                     "「待人工」是结构异常，机器判断不了。\n\n")
            fh.write("姓名规范化已把 `马克思·K`、`K. 马克思`、`弗利, D. K.` 这类写法"
                     "统一成纯中文姓名，原先由此产生的假冲突已消解。\n\n")

            fh.write("## 一、待裁决：同一原文有多种译法\n\n")
            if still_conflict:
                fh.write("| ☐ | 原文 | 推荐 | 备选（频次） | 类别 | 次数 |\n")
                fh.write("|---|---|---|---|---|---|\n")
                for r in still_conflict:
                    alts = "／".join(r["variants"].split(" | ")[1:]) or "—"
                    fh.write(f"| ☐ | {r['src']} | **{r['dst']}** | {alts} | "
                             f"{r['kind']} | {r['count']} |\n")
            else:
                fh.write("无。\n")

            fh.write("\n## 二、权威译名与频次推荐冲突（已按权威值覆盖，请复核）\n\n")
            if overrides:
                fh.write("| ☐ | 原文 | 频次推荐 | 权威译名 | 置信度 | 依据 |\n")
                fh.write("|---|---|---|---|---|---|\n")
                for o in overrides:
                    fh.write(f"| ☐ | {o['src']} | {o['freq_dst']}（{o['freq_count']}） | "
                             f"**{o['verified_dst']}** | {o['confidence']} | {o['basis']} |\n")
            else:
                fh.write("无。\n")

            fh.write("\n## 三、仍需人工判断（缩写残留、原文脏字符等）\n\n")
            if flagged:
                fh.write("| ☐ | 原文 | 现有译法 | 问题 |\n|---|---|---|---|\n")
                reason = {
                    "initials_merged": "姓名与缩写被拼在一起",
                    "mixed_latin": "译文残留拉丁字母",
                    "long_src": "原文过长，不像术语",
                    "long_dst": "译文过长，不像译名",
                }
                for r in flagged:
                    why = "／".join(reason.get(f, f) for f in r["flag"].split(";"))
                    fh.write(f"| ☐ | {r['src']} | {r['dst']} | {why} |\n")
            else:
                fh.write("无。\n")

            fh.write("\n## 四、疑似同一实体、写法不一（建议合并）\n\n")
            if near:
                fh.write("| ☐ | 归一化键 | 现有写法 → 译法 |\n|---|---|---|\n")
                for k, group in sorted(near.items(), key=lambda kv: kv[0]):
                    cell = "；".join(f"`{g['src']}` → {g['dst']}" for g in group)
                    fh.write(f"| ☐ | {k} | {cell} |\n")
            else:
                fh.write("无。\n")

            fh.write("\n## 五、全部条目（已去重）\n\n")
            fh.write("| 原文 | 译法 | 类别 | 状态 | 依据 | 次数 |\n|---|---|---|---|---|---|\n")
            for r in rows:
                fh.write(f"| {r['src']} | {r['dst']} | {r['kind']} | {r['status']} | "
                         f"{r['basis']} | {r['count']} |\n")
        print(f"\n已写出：\n  {master}\n  {conf_path}\n  {over_path}\n  {md}")


if __name__ == "__main__":
    main()
