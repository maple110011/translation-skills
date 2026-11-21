#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把译文里的 ASCII 引号统一成中文引号。

规则：
- 双引号 `"` 按出现次序交替成 “ ”；单引号 `'` 交替成 ‘ ’。
- 英文所有格撇号（Dymski's）不动。
- 跳过：YAML front matter、参考文献、行间/行内公式、代码、图片语法。
  参考文献是原文，按规则 4 不译，也就不改它的引号。

用法：
    python scripts/zh_quotes.py 译文.md --inplace
    python scripts/zh_quotes.py 译文.md --check     # 只报告，不改
"""
import argparse
import os
import re
import sys

FRONT = re.compile(r"---\n.*?\n---\n", re.S)
REFHEAD = re.compile(r"^(#{1,6})\s*(?:参考文献|References)\s*$", re.M)


def split_refs(md):
    """正文与参考文献分开：参考文献保持原文。"""
    m = REFHEAD.search(md)
    return (md, "") if not m else (md[:m.start()], md[m.start():])


def convert(s):
    saved = []

    def stash(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    s = re.sub(r"\$\$.*?\$\$", stash, s, flags=re.S)
    s = re.sub(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", stash, s)
    s = re.sub(r"```.*?```", stash, s, flags=re.S)
    s = re.sub(r"`[^`]*`", stash, s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", stash, s)
    # HTML 标签与注释先整段保护：<table> 的 colspan="2" 里是属性定界符，
    # 转成中文引号会让属性失效（表格塌成一行）。
    s = re.sub(r"<!--.*?-->", stash, s, flags=re.S)
    s = re.sub(r"<[^>]*>", stash, s)

    out, dq, sq = [], 0, 0
    for i, ch in enumerate(s):
        if ch == '"':
            out.append("“" if dq % 2 == 0 else "”")
            dq += 1
        elif ch == "'":
            prev = s[i - 1] if i else ""
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if prev.isascii() and prev.isalpha() and nxt.isascii() and nxt.isalpha():
                out.append(ch)          # 所有格撇号
            else:
                out.append("‘" if sq % 2 == 0 else "’")
                sq += 1
        else:
            out.append(ch)
    s = "".join(out)
    for i, v in enumerate(saved):
        s = s.replace(f"\x00{i}\x00", v)
    return s


def main():
    ap = argparse.ArgumentParser(description="ASCII 引号 → 中文引号")
    ap.add_argument("target", help="译文 md")
    ap.add_argument("--inplace", action="store_true", help="直接改写文件")
    ap.add_argument("--check", action="store_true", help="只检查，不改")
    ap.add_argument("--all", action="store_true", help="参考文献也转（默认跳过）")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        sys.exit(f"找不到 {args.target}")
    md = open(args.target, encoding="utf-8").read()

    front = ""
    if md.startswith("---"):
        m = FRONT.match(md)
        if m:
            front = m.group(0)
            md = md[m.end():]

    head, tail = split_refs(md)
    if args.all:
        head, tail = head + tail, ""

    body = convert(head)
    n_dq = head.count('"')
    n_sq = sum(1 for i, c in enumerate(head)
               if c == "'" and not (i and head[i - 1].isascii() and head[i - 1].isalpha()
                                    and i + 1 < len(head) and head[i + 1].isascii()
                                    and head[i + 1].isalpha()))

    if n_dq % 2 or n_sq % 2:
        print(f"注意：引号数量不成对（双 {n_dq}、单 {n_sq}），转换后可能有一个落单，请核对。")

    if args.check:
        print(f"正文待转：双引号 {n_dq} 个、单引号 {n_sq} 个")
        return

    out = front + body + tail
    if args.inplace:
        open(args.target, "w", encoding="utf-8").write(out)
        print(f"已转换：双引号 {n_dq} 个、单引号 {n_sq} 个")
    else:
        print(out)


if __name__ == "__main__":
    main()
