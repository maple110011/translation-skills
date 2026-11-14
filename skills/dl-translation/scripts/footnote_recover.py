#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""统一脚注恢复 / 补全 / 核验（两个翻译 skill 共用同一实现）。

主检出源是 MinerU 的 ``content_list.json``（``type=page_footnote``）：版面识别
认得出页底脚注，只是服务端生成 ``full.md`` 时按类型白名单把它们整类过滤了。
PDF 文字层只作**交叉验证**——双栏期刊的脚注排在栏底而非页底，缩进特征会失效，
不能当主源；这一步用来发现「提取包本身被污染」或跨页续文被截断。

典型用法
--------
第 1 步，提取后立刻恢复并自动补回原文 / 译文两侧::

    python scripts/footnote_recover.py _work/extract -o _work \
        --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

填好 ``_work/脚注_待译.csv`` 的 ``zh`` 列后，把中文回填译文::

    python scripts/footnote_recover.py _work/extract -o _work \
        --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check

交付前连 PDF 文本层一起验::

    python scripts/footnote_recover.py _work/extract -o _work \
        --source <stem>_原文.md --target <stem>_zh.md --check --pdf-out <stem>_zh.pdf

只用 Python 标准库；``pdftotext``（poppler / TeX Live）可选，用于交叉验证与 PDF
验收。``--apply`` 会写回 Markdown，写回前自动生成 ``*.bak_footnotes`` 备份。
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys

AFFIL_KEYS = ("University", "Institute", "Department", "Correspondence",
              "Correspondance", "Copyright", "Proceedings", "PMLR", "@")

# 只剥真正的排版标签；`<t.nagler@lmu.de>` 这类邮箱必须保留，否则补回去会丢信息。
TAG_RE = re.compile(r"</?(?:sup|sub|i|b|em|strong|br|span|p|div|u|small)\b[^>]*>", re.I)

HEAD_RE = re.compile(r"(?m)^##\s*脚注\s*$")
DEF_RE = re.compile(r"(?m)^\[\^(\w+)\]:\s*(.*)$")
SUP_NUM_RE = re.compile(r"<sup>\s*(\d{1,3})\s*</sup>")
URL_RE = re.compile(r"https?://[^\s<>\"')，。；]+")
REF_HEAD_RE = re.compile(r"(?m)^##\s*(?:参考文献|REFERENCES|References)\s*$")
PENDING = "<!-- 待译：请填入中文脚注译文 -->"
CSV_FIELDS = ["page", "marker", "category", "text", "plain", "bbox",
              "in_full_md", "in_target", "zh", "in_pdf"]


# ------------------------------------------------------------------ 工具

def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def plain(s):
    return norm(TAG_RE.sub(" ", s or ""))


def page_of(x):
    """page_idx 在不同 MinerU 版本里可能是 int、字符串或缺失。"""
    try:
        return int(x.get("page_idx", 0) or 0) + 1
    except (TypeError, ValueError):
        return 1


def find_content_list(src):
    p = pathlib.Path(src)
    if p.is_file():
        return p
    fs = sorted(f for f in p.rglob("*content_list*.json")
                if "v2" not in f.name.lower())
    if not fs:
        fs = sorted(f for f in p.rglob("*content_list*.json"))
    if not fs:
        raise SystemExit("找不到 content_list.json：%s" % src)
    return fs[0]


def read_content_list(cl):
    data = json.loads(cl.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for k in ("content_list", "pages", "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
        raise SystemExit("content_list.json 结构不认识：%s" % cl.name)
    return data


def parse_footnotes(data):
    rows = []
    for x in data:
        if not isinstance(x, dict) or x.get("type") != "page_footnote":
            continue
        text = str(x.get("text", "") or "")
        m = re.match(r"\s*<sup>\s*(\w{1,4})\s*</sup>\s*", text)
        marker = m.group(1).strip() if m else ""
        body = text[m.end():].strip() if m else text.strip()
        # 机构注里常有多个 <sup>2</sup>；转成纯文本，别把 HTML 字面带进 Markdown/TeX。
        body = norm(TAG_RE.sub(" ", re.sub(r"<sup>\s*(\w{1,4})\s*</sup>", r" \1 ", body)))
        p = plain(body)
        if any(k in p for k in AFFIL_KEYS) and len(p) >= 40:
            category = "affiliation"
        elif marker.isdigit() and len(p) >= 30:
            category = "footnote"
        elif len(p) < 30:
            category = "noise"
        else:
            category = "other"
        rows.append({
            "page": page_of(x),
            "marker": marker,
            "category": category,
            "text": body,
            "plain": p,
            "bbox": json.dumps(x.get("bbox", []), ensure_ascii=False),
            "in_full_md": "no",
            "in_target": "no",
            "zh": "",
            "in_pdf": "",
        })
    rows.sort(key=lambda r: (r["page"], int(r["marker"]) if r["marker"].isdigit() else 999))
    return rows


def load_zh(csv_path, translations):
    """保留已经人工填过的中文译文，重复运行不丢。"""
    out = {}
    for f in (csv_path, translations):
        if not f or not pathlib.Path(f).is_file():
            continue
        with open(f, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                zh = (r.get("zh") or "").strip()
                if zh and zh not in ("TODO", "待译"):
                    out[(str(r.get("page", "")), str(r.get("marker", "")))] = zh
    return out


def write_outputs(rows, outdir, cl):
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "脚注.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})

    lines = ["# MinerU 页底脚注（content_list.json / page_footnote）", "",
             "来源：`%s`" % cl.name,
             "主源为提取包；`--pdf` 的 PDF 文字层仅作交叉验证。", ""]
    for r in rows:
        lines += ["## 第 %s 页 · 脚注 %s · %s" %
                  (r["page"], r["marker"] or "—", r["category"]), "",
                  r["text"], ""]
    (outdir / "脚注_原文.md").write_text("\n".join(lines), encoding="utf-8")

    todo = outdir / "脚注_待译.csv"
    with open(todo, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["page", "marker", "category", "en", "zh"])
        w.writeheader()
        for r in rows:
            # 机构/版权注按原刊信息保留英文，不占 [^n] 编号，也无需中文译文。
            if r["category"] == "footnote":
                w.writerow({"page": r["page"], "marker": r["marker"],
                            "category": r["category"], "en": r["text"],
                            "zh": r["zh"]})
    return csv_path, todo


# ------------------------------------------------------- PDF 文字层交叉验证

def pdf_text(pdf, text_file):
    if text_file:
        return pathlib.Path(text_file).read_text(encoding="utf-8-sig", errors="replace")
    if not pdf:
        return None
    exe = shutil.which("pdftotext")
    if not exe:
        print("  （没有 pdftotext，跳过 PDF 文字层交叉验证）")
        return None
    try:
        r = subprocess.run([exe, "-layout", "-enc", "UTF-8", str(pdf), "-"],
                           capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        print("  （pdftotext 调用失败，跳过交叉验证：%s）" % e)
        return None
    if r.returncode:
        print("  （pdftotext 退出码 %d，跳过交叉验证）" % r.returncode)
        return None
    return r.stdout.decode("utf-8", errors="replace")


def cross_check(rows, raw, outdir):
    if raw is None:
        return
    pages = [norm(p) for p in raw.split("\f")]
    found, missing = [], []
    for r in rows:
        if r["category"] not in ("footnote", "affiliation") or not r["plain"]:
            continue
        key = norm(r["plain"])[:25]
        idx = max(0, r["page"] - 1)
        nearby = " ".join(pages[max(0, idx - 1):idx + 2])
        if key and key in nearby:
            found.append(r)
        else:
            missing.append(r)
    lines = ["# 脚注交叉验证（PDF 文字层）", "",
             "主源 `content_list.json` 共 %d 条内容脚注；PDF 文字层在对应页±1 页内"
             "确认 %d 条。" % (len(found) + len(missing), len(found)), "",
             "> 双栏期刊的脚注排在栏底，`pdftotext -layout` 的缩进特征会变，"
             "未确认**不等于**提取包有错；这一层只用来发现文字层污染、跨页续文截断。", ""]
    if missing:
        lines += ["## 文字层未确认（逐条对照 PDF 目视）", ""]
        for r in missing:
            lines.append("- 第 %s 页脚注 %s：%s" % (r["page"], r["marker"], r["plain"][:90]))
        lines.append("")
    (outdir / "脚注_交叉验证.md").write_text("\n".join(lines), encoding="utf-8")
    print("交叉验证：%d/%d 条在 PDF 文字层确认；未确认 %d 条（见 脚注_交叉验证.md）"
          % (len(found), len(found) + len(missing), len(missing)))


# ------------------------------------------------------------ 原文 / 译文补全

def footnote_lines(rows, side):
    out = []
    for r in rows:
        if r["category"] not in ("footnote", "affiliation"):
            continue
        if r["category"] == "affiliation" or not r["marker"].isdigit():
            # 作者角标 / 版权声明常与正文脚注同号（都叫 1），不能占用 [^n]；
            # 作为原刊信息补成引用块，两侧同步、不破坏编号体系。
            label = ("脚注 %s" % r["marker"]) if r["marker"].isdigit() else "无编号"
            out.append("> 第 %s 页原刊机构／版权信息（%s）：%s"
                       % (r["page"], label, r["text"]))
            continue
        body = (r["zh"] or (r["text"] + " " + PENDING)) if side == "target" else r["text"]
        out.append("[^%s]: 第 %s 页脚注 %s：%s" % (r["marker"], r["page"], r["marker"], body))
    return out


def apply_md(path, rows, side):
    """把脚注节写回 Markdown；两侧插入同样结构，块级对账才不会错位。

    幂等且可更新：已有 `[^n]:` 行按清单重写（这样填好中文译文后能覆盖
    「待译」占位），缺的追加；无编号的机构／版权说明以引用块补入。
    """
    p = pathlib.Path(path)
    if not p.is_file():
        return "找不到 %s（%s）" % (p, side)
    text = p.read_text(encoding="utf-8")
    new_text = SUP_NUM_RE.sub(lambda m: "[^%s]" % m.group(1), text)

    desired, notes = {}, []
    for ln in footnote_lines(rows, side):
        m = re.match(r"\[\^(\w+)\]:", ln)
        if m:
            desired[m.group(1)] = ln
        else:
            notes.append(ln)

    head = HEAD_RE.search(new_text)
    if head:
        end = re.search(r"(?m)^##\s", new_text[head.end():])
        stop = head.end() + (end.start() if end else len(new_text) - head.end())
        block = new_text[head.end():stop]
        seen, out_lines = set(), []
        for ln in block.split("\n"):
            m = re.match(r"^\[\^(\w+)\]:", ln)
            if m and m.group(1) in desired:
                out_lines.append(desired[m.group(1)])
                seen.add(m.group(1))
            else:
                out_lines.append(ln)
        add = [desired[n] for n in desired if n not in seen]
        extras = [n for n in notes if n.strip() and n not in block]
        new_block = "\n".join(out_lines + add + extras).strip("\n") + "\n"
        new_text = new_text[:head.end()] + "\n" + new_block + "\n" + new_text[stop:]
    else:
        section = "## 脚注\n\n" + "\n".join(notes + list(desired.values())) + "\n"
        ref = REF_HEAD_RE.search(new_text)
        if ref:
            new_text = new_text[:ref.start()] + section + "\n" + new_text[ref.start():]
        else:
            new_text = new_text.rstrip() + "\n\n" + section

    if new_text != text:
        bak = p.with_name(p.name + ".bak_footnotes")
        if not bak.exists():
            bak.write_text(text, encoding="utf-8")
        p.write_text(new_text, encoding="utf-8")
        print("  已写回 %s（备份 %s）；%d 条编号定义 + %d 条说明"
              % (p.name, bak.name, len(desired), len(notes)))
    else:
        print("  %s 无需改动" % p.name)
    return None


def scaffold(rows, path):
    out = ["## 脚注", "",
           "> 由 `content_list.json` 的 `page_footnote` 恢复；原文与译文两侧同步补这一节。", ""]
    for r in rows:
        if r["category"] not in ("footnote", "affiliation") or not r["marker"].isdigit():
            continue
        out += ["**第 %s 页脚注 %s**（%s）" % (r["page"], r["marker"], r["category"]),
                "", r["text"], "", "译文：" + (r["zh"] or "TODO"), ""]
    pathlib.Path(path).write_text("\n".join(out), encoding="utf-8")
    print("待补骨架：%s" % path)


# ------------------------------------------------------------------ 内容级验收

def section_of(text):
    m = HEAD_RE.search(text or "")
    if not m:
        return None
    end = re.search(r"(?m)^##\s", text[m.end():])
    return text[m.end():m.end() + (end.start() if end else len(text) - m.end())]


def pdf_out_text(pdf_out):
    exe = shutil.which("pdftotext")
    if not pdf_out or not pathlib.Path(pdf_out).is_file():
        return None
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-enc", "UTF-8", str(pdf_out), "-"],
                           capture_output=True, timeout=300)
        if r.returncode:
            return None
        return r.stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_all(rows, source, target, pdf_out, allow_pending, skip):
    if skip:
        print("  （已显式跳过脚注核对）")
        return [], []
    if not rows:
        print("✓ 脚注核对：清单 0 条")
        return [], []
    problems, warns = [], []
    needed = [r for r in rows if r["category"] == "footnote"
              and r["marker"].isdigit()]
    print("清单：%d 条内容脚注需补（另有 %d 条机构／版权注作说明保留）"
          % (len(needed), sum(1 for r in rows if r["category"] in ("footnote", "affiliation")) - len(needed)))
    if not source and not target:
        warns.append("未指定 --source / --target：只核了清单，没核 Markdown 的补全结果；"
                     "交付前务必补上这两个参数")

    for side, path in (("原文", source), ("译文", target)):
        if not path:
            continue
        p = pathlib.Path(path)
        if not p.is_file():
            problems.append("%s侧文件不存在：%s" % (side, path))
            continue
        text = p.read_text(encoding="utf-8")
        sec = section_of(text)
        if sec is None:
            problems.append("%s缺 `## 脚注` 节：清单有 %d 条页底脚注要补" % (side, len(needed)))
            continue
        defs = {m.group(1): m.group(2) for m in DEF_RE.finditer(sec)}
        for r in needed:
            n = r["marker"]
            if n not in defs:
                problems.append("%s脚注节缺 `[^%s]:` 定义（第 %s 页）" % (side, n, r["page"]))
                continue
            line = defs[n]
            if str(r["page"]) not in line:
                problems.append("%s `[^%s]` 页码不符：应为第 %s 页" % (side, n, r["page"]))
            for u in URL_RE.findall(r["plain"]):
                if u not in line:
                    problems.append("%s `[^%s]` 丢了链接 %s" % (side, n, u[:60]))
            if side == "译文":
                if PENDING in line or "TODO" in line:
                    if not allow_pending:
                        problems.append("译文 `[^%s]` 还是英文待译：填 _work/脚注_待译.csv 的 zh 列后重跑 --apply"
                                        % n)
                elif not re.search(r"[\u4e00-\u9fff]", line):
                    warns.append("译文 `[^%s]` 没有汉字，确认是否为纯链接/代码" % n)
        if re.search(r"<sup>\s*\d", text):
            problems.append("%s仍有字面 `<sup>n</sup>`：交付形态只能是 `[^n]`" % side)
        print("  %s脚注节：%d 条编号定义" % (side, len(defs)))

    if pdf_out:
        raw = pdf_out_text(pdf_out)
        if raw is None:
            problems.append("拿不到译文 PDF 文本层：%s" % pdf_out)
        else:
            # 中文长句在 PDF 文本层里常跨行断开（甚至断在词中间），
            # 两边都去掉所有空白再比对，避免「内容明明在却报丢失」。
            big = re.sub(r"\s+", "", raw)
            for tag in ("[^1]", "<sup>"):
                if tag in raw:
                    problems.append("PDF 文本层残留字面 %s：脚注没被正确渲染" % tag)
            for r in needed:
                key = re.sub(r"\s+", "",
                             re.sub(r"<[^>]+>", "", (r["zh"] or r["plain"])[:14]))
                if key and key not in big:
                    problems.append("PDF 文本层找不到脚注 %s 的内容（%s…）"
                                    % (r["marker"], key))
            print("  PDF 文本层：%d 字符，逐条核 %d 条脚注" % (len(raw), len(needed)))
    return problems, warns


# ----------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="统一脚注恢复 / 补全 / 核验（content_list.json）")
    ap.add_argument("src", help="MinerU 提取目录，或 *_content_list.json")
    ap.add_argument("-o", "--outdir", default=None, help="清单输出目录")
    ap.add_argument("--md", default=None, help="兼容旧用法：等同 --source")
    ap.add_argument("--source", default=None, help="原文提取稿 Markdown")
    ap.add_argument("--target", default=None, help="译文 Markdown")
    ap.add_argument("--pdf", default=None, help="原 PDF，仅作文字层交叉验证")
    ap.add_argument("--text", default=None, help="已导出的 PDF 文字层（代替 --pdf）")
    ap.add_argument("--pdf-out", default=None, help="编译后的译文 PDF，验收脚注是否进文本层")
    ap.add_argument("--apply", action="store_true", help="把脚注节补回原文 / 译文两侧")
    ap.add_argument("--translations", default=None, help="填好 zh 列的 CSV（默认读 _work/脚注_待译.csv）")
    ap.add_argument("--check", action="store_true", help="内容级硬门禁，有缺失返回 1")
    ap.add_argument("--scaffold", default=None, help="另写一份可粘贴的待补脚注节")
    ap.add_argument("--allow-pending", action="store_true", help="允许译文侧留英文待译（不推荐）")
    ap.add_argument("--skip-footnote-check", action="store_true",
                    help="仅纯 Markdown 输入、没有 MinerU 结果包时显式跳过")
    args = ap.parse_args(argv)

    cl = find_content_list(args.src)
    rows = parse_footnotes(read_content_list(cl))
    outdir = pathlib.Path(args.outdir) if args.outdir else cl.parent
    outdir.mkdir(parents=True, exist_ok=True)
    # 必须先读回已填过的中文，再写清单；否则 write_outputs 会把待译 CSV 清空。
    zh_map = load_zh(outdir / "脚注.csv",
                     args.translations or (outdir / "脚注_待译.csv"))
    for r in rows:
        r["zh"] = zh_map.get((str(r["page"]), str(r["marker"])), "")
    csv_path, todo = write_outputs(rows, outdir, cl)

    full = cl.parent / "full.md"
    full_text = norm(full.read_text(encoding="utf-8")) if full.exists() else ""
    src_text = norm(pathlib.Path(args.source or args.md).read_text(encoding="utf-8")) \
        if (args.source or args.md) and pathlib.Path(args.source or args.md).is_file() else ""
    tgt_text = norm(pathlib.Path(args.target).read_text(encoding="utf-8")) \
        if args.target and pathlib.Path(args.target).is_file() else ""
    for r in rows:
        key = norm(r["plain"])[:30]
        r["in_full_md"] = "yes" if key and key in full_text else "no"
        r["in_target"] = "yes" if key and (key in src_text or key in tgt_text) else "no"
    print("提取包：%s" % cl.name)
    counts = {}
    for r in rows:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    print("page_footnote 共 %d 条：%s" %
          (len(rows), "、".join("%s %d" % kv for kv in sorted(counts.items()))))
    print("清单：%s / %s" % (csv_path, todo))

    raw = pdf_text(args.pdf, args.text)
    cross_check(rows, raw, outdir)

    if args.scaffold:
        scaffold(rows, args.scaffold)

    if args.apply:
        print("补回脚注节：")
        for side, path in (("source", args.source or args.md), ("target", args.target)):
            if path:
                err = apply_md(path, rows, side)
                if err:
                    print("  [!] " + err)
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in CSV_FIELDS})

    problems, warns = [], []
    if args.check:
        problems, warns = check_all(rows, args.source or args.md, args.target,
                                    args.pdf_out, args.allow_pending,
                                    args.skip_footnote_check)
        for w in warns:
            print("  [!] " + w)
        if problems:
            print("\n[FAIL] 脚注核对 %d 项不通过：" % len(problems))
            for p in problems[:20]:
                print("    - " + p)
            if len(problems) > 20:
                print("    ... 另有 %d 项" % (len(problems) - 20))
        else:
            print("\n[PASS] 脚注核对通过")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
