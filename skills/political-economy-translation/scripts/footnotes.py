#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口：脚注流程已统一到 ``footnote_recover.py``。

两个翻译 skill 现在共用同一套实现：以 MinerU ``content_list.json`` 的
``page_footnote`` 为主检出源，PDF 文字层只作交叉验证（双栏期刊脚注在栏底，
按页底缩进找会漏）。旧命令会尽力映射到新脚本；拿不到提取包时给出迁移提示。

新流程直接运行：

    python scripts/footnote_recover.py _work/extract -o _work \
        --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from footnote_recover import main as recover_main


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--md")
    ap.add_argument("-o", "--outdir", default="_work")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--patch")
    ap.add_argument("--auto-mark", action="store_true")
    ap.add_argument("--text")
    ap.add_argument("--drop", action="append", default=[])
    args, _ = ap.parse_known_args()

    src = None
    if args.md:
        base = pathlib.Path(args.md).parent
        cands = list(base.rglob("*content_list*.json"))
        if not cands:
            cands = list(base.parent.rglob("*content_list*.json"))
        if cands:
            src = str(cands[0])
    if not src:
        print("[兼容入口] 找不到 MinerU content_list.json，无法沿用旧的 PDF 文字层路线。\n"
              "新流程以提取包为主源，请直接运行：\n"
              "  python scripts/footnote_recover.py _work/extract -o _work "
              "--source <原文>.md --target <译文>_zh.md --apply --check --pdf <原文>.pdf",
              file=sys.stderr)
        return 2

    new_argv = [src, "-o", args.outdir]
    if args.md:
        new_argv += ["--source", args.md]
    if args.pdf:
        new_argv += ["--pdf", args.pdf]
    if args.text:
        new_argv += ["--text", args.text]
    new_argv.append("--check")
    if args.patch or args.auto_mark:
        print("[兼容入口] `--patch` / `--auto-mark` 已由 `footnote_recover.py --apply` 取代，"
              "本入口只做核对，不写回 Markdown。")
    print("[兼容入口] footnotes.py → footnote_recover.py（content_list.json 路线）")
    return recover_main(new_argv)


if __name__ == "__main__":
    sys.exit(main())
