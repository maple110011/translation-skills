#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""marx_quotes.py 的引号体例与引用体例回归测试。

覆盖两处曾经整条漏掉的情形：

1. **英式单引号**。Sage／T&F 通篇 `‘…’`，引擎的行内规则只认双引号，
   实测一篇 41 个单引号的稿子抽出 0 条。
2. **MEGA 式引用串** `Marx, 1987a [1872]: 90`。年份后面不接冒号，
   按 `(\\d{4})\\s*:` 找年份则整条不成立，锚定也无从谈起。

不依赖 `_marx_ref`：这里只测本 skill 自己那部分（扫描、解析、锚定），
引擎交给它的 `extract()` 用桩代替。

    python scripts/_test_marx_quotes.py
退出码 0 = 全过。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import marx_quotes as mq                                   # noqa: E402

YEARS = {"1872", "1976", "1978", "1981", "1987"}


class StubQuotes:
    """引擎的 quotes 模块替身：只提供 find_quotes 用到的那几个入口。"""

    def __init__(self, items=()):
        self.items = list(items)

    def extract(self, md):
        return self.items

    @staticmethod
    def clean(t):
        return " ".join(t.split()).strip(" \t\"'—–-")

    @staticmethod
    def is_english(t):
        return len(t) >= 20 and len([w for w in t.replace(",", " ").split()
                                     if len(w.strip(".")) >= 2]) >= 4


def cite_cases():
    """(引用串, 期望 year, 期望 orig, 期望 page)。None 表示不该认成引用。"""
    return [
        ("(1978: 357)", "1978", "", "357"),
        ("(1978: 580).", "1978", "", "580"),
        ("(Marx 1990: 448, emphasis added)", "1990", "", "448"),
        ("(Marx [1867] 1976: 173–6)", "1976", "1867", "173–6"),
        ("(Marx, 1987a [1872]: 90)", "1987", "1872", "90"),
        ("(Marx, 1987a [1872], p. 90)", "1987", "1872", "90"),
        ("(Marx 1976: ch. 10)", "1976", "", "ch. 10"),
        ("（Marx 1978: 580）", "1978", "", "580"),
        ("(Capital I, p. 163)", None, None, None),
        ("(MECW 35: 436)", None, None, None),
        ("(as we saw above: see p. 12)", None, None, None),
    ]


def volume_cases():
    vmap = dict(mq.DEFAULT_MAP)
    return [
        ({"year": "1978", "orig": ""}, vmap, "6"),
        ({"year": "1987", "orig": "1872"}, vmap, "5"),          # 首版年兜底
        ({"year": "1987", "orig": "1872"}, dict(vmap, **{"1987": "6"}), "6"),
        ({"year": "2001", "orig": ""}, vmap, ""),               # 认不出就全库
    ]


BRITISH = """---
title: t
---

kuruma observes that ‘the worker sells his labour power as a commodity, and the capitalist buys it in order to consume it’ (Marx, 1987a [1872]: 90).

Smith notes that 'it is not the consciousness of men that determines their being, but their social being that determines their consciousness' (Marx [1867] 1976: 173–6).

Consider the ‘immaterial labour’ hypothesis and the ‘social factory’ thesis; and Marx’s ‘state’s role’ note (Panitch 1994: 12).

> ‘The wealth of those societies in which the capitalist mode of production prevails, appears as an immense accumulation of commodities’ (Marx 1976: 125).
"""


def find_cases():
    qs, _ = mq.find_quotes(BRITISH, StubQuotes(), YEARS)
    by_text = {q["text"][:40]: q for q in qs}
    return qs, by_text


def main():
    ok, bad = 0, []

    def check(name, cond, detail=""):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append((name, detail))

    for text, year, orig, page in cite_cases():
        got = mq.parse_cite(text)
        if year is None:
            check(f"parse_cite 不认 {text}", got is None, f"却解析成 {got}")
            continue
        check(f"parse_cite {text}", bool(got), "认不出来")
        if got:
            check(f"parse_cite {text} 年份", got["year"] == year, f"{got['year']} ≠ {year}")
            check(f"parse_cite {text} 首版年", got["orig"] == orig, f"{got['orig']} ≠ {orig}")
            check(f"parse_cite {text} 页码", got["page"] == page, f"{got['page']} ≠ {page}")

    for q, vmap, expect in volume_cases():
        got = mq.volume_for(q, vmap)
        check(f"volume_for {q}", got == expect, f"{got!r} ≠ {expect!r}")

    tc = mq.tail_cite("The passage ends here (Marx, 1987a [1872]: 90).")
    check("tail_cite 段末引用", tc is not None and tc[1]["page"] == "90", repr(tc))
    check("tail_cite 无引用", mq.tail_cite("No citation here at all.") is None)

    qs, by = find_cases()
    texts = [q["text"] for q in qs]

    first = [t for t in texts if t.startswith("the worker sells")]
    check("英式单引号被抓到", len(first) == 1, f"{len(texts)} 条里没有/重复：{texts}")
    if first:
        q = [x for x in qs if x["text"] == first[0]][0]
        check("英式引号带 MEGA 引用串", q["citation"] == "Marx, 1987a [1872]: 90",
              q["citation"])
        check("MEGA 引用串定年", q["year"] == "1987", q["year"])

    check("直单引号也被抓到", any(t.startswith("it is not the consciousness") for t in texts),
          str(texts))
    check("撇号不被当成引号",
          not any("state’s role" in t or "immaterial labour" in t for t in texts),
          str(texts))
    check("短术语不被当成整段引文", not any(t.startswith("immaterial labour") for t in texts))
    check("引文块署同一行的引用串也能认",
          any(q["citation"] == "Marx 1976: 125" for q in qs),
          str([(q["kind"], q["citation"]) for q in qs]))
    check("混合段不被整体算成引文",
          not any(q["kind"] == "block" and "kuruma observes" in q["text"] for q in qs),
          str([q["text"][:30] for q in qs if q["kind"] == "block"]))

    # 引擎与本地扫描抓到同一条时不重复计数
    md = "the worker sells his labour power as a commodity, and the capitalist buys it"
    stub = StubQuotes([{"start": 0, "end": 40, "kind": "inline", "text": md,
                        "raw": md, "citation": "Marx, 1987a [1872]: 90", "line": 1}])
    dup, _ = mq.find_quotes(f"‘{md}’ (Marx, 1987a [1872]: 90)", stub, YEARS)
    check("引擎与本地去重", len(dup) == 1, f"{len(dup)} 条")

    print()
    if bad:
        print(f"失败 {len(bad)} 条：")
        for name, detail in bad:
            print(f"  ✗ {name}：{detail}")
        return 1
    print(f"全部通过（{ok} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
