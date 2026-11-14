#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「人的意见」落成改动：回填术语表、改译文、重跑校验、记下已决条目。

人在 待校对.md 里写意见，agent 把意见翻成一张决定表（CSV），本脚本负责执行：

    python scripts/review_apply.py --target 译文.md --glossary _work/x_术语.csv \
        --decisions _work/x_决定.csv --resolved _work/x_已决定.csv \
        --source 原文.md --manifest _work/x_待校对.md --suggest _work/x_候选建议.csv

决定表列：`键,动作,旧,新,说明`
    键    term:<原文> | text:<位置> | candidate:<原文> | manual:<原文>
    动作  term   改术语表译法（旧非空时顺带替换译文）
          text   只替换译文（旧→新）
          accept 候选术语收进表（新＝译法）
          drop   候选术语不收
          keep   维持现状，仅登记

脚本不做判断，只做执行。任何一条改不动，都停下来报出来，不静默跳过。
"""
import argparse
import csv
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load_glossary(path):
    rows = read_csv(path)
    if not rows:
        return [], ["src", "dst", "note"]
    fields = list(rows[0].keys())
    return rows, fields


def apply_glossary(path, rows, fields, key, new_dst, note=""):
    key_l = key.strip().lower()
    for r in rows:
        if (r.get("src") or "").strip().lower() == key_l:
            r["dst"] = new_dst
            if note and "note" in fields:
                r["note"] = note
            write_csv(path, rows, fields)
            return "updated"
    row = {f: "" for f in fields}
    row["src"] = key
    row["dst"] = new_dst
    if "note" in fields:
        row["note"] = note
    rows.append(row)
    write_csv(path, rows, fields)
    return "added"


def main(argv=None):
    ap = argparse.ArgumentParser(description="执行校对决定：改术语表、改译文、重跑校验")
    ap.add_argument("--target", required=True, help="译文 Markdown")
    ap.add_argument("--glossary", required=True, help="项目术语表 CSV")
    ap.add_argument("--decisions", required=True, help="决定表 CSV：键,动作,旧,新,说明")
    ap.add_argument("--resolved", default="", help="已决定清单 CSV（追加写入）")
    ap.add_argument("--source", default="", help="原文，用于重跑对账")
    ap.add_argument("--manifest", default="", help="重跑后把清单写到这里")
    ap.add_argument("--manual", default="", help="人工待校 CSV")
    ap.add_argument("--suggest", default="", help="候选术语建议 CSV")
    ap.add_argument("--marx", default="", help="马恩引文 CSV，重生成清单时透传")
    ap.add_argument("--marx-note", default="", help="引文核查备注 CSV，重生成清单时透传")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不落盘")
    args = ap.parse_args(argv)

    decisions = read_csv(args.decisions)
    if not decisions:
        sys.exit("决定表是空的。")

    text = open(args.target, encoding="utf-8").read()
    gloss, gfields = load_glossary(args.glossary)

    log, problems = [], []
    for d in decisions:
        key = (d.get("键") or "").strip()
        act = (d.get("动作") or "").strip().lower()
        old = (d.get("旧") or "").strip()
        new = (d.get("新") or "").strip()
        why = (d.get("说明") or "").strip()
        if not key or not act:
            problems.append(f"缺字段：{d}")
            continue

        kind, _, name = key.partition(":")
        name = name.strip()

        if act in ("term", "accept"):
            if not new:
                problems.append(f"{key}：改译法却没给「新」")
                continue
            if not args.dry_run:
                state = apply_glossary(args.glossary, gloss, gfields, name, new, why)
                log.append(f"[术语表{ '更新' if state=='updated' else '新增' }] {name} → {new}")
            if old and old != new:
                n = text.count(old)
                if n == 0:
                    problems.append(f"{key}：译文里找不到「{old}」，未替换")
                else:
                    text = text.replace(old, new)
                    log.append(f"[译文] {old} → {new}（{n} 处）")

        elif act == "text":
            if not old or not new:
                problems.append(f"{key}：替换需要「旧」和「新」")
                continue
            n = text.count(old)
            if n == 0:
                problems.append(f"{key}：译文里找不到要替换的句子：{old[:30]}…")
                continue
            text = text.replace(old, new)
            log.append(f"[译文] 替换 {n} 处：{old[:24]}… → {new[:24]}…")

        elif act == "drop":
            log.append(f"[候选不收] {name}")
        elif act == "keep":
            log.append(f"[维持现状] {name}")
        else:
            problems.append(f"{key}：未知动作 {act}")

    if args.dry_run:
        print("\n".join(log))
        if problems:
            print("\n问题：\n" + "\n".join("  " + p for p in problems))
        return 1 if problems else 0

    open(args.target, "w", encoding="utf-8").write(text)

    if args.resolved:
        exists = os.path.exists(args.resolved)
        rows = read_csv(args.resolved) if exists else []
        fields = ["键", "动作", "说明"]
        for d in decisions:
            rows.append({"键": (d.get("键") or "").strip(),
                         "动作": (d.get("动作") or "").strip(),
                         "说明": (d.get("说明") or "").strip()})
        write_csv(args.resolved, rows, fields)
        log.append(f"[已决] {len(decisions)} 条 → {args.resolved}")

    # 重跑机械校验：改完不验，等于没改
    checks = []
    if args.source:
        for args_ in (["--inplace", args.target],):
            r = subprocess.run([sys.executable, os.path.join(HERE, "normalize_math.py")] + args_,
                               capture_output=True, text=True, encoding="utf-8")
            checks.append(("公式归一", r.returncode == 0, (r.stdout or "").strip().splitlines()[-1:]))
        r = subprocess.run([sys.executable, os.path.join(HERE, "fidelity_check.py"),
                            args.source, args.target, "--glossary", args.glossary,
                            "--strict"],
                           capture_output=True, text=True, encoding="utf-8")
        tail = [l for l in (r.stdout or "").splitlines() if l.startswith(("✓", "✗", "结论"))]
        checks.append(("结构对账", r.returncode == 0, tail))

    print("\n".join(log))
    if checks:
        print()
        for name, ok, lines in checks:
            print(f"{'✓' if ok else '✗'} {name}")
            for l in lines:
                print("   " + l)
    if problems:
        print("\n没改成的（需人工处理）：")
        for p in problems:
            print("  " + p)

    # 清单重生成：已决条目自动消失
    if args.manifest and args.source:
        cmd = [sys.executable, os.path.join(HERE, "review_queue.py"),
               args.source, args.target, "--glossary", args.glossary,
               "-o", args.manifest]
        if args.manual:
            cmd += ["--manual", args.manual]
        if args.suggest:
            cmd += ["--suggest", args.suggest]
        if args.resolved:
            cmd += ["--resolved", args.resolved]
        if args.marx:
            cmd += ["--marx", args.marx]
        if args.marx_note:
            cmd += ["--marx-note", args.marx_note]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        print("\n" + (r.stdout or "").strip())
        if r.returncode:
            print(r.stderr)

    failed = [name for name, ok, _ in checks if not ok]
    if failed:
        print("\n[!] 回填后重跑校验未通过：" + "、".join(failed) + "；修好再交付，别当展示信息看。")
    return 1 if problems or failed else 0


if __name__ == "__main__":
    sys.exit(main())
