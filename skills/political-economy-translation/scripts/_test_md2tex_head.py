#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""`md2tex.is_author_line` 的回归测试。

背景：首页的标题、英文题名、作者都由 front matter 生成，正文开头再出现一遍
H1 与作者行就成了重复。所以要认「标题下面那一行是不是作者名」，而且**不能
把中文摘要的第一句当成作者行删掉**——`劳动强化会提高剥削率吗` 这种没有标点
的短句，形态上和「张三、李四」几乎没有区别。

判据分两层：形态（无句读、无数字、片段数 1–6、每段长度与词数）＋ 与
front matter 的 `authors` 反向核对（首词要出现在作者串里，且两边文字系统
相同才核）。这个文件把两类误判都钉住：该删的删、不该删的不删。

用法::

    python scripts/_test_md2tex_head.py      # 0 = 全过
"""
import pathlib
import re
import sys

SKILL = pathlib.Path(__file__).resolve().parent
src = (SKILL / "md2tex.py").read_text(encoding="utf-8")
start = src.index("def is_author_line(s):")
end = src.index("def drop_title_block(ls):")
BODY = src[start:end]

BASU = "Basu, Deepankar, Haas, Cameron, Moraitis, Thanos"

CASES = [
    # (作者行, front matter 的 authors, 期望)
    ("Deepankar Basu、Cameron Haas 和 Thanos Moraitis", BASU, True),
    ("Deepankar Basu, Cameron Haas, and Thanos Moraitis", BASU, True),
    ("Basu, Deepankar", BASU, True),
    ("张三", "Zhang, San", True),          # 西文 YAML + 中文作者行：靠形态
    ("张三、李四", "Zhang, San; Li, Si", True),
    ("John Smith", "Smith, John", True),
    ("John Smith, Jane Doe & Bob Lee", "Smith, John; Doe, Jane; Lee, Bob", True),
    # 下面这些必须判 False，否则正文会被吃掉一段
    ("这是一句没有任何标点的短句", BASU, False),
    ("劳动强化会提高剥削率吗", BASU, False),
    ("由此我们得到两个结论", BASU, False),
    ("劳动强化会提高剥削率吗？", BASU, False),
    ("Marx 1992: ch. 6", BASU, False),
    ("第 II 部类的劳动强化", BASU, False),
    ("The rate of exploitation rises when labor intensity increases", BASU, False),
    ("", BASU, False),
]


def main():
    bad = 0
    for text, authors, want in CASES:
        ns = {"re": re, "AUTHORS": authors}
        exec(BODY, ns)
        got = ns["is_author_line"](text)
        if got != want:
            bad += 1
        print("%s want=%-5s got=%-5s  %s"
              % ("ok  " if got == want else "FAIL", want, got, text[:52]))
    print("\n%d/%d 通过" % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
