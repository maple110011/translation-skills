#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""图片版式归一：把 MinerU 拆散的多联图合成一张，并按原刊尺寸给宽度。

MinerU 会把一张多联图（Figure 6 的"左／中／右"三栏）识别成三个独立的
``image`` 块，``full.md`` 里就是三条 ``![图 6 左：…](images/a.jpg)``。照着
逐条渲染，PDF 里就成了三张各自接近满页宽的图，图注也被拆在三处——原文是
一行的三联图，译文却占了整页。

本脚本以 ``content_list.json`` 的 ``bbox`` 为准做两件事：

1. **分组**：同页、竖直区间重叠超过一半的图片属于同一联图（同一行）。把 md 里
   这几条图片行合并成**一行** ``![](a) ![](b) ![](c)``，``md2tex.py`` 会把它
   排成一行的 minipage；组内被 MinerU 单独抽出来的子图标签（"含类别特征"、
   "归一化 ROC AUC"）收成一行小字留在图与图注之间，不丢信息。
2. **量宽**：每张图的原始宽度占正文栏宽的比例 ``w / 栏宽``。写进
   ``_work/图片版式.csv``，``md2tex.py --fig-meta`` 读它来决定
   ``width=N\linewidth``——附录里那些原刊只占半栏的图，不会再被拉满整栏。

只处理"多块拼成一张图"和"宽度"两件事；图片内容、图注文字、编号都不动。
`<table><td>` 形式的多联图（本 skill 的另一种写法）已经是一行，跳过。

用法::

    python scripts/figure_layout.py _work/extract -o _work --md <stem>_zh.md --apply
    python scripts/md2tex.py <stem>_zh.md out.tex --fig-meta _work/图片版式.csv --pdf
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import statistics
import sys

IMG_TYPES = ("image", "chart")
IMG_LINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# 组内夹着的子图标签不会以这些开头；以它们开头的行说明这一组到头了
NOT_LABEL_RE = re.compile(r"^(?:!\[|#|\||>|\*\*(?:图|表)\s*\d|(?:图|表)\s*\d+\s*[.．、:：])")
FIELDS = ["page", "group", "path", "x0", "x1", "width_frac", "caption"]


def page_of(x):
    try:
        return int(x.get("page_idx", 0) or 0) + 1
    except (TypeError, ValueError):
        return 1


def find_content_list(src):
    p = pathlib.Path(src)
    if p.is_file():
        return p
    fs = sorted(f for f in p.rglob("*content_list*.json") if "v2" not in f.name.lower())
    if not fs:
        fs = sorted(p.rglob("*content_list*.json"))
    if not fs:
        raise SystemExit("找不到 content_list.json：%s" % src)
    return fs[0]


def read_items(cl):
    data = json.loads(cl.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("content_list", "pages", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
        raise SystemExit("content_list.json 结构不认识：%s" % cl.name)
    return data


def load_layout(items):
    """图片块 → 记录；同时算出每页的正文栏宽（文本块宽度中位数）。"""
    texts_by_page, imgs = {}, []
    for x in items:
        if not isinstance(x, dict) or not x.get("bbox"):
            continue
        b = x["bbox"]
        if len(b) < 4:
            continue
        if x.get("type") == "text":
            texts_by_page.setdefault(page_of(x), []).append(b[2] - b[0])
        elif x.get("type") in IMG_TYPES and x.get("img_path"):
            cap = x.get("image_caption") or x.get("img_caption") or []
            if isinstance(cap, str):
                cap = [cap]
            imgs.append({
                "page": page_of(x),
                "path": str(x["img_path"]),
                "bbox": [float(v) for v in b[:4]],
                "cap": re.sub(r"\s+", " ", " ".join(cap)).strip(),
            })
    allw = [w for v in texts_by_page.values() for w in v if w > 250]
    col_all = statistics.median(allw) if allw else 600.0
    for im in imgs:
        # 每页用最宽的那个文本块当栏宽。中位数在只有标题、轴标签的页面上会
        # 被几十磅的字宽带偏（Appendix 页尤其明显），最宽块才接近正文栏宽。
        ws = [w for w in texts_by_page.get(im["page"], []) if w > 100]
        col_page = max(ws) if ws else col_all
        if col_page < 0.6 * col_all:
            col_page = col_all
        im["col"] = col_page
        im["frac"] = min(1.0, max(0.12, (im["bbox"][2] - im["bbox"][0]) / col_page))
    imgs.sort(key=lambda i: (i["page"], i["bbox"][0]))
    return imgs, texts_by_page


def group_rows(imgs):
    """同页且竖直重叠过半的图并成一组（= 原刊里的一行多联图）。"""
    gid, groups = 0, {}
    for im in imgs:
        y0, y1 = im["bbox"][1], im["bbox"][3]
        hit = None
        for g, members in groups.items():
            if members[0]["page"] != im["page"]:
                continue
            ly0 = min(m["bbox"][1] for m in members)
            ly1 = max(m["bbox"][3] for m in members)
            ov = min(y1, ly1) - max(y0, ly0)
            if ov > 0.5 * min(y1 - y0, ly1 - ly0):
                hit = g
                break
        if hit is None:
            gid += 1
            hit = gid
            groups[hit] = []
        groups[hit].append(im)
        im["group"] = hit
    for members in groups.values():
        members.sort(key=lambda m: m["bbox"][0])
        for m in members:
            m["group"] = "%d-%d" % (m["page"], m["group"])
    return imgs


def subplot_labels(items, page, y0, y1):
    """同一页、落在图片组竖直范围内的短文本块 = 子图标题／坐标轴标题。"""
    out = []
    for x in items:
        if x.get("type") != "text" or page_of(x) != page or not x.get("bbox"):
            continue
        b = x["bbox"]
        cy = (b[1] + b[3]) / 2
        txt = re.sub(r"\s+", " ", str(x.get("text", ""))).strip()
        if not txt or len(txt) > 60:
            continue
        if y0 - 34 <= cy <= y1 + 34:
            out.append(txt)
    return out


def md_image_lines(lines):
    """md 里每条图片行的信息：(行号, [(alt, path), ...], 路径 basename 列表)。"""
    out = []
    for i, ln in enumerate(lines):
        figs = IMG_LINE_RE.findall(ln)
        if figs:
            out.append((i, figs, [pathlib.PurePosixPath(p.replace("\\", "/")).name
                                  for _a, p in figs]))
    return out


def already_grouped(lines, first, last):
    """这一段是不是已经包在 <table> 里（本 skill 的另一种多联图写法）。"""
    lo = max(0, first - 8)
    return any("<table" in lines[k].lower() for k in range(lo, last + 1))


def merge_group(lines, span, labels):
    """把 span 段（含首尾图片行）换成一行多图 + 一行子图标签。"""
    first, last = span[0][0], span[-1][0]
    # 最后一张图后面紧跟的短行（子图坐标轴标题常落在图注上方）也吃进来，
    # 否则它们会孤零零留在图与图注之间。遇到空行、图注、标题就停。
    k = last + 1
    while k < len(lines):
        txt = lines[k].strip()
        if not txt or NOT_LABEL_RE.match(txt) or len(txt) > 60:
            break
        last = k
        k += 1
    figs, labels_found = [], []
    for idx in range(first, last + 1):
        ln = lines[idx]
        got = IMG_LINE_RE.findall(ln)
        if got:
            figs.extend(got)
            continue
        txt = ln.strip()
        if not txt:
            continue
        if NOT_LABEL_RE.match(txt) or len(txt) > 60:
            return None, [], last
        labels_found.append(txt)
    if len(figs) < 2:
        return None, [], last
    out = [" ".join("![%s](%s)" % (a, p) for a, p in figs)]
    wanted = [l for l in labels if l in labels_found]
    rest = [l for l in labels_found if l not in wanted]
    keep = []
    for l in wanted + rest:
        if not keep or keep[-1] != l:
            keep.append(l)
    if keep:
        out += ["", "　".join(keep)]
    return out, figs, last


def main(argv=None):
    ap = argparse.ArgumentParser(description="多联图合并 + 按原刊比例定宽")
    ap.add_argument("src", help="MinerU 提取目录，或 *_content_list.json")
    ap.add_argument("-o", "--outdir", default=None, help="图片版式.csv 输出目录")
    ap.add_argument("--md", required=True, help="译文 Markdown")
    ap.add_argument("--apply", action="store_true", help="把多联图合并成一行写回 md")
    args = ap.parse_args(argv)

    cl = find_content_list(args.src)
    items = read_items(cl)
    imgs, _ = load_layout(items)
    group_rows(imgs)
    outdir = pathlib.Path(args.outdir) if args.outdir else cl.parent
    outdir.mkdir(parents=True, exist_ok=True)

    md = pathlib.Path(args.md)
    lines = md.read_text(encoding="utf-8").split("\n")
    by_name = {}
    for im in imgs:
        by_name.setdefault(pathlib.PurePosixPath(im["path"].replace("\\", "/")).name, []).append(im)

    # 1) 版式清单：md 里出现的每张图，配原刊宽度
    rows, missing = [], []
    for _i, figs, names in md_image_lines(lines):
        for (alt, path), name in zip(figs, names):
            cand = by_name.get(name)
            if not cand:
                missing.append(name)
                continue
            im = cand[0]
            rows.append({"page": im["page"], "group": im["group"], "path": path,
                         "x0": "%.0f" % im["bbox"][0], "x1": "%.0f" % im["bbox"][2],
                         "width_frac": "%.3f" % im["frac"],
                         "caption": im["cap"] or alt})
    layout_csv = outdir / "图片版式.csv"
    if rows:
        with open(layout_csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    # 2) 合并多联图
    spans, cur = [], []
    for rec in md_image_lines(lines):
        idx = rec[0]
        if cur and idx - cur[-1][0] > 12:
            spans.append(cur)
            cur = []
        cur.append(rec)
    if cur:
        spans.append(cur)

    changed, merged = list(lines), 0
    for span in sorted(spans, key=lambda s: -s[0][0]):
        if len(span) < 2:
            continue
        if already_grouped(lines, span[0][0], span[-1][0]):
            print("  · 第 %d–%d 行已是 <table> 多联图，跳过"
                  % (span[0][0] + 1, span[-1][0] + 1))
            continue
        first = span[0][0]
        page = None
        y0, y1 = None, None
        for _i, _f, names in span:
            im = by_name.get(names[0], [None])[0]
            if im:
                page = im["page"]
                y0 = im["bbox"][1] if y0 is None else min(y0, im["bbox"][1])
                y1 = im["bbox"][3] if y1 is None else max(y1, im["bbox"][3])
        labels = subplot_labels(items, page, y0, y1) if page else []
        rep, figs, last = merge_group(changed, span, labels)
        if not rep:
            continue
        changed[first:last + 1] = rep
        merged += 1
        print("  ✓ 第 %d–%d 行：%d 张图合成一行%s"
              % (first + 1, last + 1, len(figs), ("，保留子图标签" if len(rep) > 1 else "")))

    print("图片版式：%d 张图、%d 个多联图组合并；清单 %s"
          % (len(rows), merged, layout_csv))
    if missing:
        print("  [!] %d 张图在提取包里找不到对应 bbox（宽度沿用默认）：%s"
              % (len(missing), "、".join(missing[:4])))
    narrow = [r for r in rows if float(r["width_frac"]) < 0.75]
    if narrow:
        print("  原刊宽度不足整栏 75%% 的图 %d 张（md2tex --fig-meta 会按此收窄）：%s"
              % (len(narrow), "、".join("%s %.0f%%" % (pathlib.PurePosixPath(r["path"]).name[:8],
                                                      float(r["width_frac"]) * 100)
                                        for r in narrow[:6])))

    if args.apply and changed != lines:
        bak = md.with_name(md.name + ".bak_figures")
        if not bak.exists():
            bak.write_text("\n".join(lines), encoding="utf-8")
        md.write_text("\n".join(changed), encoding="utf-8")
        print("已写回 %s（备份 %s）" % (md.name, bak.name))
    elif args.apply:
        print("%s 无需改动" % md.name)
    else:
        print("（未加 --apply，只出了清单）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
