#!/usr/bin/env python3
"""Check that every formula in the source survived into the target intact.

Why this is a separate script
-----------------------------
`fidelity_check.py` counts blocks and citations. It can see that a display
formula is still there, not that its content changed — and in a paper, the
content of a formula *is* the paper. A dropped subscript, `\\|x\\|` rendered as
`|x|`, `\\sigma^2` written as `\\sigma`, `\\le` softened to `<`: each is a
one-character edit that silently changes the statement, and none of them is
visible to a block-level audit.

What is compared
----------------
Every math span (display and inline) is extracted from both files by
`mathscan.py`, aligned in order, and compared with whitespace collapsed and
nothing else. So ``x^2`` vs ``x^{2}`` counts as a change (it is not the same
LaTeX), while a re-indented multi-line block does not.

Differences are classified:

    text  only the prose inside ``\\text{...}`` differs — usually a translated
          word label. Allowed with ``--allow-text-only``, otherwise reported.
    near  ≤ --near characters differ: a typo, an altered accent, a flipped
          subscript. Treated as an error; the label just says why it matters.
    diff  anything bigger. Error.

Usage
-----
    python math_fidelity.py 原文.md 译文_zh.md
    python math_fidelity.py 原文.md 译文_zh.md --csv _work/公式差异.csv --strict
"""

from __future__ import annotations

import argparse
import csv
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathscan import canon, scan, strip_notation, strip_text_bodies  # noqa: E402

try:                                    # console may be cp936: never die on ✓
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

TAG = re.compile(r"\\tag\*?\{([^{}]*)\}")
LABEL = re.compile(r"\\label\{([^{}]*)\}")
REF = re.compile(r"\\(?:eq)?ref\{([^{}]*)\}")


# --------------------------------------------------------------------------
def align(a, b):
    """Pair up the two span lists, tolerating a missing or extra formula.

    Positional comparison would report every formula after the first dropped
    one as changed. Aligning first means one missing equation costs one line in
    the report instead of forty.
    """
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs.extend((i1 + k, j1 + k) for k in range(i2 - i1))
        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                pairs.append((i1 + k if i1 + k < i2 else None,
                              j1 + k if j1 + k < j2 else None))
        elif tag == "delete":
            pairs.extend((i, None) for i in range(i1, i2))
        else:
            pairs.extend((None, j) for j in range(j1, j2))

    # 语序调整不是公式错误。中文常把条件前置、把"随 n 增大"挪到句尾，
    # 同一个式子因此换了位置；SequenceMatcher 会把它报成一"缺"一"多"，
    # 看上去像漏译。这里把双方都落单、且内容完全相同的配对回来。
    free_t = {}
    for i, j in pairs:
        if i is None and j is not None:
            free_t.setdefault(b[j], []).append(j)
    moved, fixed = set(), []
    for i, j in pairs:
        if j is None and i is not None and free_t.get(a[i]):
            jj = free_t[a[i]].pop(0)
            fixed.append((i, jj))
            moved.add((i, jj))
        else:
            fixed.append((i, j))
    return fixed, moved


def char_diff(a, b, width=16):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            seg = a[i1:i2]
            out.append(seg if len(seg) <= 2 * width else seg[:width] + "…" + seg[-width:])
        elif tag == "replace":
            out.append(f"[-{a[i1:i2]}-]{{+{b[j1:j2]}+}}")
        elif tag == "delete":
            out.append(f"[-{a[i1:i2]}-]")
        else:
            out.append(f"{{+{b[j1:j2]}+}}")
    s = "".join(out)
    return s if len(s) <= 400 else s[:400] + "…"


def snippet(text, start, end, width=45):
    left = re.sub(r"\s+", " ", text[max(0, start - width):start]).strip()
    right = re.sub(r"\s+", " ", text[end:end + width]).strip()
    return f"…{left} ⟦式⟧ {right}…"


def unbalanced_dollars(text, skip=("\\$",)):
    """Lines with an odd number of unescaped `$` — a delimiter is missing."""
    bad = []
    for i, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("$$") and line.rstrip().endswith("$$") and line.count("$") % 2 == 0:
            continue
        n = 0
        j = 0
        while j < len(line):
            if line[j] == "\\":
                j += 2
                continue
            if line[j] == "$":
                n += 1
            j += 1
        if n % 2 == 1:
            bad.append((i, line.strip()[:70]))
    return bad


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="逐条比对原文与译文中的公式。")
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--csv", default="", help="把差异写成 CSV，供审校清单使用")
    ap.add_argument("--max", type=int, default=25, help="控制台最多列出多少条差异")
    ap.add_argument("--near", type=int, default=3, help="差异字符数不超过此值时标为「微差」")
    ap.add_argument("--allow-text-only", action="store_true",
                    help="把 \\text{} 内的文字差异视为可接受（默认仍列出）")
    ap.add_argument("--strict", action="store_true", help="有差异时返回码 1")
    args = ap.parse_args(argv)

    with open(args.source, "r", encoding="utf-8") as fh:
        src = fh.read()
    with open(args.target, "r", encoding="utf-8") as fh:
        raw_tgt = fh.read()
    # The notation table carries formulas too (`$n$`, `$\mathcal{R}(\hat f)$`
    # …). They are not translations of anything in the source, so counting them
    # would report every table row as an extra formula.
    tgt = strip_notation(raw_tgt)
    notation_spans = len(scan(raw_tgt)) - len(scan(tgt))

    s_spans, t_spans = scan(src), scan(tgt)
    s_txt = [s.text for s in s_spans]
    t_txt = [t.text for t in t_spans]

    same = text_only = near = diff = missing = extra = 0
    kind_drift = []
    rows = []

    pairs, moved = align(s_txt, t_txt)
    reorder = 0

    for i, j in pairs:
        if i is None:
            extra += 1
            rows.append({
                "序号": f"+{j + 1}", "类型": "多出", "源行": "",
                "相似度": "", "原文式": "", "译文式": t_txt[j],
                "源上下文": "", "说明": "译文中多出一处原文没有的公式",
            })
            continue
        if j is None:
            missing += 1
            rows.append({
                "序号": f"-{i + 1}", "类型": "缺失", "源行": s_spans[i].line,
                "相似度": "", "原文式": s_txt[i], "译文式": "",
                "源上下文": snippet(src, s_spans[i].start, s_spans[i].end),
                "说明": "原文的公式在译文里没有对应",
            })
            continue

        a, b = s_txt[i], t_txt[j]
        if a == b:
            same += 1
            if (i, j) in moved:
                reorder += 1
            if s_spans[i].kind != t_spans[j].kind:
                kind_drift.append((s_spans[i], t_spans[j]))
            continue

        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        ratio = sm.ratio()
        nchar = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes()
                    if tag != "equal")
        if strip_text_bodies(a) == strip_text_bodies(b):
            text_only += 1
            typ, note = "文内文字不同", "仅 \\text{} 里的说明文字不同，公式主体一致"
        elif nchar <= args.near:
            near += 1
            typ, note = "微差", "只差一两个字符：上下标、重音、不等号方向都要核对"
        else:
            diff += 1
            typ, note = "内容不同", "公式主体被改写"
        rows.append({
            "序号": f"{i + 1}", "类型": typ, "源行": s_spans[i].line,
            "相似度": f"{ratio:.3f}", "原文式": a, "译文式": b,
            "源上下文": snippet(src, s_spans[i].start, s_spans[i].end),
            "说明": note,
        })

    errors = [r for r in rows if r["类型"] in ("缺失", "多出", "内容不同", "微差")]
    if not args.allow_text_only:
        errors += [r for r in rows if r["类型"] == "文内文字不同"]

    # equation numbering, labels and cross-references
    tags_s = [t for s in s_spans for t in TAG.findall(s.body)]
    tags_t = [t for s in t_spans for t in TAG.findall(s.body)]
    labs_s = {x for s in s_spans for x in LABEL.findall(s.body)}
    labs_t = {x for s in t_spans for x in LABEL.findall(s.body)}
    refs_t = {x for x in REF.findall(tgt)}

    print(f"文件：{args.target}")
    print(f"  公式：源 {len(s_spans)} 处（行间 {sum(s.kind == 'display' for s in s_spans)}、"
          f"行内 {sum(s.kind == 'inline' for s in s_spans)}）")
    print(f"        译 {len(t_spans)} 处（行间 {sum(s.kind == 'display' for s in t_spans)}、"
          f"行内 {sum(s.kind == 'inline' for s in t_spans)}）")
    print(f"  逐字一致：{same}　文内文字不同：{text_only}　微差：{near}　内容不同：{diff}　"
          f"缺失：{missing}　多出：{extra}")
    if reorder:
        # 不是错误：同一批公式都在，只是句内顺序不同。但要报出来——若某处
        # 有十几处「顺序不同」，多半是整段被重排了，那不是翻译是改写。
        print(f"  （其中 {reorder} 处仅位置调整：公式相同、句内语序不同，不计入差异）")
    if notation_spans:
        print(f"  （符号一览里的 {notation_spans} 处公式不计入比对）")

    if len(s_spans) == len(t_spans):
        print("  [OK] 公式数量一致")
    else:
        print(f"  [XX] 公式数量不一致：源 {len(s_spans)}，译 {len(t_spans)}")

    for s, t in kind_drift[:5]:
        print(f"  [!] 行间/行内不一致：源第 {s.line} 行是{s.kind}，译文第 {t.line} 行是{t.kind}"
              f"（{canon(s.body)[:40]}）")

    if tags_s != tags_t:
        print(f"  [XX] 公式编号不一致：源 {tags_s}，译 {tags_t}")
    else:
        print(f"  [OK] 公式编号：{len(tags_s)} 个 \\tag 顺序一致")
    if labs_s != labs_t:
        print(f"  [XX] \\label 不一致：缺少 {sorted(labs_s - labs_t)}，多出 {sorted(labs_t - labs_s)}")
    elif labs_s:
        print(f"  [OK] \\label：{len(labs_s)} 个一致")
    dangling = sorted(refs_t - labs_t)
    if dangling:
        print(f"  [!] 译文引用了不存在的 label：{dangling}")

    bad_s = unbalanced_dollars(src)
    bad_t = unbalanced_dollars(tgt)
    if bad_t:
        print(f"  [XX] 译文有 {len(bad_t)} 行 $ 不成对（公式定界符漏了）：")
        for line, body in bad_t[:6]:
            print(f"       第 {line} 行：{body}")
    elif not bad_s:
        print("  [OK] $ 定界符成对")
    if bad_s and not bad_t:
        print(f"  [!] 原文有 {len(bad_s)} 行 $ 不成对（提取稿常见），译文已自行闭合，需对照 PDF 核对")

    if errors:
        print(f"\n需要处理的差异 {len(errors)} 处（最多列 {args.max} 条）：")
        for r in errors[:args.max]:
            print(f"\n[{r['序号']}] {r['类型']} · 源第 {r['源行']} 行 · 相似度 {r['相似度']}")
            print(f"  源：{r['原文式'][:220]}")
            print(f"  译：{r['译文式'][:220]}")
            print(f"  差：{char_diff(r['原文式'], r['译文式'])}")
            if r["源上下文"]:
                print(f"  位置：{r['源上下文']}")
        if len(errors) > args.max:
            print(f"\n…另有 {len(errors) - args.max} 条，见 CSV。")
    else:
        print("\n[OK] 所有公式与原文逐字一致。")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["序号", "类型", "源行", "相似度",
                                               "原文式", "译文式", "源上下文", "说明"])
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"差异清单：{os.path.abspath(args.csv)}（{len(rows)} 条）")

    print("\n" + "=" * 50)
    total = len(errors) + (1 if bad_t else 0) + (1 if tags_s != tags_t else 0) + \
        (1 if labs_s != labs_t else 0)
    if total:
        print(f"结论：{len(errors)} 处公式差异"
              + ("，$ 定界符有落单" if bad_t else "")
              + ("，编号/label 不一致" if (tags_s != tags_t or labs_s != labs_t) else "")
              + "。公式一处不同，命题就不是同一个命题。"
              + ("（差异全部来自 \\text{} 里的标签文字：一篇之内统一即可，"
                 "确认后可加 --allow-text-only 放行）"
                 if (text_only and len(errors) == text_only and not bad_t) else ""))
        return 1 if args.strict else 0
    print("结论：公式层面通过。定理条件与结论的措辞仍需人工核对——脚本比的是符号，不是语义。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
