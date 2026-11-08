#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给一个人名，返回唯一译法。按三层优先级取，不并列。

和 skill 自带的 `lookup_term.py` 分工不同：

- `lookup_term.py` 是**裁决工具**：把各表里的候选全部摆出来，同一 src 有多种
  译法时打 ⚠ 让你先定。它不该用来"查个结果就走"。
- 本脚本是**取用工具**：优先级已经定了，直接给结论。正文里出现一个人名时用它。

优先级（高到低）：

1. `names_override.csv`        学界惯用，79 条，本目录自带
2. `verified_names.csv`        权威译名，240 条，skill 自带（标 high 的）
3. `glossary_core.csv`         跨文献专名，1170 条，skill 自带
4. `names_xinhua.tsv.gz`       新华社标准，48.8 万条，本目录自带

用法：
    python pick_name.py Veblen Shaikh Bensussan
    python pick_name.py --explain Veblen     # 说明这条例子的来源层
    python pick_name.py --json Veblen        # 给程序读

命中第一层即返回，不再往下看——这一层就是为"压过其余"存在的。
四层都没有时退出码 1，提示按 terminology.md 音译规则自己定。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_GLOSSARY = os.path.join(
    os.path.expanduser("~"), ".codebuddy", "skills",
    "political-economy-translation", "references", "glossary")

LAYERS = [
    ("override", "names_override.csv"),
    ("verified", "verified_names.csv"),
    ("core", "glossary_core.csv"),
]


def _key(s):
    """比对用的键：小写、去首字母缩写、去标点、压空格。

    `Veblen`、`veblen`、`Veblen T`、`veblen, t.` 都要能对上同一条。
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s)
    # 去掉尾部的单字母（首字母缩写）：'veblen t' -> 'veblen'
    s = re.sub(r"\s+[a-z]$", "", s)
    return s


def load_rows(path):
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []


def build_index(glossary_dir):
    """返回 {层名: {键: (译名, 说明)}}。同键多值时取第一条，因为文件本身已按权威度排。"""
    out = {}
    for layer, fname in LAYERS:
        path = os.path.join(glossary_dir, fname)
        idx = {}
        for r in load_rows(path):
            src = (r.get("src") or "").strip()
            dst = (r.get("dst") or "").strip()
            if not src or not dst:
                continue
            basis = (r.get("basis") or r.get("note") or "").strip()
            status = (r.get("status") or "").strip()
            note = "／".join(x for x in (status, basis) if x)
            idx.setdefault(_key(src), (dst, note, src))
        out[layer] = idx
    return out


def load_xinhua(glossary_dir):
    path = os.path.join(glossary_dir, "names_xinhua.tsv.gz")
    if not os.path.isfile(path):
        return {}
    idx = {}
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                    idx.setdefault(_key(parts[0]), (parts[1].strip(), "新华社", parts[0]))
    except OSError:
        return {}
    return idx


def pick(name, layers, xinhua, explain=False):
    k = _key(name)
    for layer, _f in LAYERS:
        hit = layers.get(layer, {}).get(k)
        if hit:
            return {"name": name, "dst": hit[0], "layer": layer, "note": hit[1]}
    hit = xinhua.get(k)
    if hit:
        return {"name": name, "dst": hit[0], "layer": "xinhua", "note": hit[1]}
    return {"name": name, "dst": None, "layer": None, "note": ""}


def main(argv=None):
    ap = argparse.ArgumentParser(description="按既定优先级给一个人名唯一译法")
    ap.add_argument("names", nargs="+", help="人名，可多个")
    ap.add_argument("--glossary", "-g", default=None, help="术语表目录（默认 skill 的）")
    ap.add_argument("--explain", action="store_true", help="多打一列，说明取自哪一层")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    gdir = args.glossary or SKILL_GLOSSARY
    if not os.path.isdir(gdir):
        sys.exit("找不到术语表目录：%s\n先装 skill，或用 --glossary 指定。" % gdir)

    layers = build_index(gdir)
    xinhua = load_xinhua(gdir)

    results = [pick(n, layers, xinhua) for n in args.names]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        width = max((len(r["name"]) for r in results), default=8)
        for r in results:
            if r["dst"] is None:
                print("%-*s  未收录 —— 按 terminology.md 的音译规则自己定，定完回填 names_override.csv"
                      % (width, r["name"]))
            elif args.explain:
                print("%-*s  →  %s   [%s%s]"
                      % (width, r["name"], r["dst"], r["layer"],
                         ("：" + r["note"]) if r["note"] else ""))
            else:
                print("%-*s  →  %s" % (width, r["name"], r["dst"]))

    return 0 if all(r["dst"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
