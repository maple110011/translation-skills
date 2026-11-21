#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重锚《文集》各卷的「段落 → 印刷页」，替换旧 page_map 的产物。

为什么重做
----------
旧 `page_map.py` 逐段在 PDF 全文里找开头，并让游标单调前进。一旦某段的前缀
在别处又出现一次，游标被带过去，**后面连续几段一起偏**。实测第 6 卷
`MEA6-017` 第 106—110 段集体偏后 2 页（记 315，实际 313）。这类错误单调、连续，
平滑救不回来，只能重锚。

做法
----
1. 把每页 PDF 文本规范化（只留汉字/字母/数字），拼成一条长串，记住每页起点。
2. 每个段落用「段首滑窗 + 多长度」找候选：PDF 文本里脚注序号会插进正文
   （「三个阶段1根据」），单取前 14 字常常对不上。
3. 候选里选一条**全局单调**的路径：DP 最小化「与旧值的偏差」之和。
   单调由状态转移本身保证，不需要事后平滑；旧值只作先验，不作定论。

旧值是「离真值最近的猜测」（多数时候只差 0—1 页），所以用它当先验既能挡住
「同书别处重复出现」的远处候选，又不会把正确页判掉。

产物与旧文件同 schema，`finalize.py` 可原样接着跑。

用法：
    python repaginate.py 1 2 3 4 5 6 7 10
    python repaginate.py --dry 6        # 只报告，不写盘
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


def load_pages(vol):
    fp = os.path.join(ROOT, f"corpus/mea{vol}_pages.jsonl")
    return {r["doc"] + ":" + str(r["i"]): r
            for r in (json.loads(l) for l in open(fp, encoding="utf-8"))}


def page_texts(vol):
    fp = os.path.join(ROOT, f"pdf/mea{vol}.txt")
    if not os.path.exists(fp):
        return None, None, None
    pages = [norm(p) for p in
             open(fp, encoding="utf-8", errors="replace").read().split("\f")]
    starts, pos = [], 0
    for t in pages:
        starts.append(pos)
        pos += len(t)
    return "".join(pages), starts, pages


def candidates(big, starts, text, max_hits=8):
    """段首滑窗 + 多长度 → [(offset, pdf_page)]，按位置排序去重。

    段首常是 OCR 重灾区（缩进、多余空格、错字），所以先在开头 48 字内滑窗；
    还对不上时退一步，用段落中段的片段再试一次——有些段落开头被脚注序号
    或断行切碎，中段反而是干净的。
    """
    s = norm(text)
    out = []
    for wlen in (14, 12, 10, 8):
        for st in range(0, min(48, max(1, len(s) - wlen + 1))):
            frag = s[st:st + wlen]
            if len(frag) < 8:
                break
            o, cnt = big.find(frag), 0
            while o >= 0 and cnt < max_hits:
                out.append(o)
                o, cnt = big.find(frag, o + 1), cnt + 1
            if out:
                break
        if out:
            break
    if not out:
        st0 = len(s) // 3
        mid = s[st0:]
        for wlen in (12, 10, 8):
            frag = mid[:wlen]
            if len(frag) < 8:
                break
            o = big.find(frag)
            if o >= 0:
                # 中段命中，按片段在段内的偏移倒推回段首
                out.append(max(0, o - st0))
                break
    res, seen = [], set()
    for o in sorted(out):
        p = page_of_off(starts, o)
        if p not in seen:
            seen.add(p)
            res.append((o, p))
    return res


def page_of_off(starts, o):
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= o:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def repaginate(vol, dry=False):
    big, starts, pages = page_texts(vol)
    if big is None:
        print(f"卷 {vol}: 缺 pdf/mea{vol}.txt，跳过")
        return None
    idx = {}
    ip = os.path.join(ROOT, f"corpus/pages_index{vol}.json")
    if os.path.exists(ip):
        idx = json.load(open(ip, encoding="utf-8"))
    old = load_pages(vol)

    rows = [json.loads(l) for l in open(os.path.join(ROOT, f"corpus/mea{vol}.jsonl"),
                                        encoding="utf-8")]
    rows = [r for r in rows if r["kind"] == "para"]
    if not rows:
        return None

    # 每个段落的候选状态：[(cost, offset, pdf_page, print_page)]
    states = []
    for r in rows:
        key = r["doc"] + ":" + str(r["i"])
        o_old = old.get(key, {})
        prior = o_old.get("print_page")
        cs = candidates(big, starts, r["text"])
        st = []
        for off, pdfp in cs:
            pr = idx.get(str(pdfp)) or idx.get(pdfp)
            if not pr:
                continue
            cost = abs(pr - prior) if prior else 0.0
            st.append((cost, off, pdfp, float(pr)))
        if not st:
            # 找不到：留一个「沿用上一段」的空状态，代价略高，让 DP 自己决定
            st = [(6.0, None, None, None)]
        st.sort()
        states.append((st, prior))

    # 单调 DP：状态 = 选中的 pdf_page，转移要求不倒退
    n = len(states)
    dp = []
    for i, (st, prior) in enumerate(states):
        cur = []
        for cost, off, pdfp, pr in st:
            if i == 0:
                cur.append((cost, -1, -1))
                continue
            best = None
            for k, (pcost, kpdf, _) in enumerate(dp[i - 1]):
                if pdfp is not None and kpdf is not None and kpdf > pdfp:
                    continue
                c = pcost + cost
                if best is None or c < best[0]:
                    best = (c, k)
            cur.append((best[0], best[1], -1) if best else (cost, -1, -1))
        dp.append(cur)

    # 回溯
    pick = [None] * n
    k = min(range(len(dp[-1])), key=lambda j: dp[-1][j][0])
    for i in range(n - 1, -1, -1):
        pick[i] = k
        k = dp[i][k][1]
        if k < 0:
            k = 0

    out, prev_pdf, prev_print, moved, miss = [], None, None, 0, 0
    for i, r in enumerate(rows):
        st = states[i][0]
        cost, off, pdfp, pr = st[pick[i]]
        if pdfp is None:
            miss += 1
            pdfp, pr = prev_pdf or 1, prev_print
        prev_pdf, prev_print = pdfp, pr
        end = pdfp
        if off is not None:
            e = min(off + len(norm(r["text"])), len(big) - 1)
            end = page_of_off(starts, e)
        key = r["doc"] + ":" + str(r["i"])
        o_old = old.get(key, {})
        if o_old.get("print_page") and pr and abs(o_old["print_page"] - pr) > 1:
            moved += 1
        out.append({"doc": r["doc"], "i": r["i"], "pdf_page": pdfp,
                    "print_page": int(pr) if pr else None,
                    "pdf_page_end": end, "b_start": off,
                    "b_len": len(norm(r["text"])) if off is not None else None,
                    "anchored": off is not None})

    # 校验：段首、段尾各自独立定位是否落在同一页（±1）
    agree = check = 0
    for r, o in zip(rows, out):
        s = norm(r["text"])
        if len(s) < 30 or o["print_page"] is None:
            continue
        tail = [idx.get(str(p)) for _, p in candidates(big, starts, s[-12:], 3)]
        tail = [t for t in tail if t]
        if not tail:
            continue
        check += 1
        if abs(tail[-1] - o["print_page"]) <= 1:
            agree += 1

    n_ok = sum(1 for o in out if o["anchored"])
    print(f"卷 {vol:>2}: {len(rows):5d} 段  锚定 {n_ok:5d} ({n_ok/len(rows):.1%})  "
          f"改页>1 {moved:5d}  沿用 {miss:3d}  "
          f"头尾校验 {agree}/{check} = {agree/max(1,check):.1%}")

    if not dry:
        fp = os.path.join(ROOT, f"corpus/_new{vol}_pages.jsonl")
        with open(fp, "w", encoding="utf-8") as fh:
            for o in out:
                fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    return {"vol": vol, "paras": len(rows), "anchored": n_ok, "moved": moved,
            "check": check, "agree": agree}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vols", nargs="*", type=int)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    vols = a.vols or [1, 2, 3, 4, 5, 6, 7, 10]
    tot = {"paras": 0, "anchored": 0, "moved": 0, "check": 0, "agree": 0}
    for v in vols:
        r = repaginate(v, a.dry)
        if r:
            for k in tot:
                tot[k] += r[k]
    print(f"合计 {tot['paras']} 段，锚定 {tot['anchored']/max(1,tot['paras']):.1%}，"
          f"改页>1 共 {tot['moved']} 段，头尾校验 {tot['agree']}/{tot['check']} = "
          f"{tot['agree']/max(1,tot['check']):.1%}")
    if a.dry:
        print("（--dry：未写盘）")


if __name__ == "__main__":
    main()
