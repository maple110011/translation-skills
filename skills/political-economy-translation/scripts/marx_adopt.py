#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 agent 裁定的引文译文接进流程。

`marx_quotes.py` 给出的「文集译文」是引擎跨句合并的结果，常常比引文本身长：
引文只是一个从句或半句，返回的却是整段两三句。**哪几句才算引文覆盖的范围，
脚本判不了**——那要读英文引文与中文候选，判断"这句是不是在讲同一件事"。
这一步交给 agent 做，结论写进采用表：

    序号,引用串,采用,原文句,说明
    1,1978: 358,对这个机制来说已经变成多余的金额，最终也会投到货币市场上去,对周转机制来说已成为多余的货币额，最终肯定会统统被抛到货币市场上去,引文是半句，取文集后半句

- `采用`：裁好的文集译文（只含引文覆盖的那部分）
- `原文句`：译文里要被替换的现有句子。留空则用引文 CSV 的「本译文段」。
  这一列存在，是因为「本译文段」常是引号内的一小截，整句换掉时定位不准。
- `说明`：为什么这么裁（引文是半句／文集此处残缺／文集无此句故保留等）

本脚本只做转换，不动译文：输出 review_apply 的决定表，由它统一执行
（改译文 → 重跑公式归一与结构对账 → 刷新待校对清单），这样校验链只有一条。

用法：
    python scripts/marx_adopt.py --quotes _work/x_马恩引文.csv \\
        --adopt _work/x_引文采用.csv --target x_zh.md -o _work/x_引文决定.csv
    python scripts/review_apply.py --target x_zh.md --glossary _work/x_术语.csv \\
        --decisions _work/x_引文决定.csv ...
"""
import argparse
import csv
import os
import sys


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv=None):
    ap = argparse.ArgumentParser(description="引文采用表 → review_apply 决定表")
    ap.add_argument("--quotes", required=True, help="marx_quotes.py 产出的引文 CSV")
    ap.add_argument("--adopt", required=True, help="采用表：序号,引用串,采用,原文句,说明")
    ap.add_argument("--target", default="", help="译文 Markdown，用来验证旧句确实存在")
    ap.add_argument("-o", "--out", required=True, help="输出决定表 CSV")
    args = ap.parse_args(argv)

    quotes = read_csv(args.quotes)
    adopt = read_csv(args.adopt)
    if not adopt:
        sys.exit("采用表是空的。")

    by_no = {(r.get("序号") or "").strip(): r for r in quotes}
    by_cite = {}
    for r in quotes:
        by_cite.setdefault((r.get("引用串") or "").strip(), []).append(r)

    text = open(args.target, encoding="utf-8").read() if args.target else ""
    rows, problems = [], []

    for a in adopt:
        no = (a.get("序号") or "").strip()
        cite = (a.get("引用串") or "").strip()
        new = (a.get("采用") or "").strip()
        if not new:
            problems.append(f"{no or cite}：采用栏是空的")
            continue

        if no:
            q = by_no.get(no)
        elif cite:
            hits = by_cite.get(cite, [])
            if len(hits) > 1:
                problems.append(f"{cite}：同一引用串有 {len(hits)} 条，改用「序号」定位")
                continue
            q = hits[0] if hits else None
        else:
            q = None
        if not q:
            problems.append(f"{no or cite}：引文表里找不到对应行")
            continue

        old = (a.get("原文句") or "").strip() or (q.get("本译文段") or "").strip()
        if not old:
            problems.append(f"{no or cite}：没有可替换的旧句（原文句为空，引文表也没抓到）")
            continue
        if text and old not in text:
            problems.append(f"{no or cite}：旧句在译文里找不到，不静默跳过 —— {old[:40]}…")
            continue
        if old == new:
            continue

        rows.append({
            "键": f"marx:{q.get('引用串', '')}",
            "动作": "text",
            "旧": old,
            "新": new,
            "说明": (a.get("说明") or "").strip() or "引文改用文集译文",
        })

    if rows:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["键", "动作", "旧", "新", "说明"])
            w.writeheader()
            w.writerows(rows)

    print(f"采用 {len(rows)} 条 → {args.out}")
    for r in rows:
        print(f"  {r['键']}：{r['旧'][:26]}… → {r['新'][:26]}…")
    if problems:
        print("\n没处理的（需人工看）：")
        for p in problems:
            print("  " + p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
