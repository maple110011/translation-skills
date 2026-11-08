#!/usr/bin/env python3
"""Look up terms in the bundled glossaries without loading them into context.

The bundled glossaries are small but grow, and the project table grows with
every paper. Reading them whole costs more context than the translation itself.
This script answers the only question that matters during translation — "what
did we decide this word means?" — and prints a handful of lines.

It searches both directions: English -> Chinese when you are choosing a
rendering, Chinese -> English when you suspect a term is being used two ways.

Usage
-----
    python lookup_term.py "excess risk" "attention"
    python lookup_term.py ResNet --exact
    python lookup_term.py 相合性
    python lookup_term.py "bias-variance" --glossary ./_work/term.csv
    python lookup_term.py "kernel" --max 20 --all

Exit code is 0 when every query found something, 1 otherwise, so the caller can
tell "not in the table, go decide it yourself" from "already decided".
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "references", "glossary")


def gather_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, n) for n in sorted(os.listdir(p))
                      if n.lower().endswith(".csv")]
        elif os.path.isfile(p):
            files.append(p)
    return files


def load(files):
    """Return a list of dicts: src, dst, alt, note, source-file."""
    rows = []
    for f in files:
        enc = "utf-8-sig"
        try:
            with open(f, "r", encoding=enc, newline="") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames:
                    continue
                for r in reader:
                    low = {(k or "").lower(): (v or "").strip()
                           for k, v in r.items()}
                    src = low.get("src") or low.get("原文") or ""
                    dst = low.get("dst") or low.get("译文") or ""
                    if not src or not dst:
                        continue
                    rows.append({
                        "src": src, "dst": dst,
                        "alt": low.get("alt") or low.get("variants") or "",
                        "note": " ".join(
                            x for x in (low.get("note"), low.get("kind"),
                                        low.get("status"), low.get("flag")) if x),
                        "file": os.path.basename(f),
                    })
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            print(f"跳过 {f}：{e}", file=sys.stderr)
    return rows


def score(row, query, exact):
    q, s, d = query.lower(), row["src"].lower(), row["dst"]
    if exact:
        return 3 if s == q else (2 if d == query else 0)
    if s == q:
        return 3
    if d == query:
        return 2
    if re.search(rf"(?<![a-z]){re.escape(q)}(?![a-z])", s):
        return 2
    if q in d:
        return 1
    if q in s:
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="在术语表中查词（支持英中双向、精确/模糊）。")
    ap.add_argument("terms", nargs="+", help="要查的词，可多个")
    ap.add_argument("--glossary", "-g", nargs="*", default=[DEFAULT_DIR],
                    help="术语表目录或文件；默认为内置 glossary/")
    ap.add_argument("--exact", action="store_true", help="只返回完全匹配")
    ap.add_argument("--max", type=int, default=6, help="每个词最多显示几条（默认 6）")
    ap.add_argument("--all", action="store_true", help="不限条数")
    args = ap.parse_args(argv)

    files = gather_files(args.glossary)
    if not files:
        sys.exit(f"在 {args.glossary} 下没有找到 .csv 术语表。")
    rows = load(files)
    if not rows:
        sys.exit("术语表为空或列名无法识别（需要 src,dst 两列）。")

    missing = 0
    for term in args.terms:
        raw = []
        for r in rows:
            sc = score(r, term, args.exact)
            if sc:
                raw.append((sc, r))
        # The master and conflicts files describe the same entries; keep one row
        # per (source, translation) pair, but merge the competing-variant lists
        # so the caller sees every candidate that has ever been used.
        best = {}
        for sc, r in raw:
            key = (r["src"].lower(), r["dst"])
            if key not in best:
                best[key] = [sc, dict(r)]
            else:
                slot = best[key][1]
                if r["alt"] and r["alt"] not in slot["alt"]:
                    slot["alt"] = " | ".join(x for x in (slot["alt"], r["alt"]) if x)
                if len(r["note"]) > len(slot["note"]):
                    slot["note"] = r["note"]
        hits = sorted(((v[0], v[1]) for v in best.values()),
                      key=lambda x: (-x[0], x[1]["src"].lower()))

        print(f"\n【{term}】  共 {len(hits)} 条")
        if not hits:
            missing += 1
            print("  （未收录。按 terminology.md 的裁决顺序自行定，并写进项目术语表。）")
            continue
        limit = len(hits) if args.all else args.max
        for sc, r in hits[:limit]:
            mark = "=" if sc >= 2 else "~"
            extra = "  "
            if r["alt"]:
                extra += f"备选:{r['alt']}  "
            if r["note"]:
                extra += f"[{r['note']}]"
            # dst=@keep 是机器可读的「不译」标记；直接打印 @keep 会让查表的人
            # 以为表里填了个奇怪的中文词，显示成一句人话。
            shown = ("保留英文原文（不译）"
                     if r["dst"].strip().lower() in ("@keep", "keep") else r["dst"])
            print(f"  {mark} {r['src']}  →  {shown}"
                  + (extra if extra.strip() else ""))
        if len(hits) > limit:
            print(f"  …另有 {len(hits) - limit} 条，用 --all 或 --max N 查看")

        # Warn only when the *same* source string has competing translations.
        grouped = {}
        for _sc, r in hits:
            grouped.setdefault(r["src"].lower(), set()).add(r["dst"])
        contested = {k: v for k, v in grouped.items() if len(v) > 1}
        for k, v in contested.items():
            print(f"  ⚠ 「{k}」有 {len(v)} 种译法：{'／'.join(sorted(v))}，须先裁决。")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
