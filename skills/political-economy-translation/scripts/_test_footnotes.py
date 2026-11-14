#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_wechat.py 脚注形态回归测试。

覆盖上游可能出现的每一种脚注写法，确认「该进的进、该炸的炸」：
      python scripts/_test_footnotes.py
退出码 0 = 全过。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "build_wechat.py")

FRONT = """---
title: "Test Paper"
authors: ["A. Author"]
year: 2024
journal: "Review of Political Economy"
translator: "某甲"
---

"""


def run(md: str, workdir: str):
    src = os.path.join(workdir, "in.md")
    open(src, "w", encoding="utf-8").write(md)
    outdir = os.path.join(workdir, "out")
    r = subprocess.run([sys.executable, SCRIPT, src, outdir],
                       capture_output=True, text=True, encoding="utf-8")
    html = ""
    p = os.path.join(outdir, "wechat_article.html")
    if os.path.isfile(p):
        html = open(p, encoding="utf-8").read()
    return r.returncode, r.stdout + r.stderr, html


def count(html, s):
    return html.count(s)


# 每条用例：(名称, 正文, 期望出现的脚注正文列表, 期望残留字面 [^n] 的处数)
CASES = [
    ("有序列表 1. 写法（曾经崩 TypeError）", """这是正文第一段，带一条脚注。<sup>1</sup>

这是第二段，带第二条。<sup>2</sup>

## 脚注

1. 这是脚注正文一。
2. 这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("Pandoc [^n] + [^n]: 定义（footnotes.py --patch 的产出）", """这是正文第一段，带一条脚注。[^1]

这是第二段，带第二条。[^2]

## 脚注

[^1]: 这是脚注正文一。
[^2]: 这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("[^n]: 定义贴在文末、没有 ## 脚注 标题", """这是正文第一段。[^1]

<!-- FOOTNOTES-RECOVERED -->

[^1]: 这是脚注正文一。
""", ["这是脚注正文一"], 0),

    ("中文括号编号 (1) 与全角 1．", """正文甲。<sup>1</sup>

正文乙。<sup>2</sup>

## 注释

(1) 这是脚注正文一。
1．这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("注 1 前缀", """正文甲。<sup>1</sup>

## 脚注

注 1　这是脚注正文一。
注 2　这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("节内条目自带 <sup>n</sup> 前缀", """正文甲。<sup>1</sup>

## 脚注

<sup>1</sup> 这是脚注正文一。
<sup>2</sup> 这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("无序列表条目按次序顺延编号", """正文甲。<sup>1</sup>

正文乙。<sup>2</sup>

## 脚注

- 这是脚注正文一。
- 这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("一条脚注折成多行（英文断词）", """正文甲。<sup>1</sup>

## 脚注

1. This is a long footnote that wraps across several
   physical lines in the markdown source and ends with a
   hyphenated word Kaldor-
   Verdoorn.
""", ["Kaldor-Verdoorn"], 0),

    ("英文标题 ## Notes", """Body with a note.<sup>1</sup>

## Notes

1. English footnote body here.
""", ["English footnote body here"], 0),

    ("混合形态：正文 [^1]，定义写 1. 列表", """正文甲。[^1]

正文乙。[^2]

## 脚注

1. 这是脚注正文一。
2. 这是脚注正文二。
""", ["这是脚注正文一", "这是脚注正文二"], 0),

    ("Unicode 上标正文标记 ¹（且确有同号定义）", """正文甲。\u00b9

## 脚注

1. 这是脚注正文一。
""", ["这是脚注正文一"], 0),

    ("脚注正文里带公式与粗体，不该被解析坏", """正文甲。<sup>1</sup>

## 脚注

1. 参见 **马克思**（1867），公式 $v = \\frac{c}{v}$ 处。
""", ["参见"], 0),

    ("多条脚注挤在同一段、无空行", """正文甲。<sup>1</sup>

## 脚注

1. 这是脚注正文一。
2. 这是脚注正文二。
3. 这是脚注正文三。
""", ["这是脚注正文一", "这是脚注正文二", "这是脚注正文三"], 0),
]

FAIL_CASES = [
    ("正文有 [^1] 但整篇没有脚注定义 → 必须提醒不静默", """正文甲。[^1]

正文乙。
""", None),
]


def main():
    root = tempfile.mkdtemp(prefix="fn_test_")
    ok, bad = 0, []
    try:
        for idx, (name, body, musts, max_literal) in enumerate(CASES, 1):
            wd = os.path.join(root, f"c{idx}")
            os.makedirs(wd)
            code, out, html = run(FRONT + body, wd)
            problems = []
            if code != 0:
                problems.append(f"退出码 {code}；输出：{out.strip()[:300]}")
            for m in musts or []:
                if count(html, m) == 0:
                    problems.append(f"版面里找不到「{m}」")
            lit = len(re.findall(r"\[\^\d+\]", html))
            if lit > max_literal:
                problems.append(f"残留 {lit} 处字面 [^n]")
            if "<sup>" in html.lower():
                problems.append("残留裸 <sup> 标签")
            if problems:
                bad.append((name, problems))
            else:
                ok += 1
                print(f"  ✓ {idx:>2}. {name}")

        for name, body, _ in FAIL_CASES:
            wd = os.path.join(root, "fail")
            os.makedirs(wd, exist_ok=True)
            code, out, html = run(FRONT + body, wd)
            warned = "找不到对应标记" in out or "没有对应" in out
            if code == 0 and warned:
                ok += 1
                print(f"  ✓  !. {name}")
            else:
                bad.append((name, [f"退出码 {code}，提醒={warned}",
                                   out.strip()[:300]]))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print()
    if bad:
        print(f"失败 {len(bad)} 条：")
        for name, problems in bad:
            print(f"  ✗ {name}")
            for p in problems:
                print(f"      - {p}")
        return 1
    print(f"全部通过（{ok} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
