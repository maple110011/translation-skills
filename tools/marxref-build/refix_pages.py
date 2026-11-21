#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按内容重定句级页码，绕开 `zh_i` 指针。

`finalize.py` 是拿句子的 `zh_i` 去找段落、再取段落页的。但 `zh_i` 会偏一两段
（句级对齐的老毛病），于是句子的页码跟着偏——实测第 6 卷「由单纯的周转运动
这一机制游离出来的货币资本」那句被报成 311，而 PDF 上它在 313。

这里不信指针：拿句子自己的中文，回本卷段落里找它到底在哪一段，再用那一段的
页码加段内偏移算句子页。找不到才退回指针。

用法：
    python refix_pages.py 1 2 3 4 5 6 7 10
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEEP = re.compile(r"[^\u4e00-\u9fff0-9A-Za-z]")


def norm(s):
    return KEEP.sub("", s or "")


def load_paras(vol):
    rows = [json.loads(l) for l in
            open(os.path.join(ROOT, f"corpus/mea{vol}.jsonl"), encoding="utf-8")]
    rows = [r for r in rows if r["kind"] == "para"]
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], []).append(r)
    for lst in by_doc.values():
        for r in lst:
            r["_n"] = norm(r["text"])
    return by_doc


def load_pages(vol):
    fp = os.path.join(ROOT, f"corpus/mea{vol}_pages.jsonl")
    return {(r["doc"], r["i"]): r for r in
            (json.loads(l) for l in open(fp, encoding="utf-8"))}


def pava(vals):
    """等距回归：把序列拟合成不降序列（保序、最小二乘），用来压掉抖动。

    一句话页码必须是单调的（句子顺序就是正文顺序），但段内插值会让相邻句
    在 1—2 页之间来回跳，偶尔还会因为匹配到别处的重复句跳出去很远。
    PAVA 只做「最不扭曲」的调整，不引入新值。
    """
    blocks = []
    for v in vals:
        blocks.append([float(v), 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    out = []
    for s, c in blocks:
        out.extend([s / c] * c)
    return out


def main(argv=None):
    vols = [int(x) for x in (argv or sys.argv[1:])] or [1, 2, 3, 4, 5, 6, 7, 10]
    for vol in vols:
        by_doc = load_paras(vol)
        pages = load_pages(vol)
        ip = os.path.join(ROOT, f"corpus/pages_index{vol}.json")
        idx = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
        fp = os.path.join(ROOT, f"corpus/vol{vol}_sent.jsonl")
        rows = [json.loads(l) for l in open(fp, encoding="utf-8")]
        hit = miss = changed = 0
        cursor = {}
        for r in rows:
            zh = norm(r.get("zh") or "")
            if len(zh) < 8:
                continue
            doc = r.get("zh_doc") or ""
            cand = by_doc.get(doc) or []
            key = zh[:14]
            found = None
            # 先在本段附近找（段落顺序与句子顺序都是单调的），避免匹配到
            # 书上别处重复出现的同一句话——那样页码会跳出去上百页
            c0 = cursor.get(doc, 0)
            lo, hi = max(0, c0 - 2), min(len(cand), c0 + 40)
            for p in cand[lo:hi]:
                pos = p["_n"].find(key)
                if pos >= 0:
                    found = (p, pos)
                    break
            if found is None:
                for p in cand[hi:] + cand[:lo]:
                    pos = p["_n"].find(key)
                    if pos >= 0:
                        found = (p, pos)
                        break
            if found is None and len(key) >= 10:
                # 前缀被断句切碎时退一步，用 10 字窗口在段内滑
                for p in cand:
                    pos = p["_n"].find(zh[3:13])
                    if pos >= 0:
                        found = (p, max(0, pos - 3))
                        break
            if not found:
                miss += 1
                continue
            p, pos = found
            try:
                cursor[doc] = cand.index(p)
            except ValueError:
                pass
            rec = pages.get((p["doc"], p["i"]))
            if not rec or not rec.get("print_page"):
                miss += 1
                continue
            old = r.get("page")
            # 段内插值：句子在段内的字符位置 → 段所占的 PDF 页区间 → 印刷页
            span = max(0, (rec.get("pdf_page_end") or rec["pdf_page"]) - rec["pdf_page"])
            frac = pos / max(1, len(p["_n"]) or 1)
            pdfp = rec["pdf_page"] + round(frac * span)
            new = int(idx.get(str(pdfp)) or rec["print_page"])
            if old and new != old:
                changed += 1
            r["page"] = new
            hit += 1

        # 按文（篇）做保序平滑，消掉段内插值抖动和偶发的远跳
        groups = {}
        for k, r in enumerate(rows):
            if r.get("page"):
                groups.setdefault(r.get("zh_doc") or "", []).append(k)
        smoothed = 0
        for doc, ks in groups.items():
            fit = pava([rows[k]["page"] for k in ks])
            for k, v in zip(ks, fit):
                p = int(round(v))
                if p != rows[k]["page"]:
                    smoothed += 1
                rows[k]["page"] = p

        with open(fp, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"卷 {vol:>2}: {len(rows):6d} 句  内容定位 {hit:6d}  未定 {miss:5d}  "
              f"页码变动 {changed:6d}  保序平滑 {smoothed:5d}")


if __name__ == "__main__":
    main()
