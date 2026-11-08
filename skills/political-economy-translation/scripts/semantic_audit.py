#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按段比对数字，只做这一件事。

为什么只剩数字
--------------
这个脚本最初查四类：数字、否定、限定、逻辑。用三篇真实译稿实测后，后面三类
的误报率过半，取样两条就能看出问题：

* ``thus`` 在 "thus far" 里是「至此」，不是因果
* ``since`` 在 "Since the NI was first introduced" 里是「自从」，不是因果
* ``must`` 译成「还须定义」，词表里没有「须」，判成漏译
* ``10,000`` 译成 ``10000``，中文不写千分位，判成丢失
* 中文把 ``may be represented`` 译成「都能得到表示」，省略情态是合法的

根子不在词表不全——补不完。同一个英文词在不同位置承担不同的语义功能，字符串
匹配看不见这一点。所以那三类交给人读（见 references/semantic-review.md），
这里只留真正能机械化的一类：**数值**。

数值错是硬错（1973 写成 1873，0.5 写成 0.05），且不受语言习惯干扰。比对前做
归一化，把中文排版的写法差异抵消掉：

* ``10,000`` / ``10 000`` / ``10000`` 视为同一个数
* ``5 per cent`` / ``5%`` 视为同一个值
* ``1980s`` 不算年份（中文惯作「八十年代」，抓它只会天天误报）

用法
----
    python semantic_audit.py 原文.md 译文.md
    python semantic_audit.py 原文.md 译文.md -o _work/x_数字核对.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fidelity_check import blocks, strip_frontmatter  # noqa: E402

# 只查不会译成中文数字的形态。普通整数（three cases → 三种情况）交给人工。
NUM_PATTERNS = {
    "年份": re.compile(r"(?<![\d.])(?:1[6-9]\d{2}|20\d{2})(?![\d.]|[sS])"),
    "小数": re.compile(r"(?<![\d.])\d+\.\d+(?![\d.])"),
    "百分比": re.compile(r"\d+(?:\.\d+)?\s*%"),
    "千分位": re.compile(r"\d{1,3}(?:[,\u00a0 ]\d{3})+(?![\d])"),
    # 页码单独查：译文漏掉 pp. 12–18 这种定位，读者无从核对引文
    "页码": re.compile(r"\bpp?\.\s*\d+(?:\s*[–—-]\s*\d+)?"),
}
PERCENT_WORDS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:per\s*cent|percent|p\.\s?c\.)", re.I)
SEPARATORS = re.compile(r"(?<=\d)[,\u00a0 ](?=\d{3}(?!\d))")
ALL_DIGITS = re.compile(r"\d+")
CN_UNIT = re.compile(r"[一二三四五六七八九十百千万亿两]+\s*(?:万|千|百|亿)")


def normalise(text):
    """把各种写法收敛成可比对的数值集合。"""
    text = PERCENT_WORDS.sub(r"\1%", text)
    vals, pct = set(), set()
    for name, rx in NUM_PATTERNS.items():
        for m in rx.finditer(text):
            raw = m.group(0).replace(" ", "").replace("\u00a0", "")
            if name == "百分比":
                pct.add(SEPARATORS.sub("", raw.rstrip("%")))
            elif name == "页码":
                # pp. 12–18 与 p. 12 都收成 12–18 / 12，只比数字本身
                page = re.sub(r"^pp?\.", "", raw).replace("—", "–").replace("-", "–")
                vals.add("p" + page)
            else:
                vals.add(SEPARATORS.sub("", raw))
    return vals, pct


def body_of(text):
    """切掉参考文献区：书目按规则 4 原样保留，两侧本就相同，
    进去比只会把书里的年份页码当成错译。"""
    return re.split(r"^#{1,6}\s*(?:参考文献|References|Bibliography)\s*$",
                    text, flags=re.M)[0]


def audit_pair(src, tgt):
    """返回这一对上的数字差异。"""
    found = []
    s_vals, s_pct = normalise(src)
    t_vals, t_pct = normalise(tgt)
    # 译文侧另外收一遍裸数字，好让 10,000 对得上 10000
    t_bare = set(ALL_DIGITS.findall(tgt))

    for kind, s_set, t_set, bare in (
        ("数字", s_vals, t_vals, t_bare),
        ("百分比", s_pct, t_pct, set()),
    ):
        for v in sorted(s_set - t_set):
            if v in bare:
                continue                      # 译文写了裸数字，只是没有分隔符
            found.append((kind, f"原文有而译文无：{v}"))
        for v in sorted(t_set - s_set):
            if v in s_vals:
                continue
            found.append((kind, f"译文多出：{v}"))
    return found


def main():
    ap = argparse.ArgumentParser(description="按段比对数字，只查归一化后不一致的数值")
    ap.add_argument("source", help="原文 md")
    ap.add_argument("target", help="译文 md")
    ap.add_argument("-o", "--out", default="", help="输出 Markdown 清单")
    args = ap.parse_args()

    src_text = body_of(strip_frontmatter(open(args.source, encoding="utf-8-sig").read()))
    tgt_text = body_of(strip_frontmatter(open(args.target, encoding="utf-8-sig").read()))
    src_p = [t for k, t in blocks(src_text, with_text=True) if k == "p"]
    tgt_p = [t for k, t in blocks(tgt_text, with_text=True) if k == "p"]

    if len(src_p) != len(tgt_p):
        print(f"段落数不一致：原文 {len(src_p)} / 译文 {len(tgt_p)}")
        print("先跑 fidelity_check.py 把结构修一致，否则配对本身就是错的。")
        return 2

    rows = []
    for i, (s, t) in enumerate(zip(src_p, tgt_p), 1):
        for kind, msg in audit_pair(s, t):
            rows.append((i, kind, msg))

    print(f"共 {len(src_p)} 段，数字不一致 {len(rows)} 处")
    for n, kind, msg in rows:
        print(f"  §{n} [{kind}] {msg}")

    if not rows:
        print("\n数值全部对得上。这只说明数字没抄错，")
        print("不说明译文准确——语义偏离要靠读，见 references/semantic-review.md。")
        return 0

    L = ["# 数字核对", "",
         f"原文 {len(src_p)} 段，{len(rows)} 处数值对不一致。", "",
         "已归一化的写法差异（10,000 / 10 000 / 10000、5 per cent / 5%、"
         "1980s 除外）不算差异。每一条都要回原文确认：可能是抄错，"
         "也可能是中文单位（如「1 万」）。", ""]
    for n, kind, msg in rows:
        L += [f"- **§{n}** [{kind}] {msg}"]
    report = "\n".join(L)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report + "\n", encoding="utf-8")
        print(f"\n清单已写入 {out}")
    else:
        print("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
