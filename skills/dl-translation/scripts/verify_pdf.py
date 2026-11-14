#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""译文 PDF 编译验收：编译错误、Overfull、图片、书签、文本层、脚注。

用法::

    python scripts/verify_pdf.py _work/pdf/paper.pdf \
        --tex _work/pdf/paper.tex --md <stem>_zh.md --footnotes _work/脚注.csv

编译 0 个 ``!`` 错误不等于内容完整：早期踩过「PDF 有页数但一张图都没有」
和「长表被 Overfull \vbox 整块截断」，还有「脚注留在 Markdown 里没进 PDF」。
这里把这些都做成可计数的检查，有问题返回 1，可直接接在编译命令后面。

只用 Python 标准库；``pdfinfo`` / ``pdftotext``（poppler / TeX Live）可选，
缺失时对应项跳过并提示。两个翻译 skill 共用同一实现。
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import subprocess
import sys

LIGATURES = "\ufb00\ufb01\ufb02\ufb03\ufb04"
CJK = re.compile(r"[\u4e00-\u9fff]")


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        return (r.stdout or b"").decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="译文 PDF 编译验收")
    ap.add_argument("pdf", help="编译出来的 PDF")
    ap.add_argument("--tex", default=None, help="对应 .tex（默认与 PDF 同名）")
    ap.add_argument("--md", default=None, help="译文 Markdown，用于核对图片数")
    ap.add_argument("--footnotes", default=None, help="_work/脚注.csv，逐条核脚注是否进 PDF")
    args = ap.parse_args(argv)

    pdf = pathlib.Path(args.pdf)
    tex = pathlib.Path(args.tex) if args.tex else pdf.with_suffix(".tex")
    log = pdf.with_suffix(".log")
    problems, info = [], []

    if not pdf.is_file() or pdf.stat().st_size == 0:
        print("[FAIL] PDF 不存在或 0 字节：%s" % pdf)
        return 1
    info.append("文件 %s，%s 字节" % (pdf, format(pdf.stat().st_size, ",")))
    pinfo = run(["pdfinfo", str(pdf)])
    m = re.search(r"Pages:\s+(\d+)", pinfo)
    info.append("页数 %s" % (m.group(1) if m else "?"))

    if log.is_file():
        t = log.read_text(encoding="utf-8", errors="ignore")
        errs = [ln for ln in t.splitlines() if ln.startswith("!")]
        vbox = [ln for ln in t.splitlines() if ln.startswith("Overfull \\vbox")]
        hbox = [ln for ln in t.splitlines()
                if ln.startswith("Overfull \\hbox") and "too wide" in ln]
        wide = [ln for ln in hbox
                if float((re.search(r"([\d.]+)pt too wide", ln) or ["", "0"])[1]) > 1]
        info.append("TeX 错误 %d / Overfull \\vbox %d / \\hbox>1pt %d"
                    % (len(errs), len(vbox), len(wide)))
        if errs:
            problems.append("日志里有 %d 行 `!` 错误：%s" % (len(errs), errs[:2]))
        if vbox:
            problems.append("Overfull \\vbox %d 处：长表/整块数据可能被截断" % len(vbox))
        if wide:
            problems.append("Overfull \\hbox 超过 1pt 的 %d 处，抽查公式或表格越界" % len(wide))
    else:
        info.append("（没有 .log，跳过编译日志检查）")

    tex_text = tex.read_text(encoding="utf-8", errors="ignore") if tex.is_file() else ""
    if tex_text:
        n_bookmark = tex_text.count(r"\pdfbookmark")
        n_add = tex_text.count(r"\addcontentsline")
        n_img = tex_text.count(r"\includegraphics")
        n_fn = len(re.findall(r"\\footnote\{", tex_text))
        n_end = len(re.findall(r"\\noindent\\textsuperscript\{", tex_text))
        info.append("\\pdfbookmark %d / \\addcontentsline %d / \\includegraphics %d / 页底脚注 %d + 文末编号段落 %d"
                    % (n_bookmark, n_add, n_img, n_fn, n_end))
        if n_add:
            problems.append("\\addcontentsline %d 处，会让每个标题出现两条书签" % n_add)
        if args.md and pathlib.Path(args.md).is_file():
            md = pathlib.Path(args.md).read_text(encoding="utf-8", errors="ignore")
            want = len(re.findall(r"!\[[^\]]*\]\(", md)) + len(re.findall(r"<img\b", md))
            info.append("译文图片引用 %d 处" % want)
            if want and n_img < want:
                problems.append("TeX 只有 %d 个 \\includegraphics，译文有 %d 处图片引用："
                                "编译 0 错误也可能一张图都没有" % (n_img, want))
    else:
        info.append("（没有 .tex，跳过书签/图片/脚注命令检查）")

    raw = run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"])
    if not raw:
        info.append("（拿不到 PDF 文本层，跳过文本层检查；装 poppler 后可补全）")
    else:
        big = re.sub(r"\s+", " ", raw)
        n_cjk = len(CJK.findall(raw))
        info.append("PDF 文本层 %d 字符，汉字 %d" % (len(raw), n_cjk))
        if n_cjk == 0:
            problems.append("PDF 文本层没有汉字：字体或文本层没生成")
        lig = [c for c in LIGATURES if c in raw]
        if lig:
            problems.append("PDF 文本层有 f-连字，检查是否忘了 Ligatures={TeX,NoCommon}")
        for tag in ("[^1]", "<sup>"):
            if tag in raw:
                problems.append("PDF 文本层残留字面 %s：脚注没被正确渲染" % tag)
        if args.footnotes:
            fp = pathlib.Path(args.footnotes)
            if not fp.is_file():
                problems.append("脚注清单不存在：%s" % fp)
            else:
                with open(fp, "r", encoding="utf-8-sig", newline="") as fh:
                    rows = list(csv.DictReader(fh))
                needed = [r for r in rows if r.get("category") == "footnote"
                          and (r.get("marker") or "").isdigit()]
                miss = []
                for r in needed:
                    key = (r.get("zh") or r.get("plain") or "")[:14]
                    key = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", key)).strip()
                    if key and key not in big:
                        miss.append("[^%s] %s…" % (r.get("marker", "?"), key))
                info.append("脚注：清单 %d 条内容脚注，PDF 文本层命中 %d 条"
                            % (len(needed), len(needed) - len(miss)))
                if miss:
                    problems.append("PDF 文本层缺 %d 条脚注内容：%s"
                                    % (len(miss), "；".join(miss[:5])))
                n_placed = (len(re.findall(r"\\footnote\{", tex_text))
                            + len(re.findall(r"\\noindent\\textsuperscript\{", tex_text)))
                if tex_text and n_placed and n_placed < len(needed):
                    problems.append("TeX 里页底脚注与文末编号段落合计 %d 条，少于清单 %d 条内容脚注"
                                    % (n_placed, len(needed)))

    for line in info:
        print("  " + line)
    if problems:
        print("\n[FAIL] PDF 验收 %d 项不通过：" % len(problems))
        for p in problems:
            print("    - " + p)
        return 1
    print("\n[PASS] PDF 验收通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
