#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用同一套独立指标，对比新旧两份「段落 → 印刷页」。

指标（都不看任何一方的结论，只看 PDF 原文）：
  hit   段落开头 15 字是否真的出现在它自称的那一页（页尾跨页算命中）
  tail  段落结尾 12 字与开头是否落在同一页（±1）
  mono  页码是否单调（段序递增时页码不倒）

用法：
    python verify_pages.py 6 --old _backup_pages_20261109/mea6_pages.jsonl \
                             --new corpus/mea6_pages.jsonl
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEEP = re.compile(r"[^\u4e00-\u9fff0-9A-Za-z]")


def norm(s):
    return KEEP.sub("", s or "")


def load(path):
    m = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        m[r["doc"] + ":" + str(r["i"])] = r
    return m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vol", type=int)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    a = ap.parse_args(argv)

    pages = [norm(p) for p in open(os.path.join(ROOT, f"pdf/mea{a.vol}.txt"),
                                   encoding="utf-8", errors="replace").read().split("\f")]
    idx = json.load(open(os.path.join(ROOT, f"corpus/pages_index{a.vol}.json"),
                         encoding="utf-8"))
    inv = {}
    for k, v in idx.items():
        if v and v not in inv:
            inv[v] = int(k)
    paras = [json.loads(l) for l in open(os.path.join(ROOT, f"corpus/mea{a.vol}.jsonl"),
                                         encoding="utf-8")]
    paras = [r for r in paras if r["kind"] == "para"]

    def text_on(pg, key):
        pdfp = inv.get(pg)
        if not pdfp or pdfp > len(pages):
            return False
        buf = pages[pdfp - 1]
        if pdfp < len(pages):
            buf += pages[pdfp]
        return key in buf

    res = {}
    for tag, path in (("old", a.old), ("new", a.new)):
        m = load(path)
        hit = tot = mono_ok = mono_tot = 0
        prev = None
        for r in paras:
            o = m.get(r["doc"] + ":" + str(r["i"]))
            if not o or not o.get("print_page"):
                continue
            key = norm(r["text"])[:15]
            if len(key) < 10:
                continue
            tot += 1
            hit += text_on(o["print_page"], key)
            if prev is not None:
                mono_tot += 1
                mono_ok += o["print_page"] >= prev
            prev = o["print_page"]
        res[tag] = (hit, tot, mono_ok, mono_tot)

    oh, ot, om, omt = res["old"]
    nh, nt, nm, nmt = res["new"]
    print(f"卷 {a.vol}: 段落开头落在自称页面上")
    print(f"  旧 {oh}/{ot} = {oh/max(1,ot):.1%}   单调 {om/max(1,omt):.1%}")
    print(f"  新 {nh}/{nt} = {nh/max(1,nt):.1%}   单调 {nm/max(1,nmt):.1%}")


if __name__ == "__main__":
    main()
