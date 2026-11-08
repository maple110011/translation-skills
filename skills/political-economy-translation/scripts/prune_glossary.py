#!/usr/bin/env python3
"""Trim a merged glossary down to the entries actually worth keeping.

The problem this solves
-----------------------
Glossaries auto-collected by translation tools are dominated by names pulled out
of reference lists. But reference entries are kept verbatim by rule — authors,
publishers and publication cities are never translated — so none of those names
needs a Chinese rendering. A 5400-row table where 4300 rows are reference-list
residue is not a glossary, it is an archive.

The discriminating signal is **how many documents a name appears in**, not how
often it appears. A term list is written once per document, so an entry present
in one document only was never reused; an entry present in five documents has
been encountered five times by five different translations, which is what
"frequently needed" actually looks like.

What survives
-------------
* entries seen in >= ``--min-files`` documents (default 2)
* every entry carrying an authoritative rendering, regardless of frequency —
  a name can be central to the field and still show up once in this corpus

Nothing is deleted. Removed rows are written to a separate file so the decision
is reversible.

Usage
-----
    python prune_glossary.py merged/glossary_master.csv -o pruned/
    python prune_glossary.py merged/glossary_master.csv -o pruned/ --min-files 3
    python prune_glossary.py merged/ -o pruned/ --min-files 2 --quiet
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter


def count_files(row):
    """Distinct documents the entry was seen in.

    Falls back to the observation count when the source table has no ``files``
    column, which is the case for the slim table shipped inside the skill.
    """
    files = (row.get("files") or "").strip()
    if files:
        return len([x for x in files.split("|") if x.strip()])
    try:
        return int(row.get("count") or 1)
    except ValueError:
        return 1


def tier_of(row, n_files):
    """core = you will meet it in most projects; common = worth keeping anyway."""
    basis = (row.get("basis") or "")
    if basis == "verified:high" or n_files >= 3:
        return "core"
    return "common"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="按跨文献出现频次裁剪术语表，低频条目移入 archive。")
    ap.add_argument("input", help="glossary_master.csv 或其所在目录")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--min-files", type=int, default=2,
                    help="至少出现在几份文献中才保留（默认 2）")
    ap.add_argument("--keep-verified", action="store_true", default=True,
                    help="无论频次，凡有权威译名的都保留（默认开启）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    src = args.input
    if os.path.isdir(src):
        cand = [os.path.join(src, n) for n in os.listdir(src)
                if n.startswith("glossary_master") and n.endswith(".csv")]
        if not cand:
            sys.exit(f"{src} 下没有 glossary_master.csv")
        src = cand[0]

    with open(src, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("输入为空。")
    os.makedirs(args.outdir, exist_ok=True)

    keep, drop = [], []
    for r in rows:
        n = count_files(r)
        authoritative = (r.get("basis") or "").startswith("verified")
        if n >= args.min_files or (args.keep_verified and authoritative):
            r["_n_files"] = n
            r["_tier"] = tier_of(r, n)
            keep.append(r)
        else:
            r["_n_files"] = n
            drop.append(r)

    keep.sort(key=lambda r: (r["_tier"] != "core", -r["_n_files"],
                             r["src"].lower()))

    core_path = os.path.join(args.outdir, "glossary_core.csv")
    with open(core_path, "w", encoding="utf-8-sig", newline="") as fh:
        fields = ["src", "dst", "kind", "tier", "status", "basis", "n_files", "count"]
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in keep:
            r["n_files"] = r.pop("_n_files")
            r["tier"] = r.pop("_tier")
            w.writerow({k: r.get(k, "") for k in fields})

    arch_path = os.path.join(args.outdir, "glossary_archive.csv")
    with open(arch_path, "w", encoding="utf-8-sig", newline="") as fh:
        fields = ["src", "dst", "kind", "n_files", "count", "files"]
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(drop, key=lambda r: r["src"].lower()):
            r["n_files"] = r.pop("_n_files")
            w.writerow({k: r.get(k, "") for k in fields})

    tiers = Counter(r["tier"] for r in keep)
    report = [
        "术语表裁剪报告",
        "=" * 40,
        f"输入            {os.path.basename(src)}",
        f"原始条目        {len(rows)}",
        f"保留阈值        ≥{args.min_files} 份文献（或有权威译名）",
        "",
        f"保留            {len(keep)}",
        f"  核心 core      {tiers['core']}",
        f"  常用 common    {tiers['common']}",
        f"移入档案        {len(drop)}",
        "",
        f"保留率          {len(keep) / len(rows):.1%}",
        f"保留池类别      " + "  ".join(
            f"{k}:{v}" for k, v in Counter(r["kind"] for r in keep).most_common()),
        "",
        "被移除条目的典型样貌（多为参考文献里的人名与出版地）：",
    ]
    for r in sorted(drop, key=lambda r: r["src"].lower())[:8]:
        report.append(f"  {r['src'][:30]:32} {r['dst'][:12]}")
    text = "\n".join(report)
    with open(os.path.join(args.outdir, "prune_report.txt"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    if not args.quiet:
        print(text)
        print(f"\n已写出：\n  {core_path}\n  {arch_path}")


if __name__ == "__main__":
    main()
