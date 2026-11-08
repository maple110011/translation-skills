#!/usr/bin/env python3
"""Build and check the 符号一览 (notation table) that every translated paper carries.

Two jobs, one file, because they must agree on what a "symbol" is:

    extract  从原文抽出应当进表的符号，生成带频次与首次出现位置的 CSV 骨架，
             译者只需补「含义」一列。
    check    核对译文的符号表与正文：正文用了但表里没有的符号、表里有但正文
             根本没有的符号（多半是抄错了）。

抽取的是「原子」而不是整条公式：`x_i^{(t)}` 的原子是 `x`，`\\sigma` 的原子是
`\\sigma`，`\\mathbb{E}` 的原子是 `\\mathbb{E}`。这样 `x_1`、`x_2`、`x_n` 归并成
一条（表里写 `$x_i$` 就够），而 `x`、`\\hat{x}`、`\\mathbf{x}` 不会被混为一谈。

Usage
-----
    python notation.py extract 原文.md -o _work/符号候选.csv
    python notation.py check 原文.md 译文_zh.md --csv _work/符号缺漏.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathscan import TEXT_CMD, notation_block, scan, strip_notation  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

GREEK = set("""alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
varkappa lambda mu nu xi omicron pi varpi rho varrho sigma varsigma tau upsilon phi varphi
chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega""".split())

# Decorations and font commands: the whole `\mathbb{E}` is one symbol, so these
# are kept together with their argument instead of being split into a command
# plus a letter.
ACCENT = (r"\\(?:hat|widehat|tilde|widetilde|bar|overline|underline|vec|dot|ddot|check|"
          r"breve|acute|grave|mathbb|mathcal|mathbf|boldsymbol|pmb|mathscr|mathfrak|mathit|"
          r"mathsf|mathtt|mathrm|mathnormal|operatorname)")

SCRIPTS = (r"(?:\s*_\s*\{(?:[^{}]|\{[^{}]*\})*\}|\s*_\s*[A-Za-z0-9]"
           r"|\s*\^\s*\{[^{}]+\}|\s*\^\s*[A-Za-z0-9])*")

# 参数可以带花括号（`\pmb{X}`），也可以不带（`\pmb X`、`\mathcal P`）——
# 后者在正文里很常见，漏掉就会把 `\mathcal P` 拆成 `\mathcal` 和 `P` 两个假符号。
ATOM = re.compile(r"(?<![\\A-Za-z])(" + ACCENT +
                  r"\s*(?:\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|[A-Za-z])" +
                  r"|\\[A-Za-z]+|[A-Za-z])(" + SCRIPTS + r")")

# Commands that are notation of the typesetting, not objects the reader looks
# up. `\nabla` stays: it is a symbol people do look up.
NON_SYMBOL = set("""left right big Big bigg Bigg bigl bigr Bigl Bigr Biggl Biggr
sum prod coprod int iint iiint oint lim liminf limsup sup inf max min arg log ln lg exp
sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh det dim ker deg gcd mod bmod pmod
quad qquad enspace thinspace hspace vspace mkern mskip hskip
cdot cdots ldots dots vdots ddots dotsb dotsc
to mapsto in notin ni subset subseteq subsetneq supset supseteq cup cap setminus emptyset varnothing
forall exists nexists neg lnot land lor implies iff Leftrightarrow leftrightarrow Rightarrow
rightarrow leftarrow Leftarrow uparrow downarrow le leq leqslant ge geq geqslant ne neq
approx sim simeq cong equiv propto ll gg pm mp times div ast star circ bullet lesssim gtrsim
oplus otimes oslash odot ominus lVert rVert vert Vert lvert rvert
lfloor rfloor lceil rceil langle rangle lbrace rbrace lbrack rbrack mid nmid colon backslash top
begin end tag label eqref ref nonumber notag displaystyle textstyle scriptstyle scriptscriptstyle
limits nolimits mathop mathrel mathbin mathord mathopen mathclose mathpunct mathinner
text mbox hbox textrm textit textbf textnormal textsf partial nabla
frac dfrac tfrac cfrac sqrt binom dbinom tbinom choose overset underset stackrel substack
mathclap mathllap mathrlap phantom hphantom vphantom boxed cancel bcancel xcancel
hfill hline cline arraystretch mathstrut strut
mathrm mathbb mathcal mathbf mathsf mathtt mathfrak boldsymbol bm""".split())


ACCENT_NAMES = {"hat", "widehat", "tilde", "widetilde", "bar", "overline", "underline",
                "vec", "dot", "ddot", "check", "breve", "acute", "grave", "mathbb",
                "mathcal", "mathbf", "boldsymbol", "pmb", "mathscr", "mathfrak", "mathit",
                "mathsf", "mathtt", "mathrm", "mathnormal", "operatorname"}


# 常见、几乎没有歧义的符号：不进符号一览。
#
# 判据不是"简单"，而是"不列出来读者也不会读错"：数集就是数集，期望就是期望，
# 索引 i 就是索引。把它们逐条列出来，表会从 10 行长到 35 行，读者反而找不到
# 真正需要查的 $p_0$、$\mathcal{P}$、$\Pi_N$。
#
# 希腊字母一律不在其中：π 在这篇里是 PPD，在另一篇里是圆周率或策略；
# 拉丁大写单字母也不在其中（`C` 既可能是通用常数，也可能是一个集合或类）。
COMMON = {
    # 数集与函数空间
    r"\mathbb{R}", r"\mathbb{N}", r"\mathbb{Z}", r"\mathbb{Q}", r"\mathbb{C}",
    # 期望、概率、方差、协方差算子
    r"\mathbb{E}", r"\mathbb{E}", r"\mathbb{P}", r"\mathbb{V}",
    r"\mathrm{Var}", r"\mathrm{Cov}", r"\mathrm{KL}",
    # 分析算子与常量
    r"\nabla", r"\partial", r"\infty", r"\emptyset",
    # 索引
    "i", "j", "k", "h", "l",
}

# 数集带上标仍是数集：`\\mathbb{R}^d` 谁都知道是 d 维实空间，不必占一行。
# 算子不带这个豁免——`\\mathbb{E}_{\\Pi}` 与 `\\mathbb{E}` 是两回事。
COMMON_ANY_SCRIPT = {
    r"\mathbb{R}", r"\mathbb{N}", r"\mathbb{Z}", r"\mathbb{Q}", r"\mathbb{C}",
    r"\mathrm{Var}", r"\mathrm{Cov}", r"\mathrm{KL}", r"\underbrace",
    # 概率算子与示性函数：`\mathbb{P}\{X_i \in A\}`、`\mathbb{1}_{(a,b]}` 都是标准写法，
    # 上下标只说明"在哪个集合上"，不改变符号含义。
    r"\mathbb{P}", r"\mathbb{1}", r"\mathbf{1}",
    # 渐近记号与信息准则：`o(n)`、`O_p(1)`、`BIC` 在每篇论文里都是同一个意思。
    r"O", r"o", r"\mathrm{BIC}", r"\operatorname{BIC}", r"\mathrm{AIC}",
    # 标准算子与函数名：Var/Cov/KL/TV/Corr 都是逐篇同义的算子名，不是要查的记号。
    r"\operatorname{Var}", r"\operatorname{Cov}", r"\operatorname{KL}",
    r"\operatorname{TV}", r"\mathrm{TV}", r"\operatorname{Corr}",
    r"\operatorname{ReLu}", r"\operatorname{ReLU}",
    # 自然常数 e、零向量、并集符号
    "e", r"\bigcup", r"\boldsymbol{0}", r"\mathbf{0}",
    # 网络层与算子的名字（SoftMax、LayerNorm、ReLU、avg）是函数名，不是查表的符号。
    r"\mathrm{SoftMax}", r"\mathrm{LayerNorm}", r"\mathrm{ReLU}",
    r"\operatorname{SoftMax}", r"\operatorname{LayerNorm}", r"\operatorname{ReLU}",
    r"\operatorname{avg}", r"\mathrm{ReLu}", r"\mathrm{relu}",
    # 零向量与单位矩阵：`\mathbf{0}`、`I_5` 是任何一篇里的同一意思。
    r"\mathbf{0}", r"I",
}


def is_common(base, forms=None):
    """`forms` 给了就要求该符号没有上下标。

    否则 `\\mathbb{E}_{\\Pi}` 会因为基底 `\\mathbb{E}` 常见而被一起删掉——可"对先验取
    期望"恰恰是这篇论文要读者记住的东西。
    """
    if base in COMMON_ANY_SCRIPT:
        return True
    if base not in COMMON:
        return False
    return True if forms is None else all(f == base for f in forms)


ALIGN_ENV = re.compile(r"\\(?:begin|end)\s*\{[^{}]*\}(?:\s*\{[^{}]*\})?")


def atoms(body):
    """Yield (base, full_form) for one formula body.

    ``base`` drops the scripts so that ``x_1``, ``x_2`` and ``x_n`` collapse to
    one table row; ``full_form`` keeps them so the table can show the form the
    paper actually uses most often.
    """
    # `\begin{array}{l}` 的 l/r/c 是列对齐参数，不是符号。不剥掉，符号表里
    # 就会凭空多出几个 "l"、"r"。
    body = ALIGN_ENV.sub(" ", TEXT_CMD.sub(" ", body))
    for m in ATOM.finditer(body):
        atom, script = m.group(1), m.group(2) or ""
        if atom.startswith("\\"):
            name = re.split(r"[\s{]", atom.lstrip("\\"))[0]
            if name in ACCENT_NAMES and "{" not in atom:
                # `\mathcal P` -> `\mathcal{P}`，让同一个符号只有一种写法
                # 必须真有空格才算"命令 + 裸字母"。不加 \s+ 的话，
                # `\boldsymbol` 本身也会被拆成 `\boldsymbo` + `l`。
                m2 = re.fullmatch(r"(\\[A-Za-z]+)\s+([A-Za-z])", atom)
                if m2:
                    atom = f"{m2.group(1)}{{{m2.group(2)}}}"
            if name not in ACCENT_NAMES and name not in GREEK and name in NON_SYMBOL:
                continue
        base = re.sub(r"\s+", "", atom)
        m3 = re.fullmatch(r"\\(?:mathit|mathrm|mathsf|mathtt|mathbf)\s*\{([A-Za-z])\}",
                          base)
        if m3:
            # `\mathit{q}` 与 `q` 是同一个符号，只是字体不同——表里当然只有 `q`。
            base = m3.group(1)
        yield base, re.sub(r"\s+", "", base + script), m.start(1)


def collect(text):
    """base -> {count, forms, first_line, context}."""
    info = OrderedDict()
    for span in scan(text):
        # Context is the prose around the formula, not the formula itself: a
        # row whose context is just `n` tells the translator nothing about
        # whether it is a sample size or an index.
        around = re.sub(r"\s+", " ", text[max(0, span.start - 30):span.end + 30]).strip()
        for base, full, pos in atoms(span.body):
            rec = info.setdefault(base, {"count": 0, "forms": Counter(),
                                         "first_line": span.line,
                                         "context": around[:90]})
            rec["count"] += 1
            rec["forms"][full] += 1
    return info


def table_symbols(block):
    """Bases listed in the notation table, plus rows whose first cell has no `$`."""
    bases, bare = set(), []
    for line in block.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", s.strip("|"))]
        if not cells or set(cells[0]) <= set("-: "):
            continue
        cell = cells[0]
        if cell in ("符号", "记号", "Symbol", "symbol"):
            continue
        spans = scan(cell)
        if not spans:
            if re.fullmatch(r"[\\A-Za-z][^，。；]*", cell):
                bare.append(cell)
                bases.update(b for b, _, _ in atoms(cell))
            continue
        for sp in spans:
            bases.update(b for b, _, _ in atoms(sp.body))
    for line in block.split("\n"):
        s2 = line.strip()
        if s2.startswith("|"):
            continue
        for sp in scan(s2):
            bases.update(b for b, _, _ in atoms(sp.body))
    return bases, bare


# --------------------------------------------------------------------------
def cmd_extract(args):
    with open(args.input, "r", encoding="utf-8") as fh:
        text = fh.read()
    info = collect(text)
    rows, common_hit = [], []
    for base, rec in info.items():
        if rec["count"] < args.min_count:
            continue
        if is_common(base, rec["forms"]) and not args.keep_common:
            common_hit.append(base)
            continue
        form = rec["forms"].most_common(1)[0][0]
        rows.append({
            "symbol": form, "base": base, "count": rec["count"],
            "first_line": rec["first_line"], "context": rec["context"], "meaning": "",
        })
    rows.sort(key=lambda r: r["first_line"])
    if args.top:
        rows = rows[:args.top]

    print(f"原文：{args.input}")
    print(f"  数学片段 {len(scan(text))} 处，候选符号 {len(rows)} 个（按首次出现排序）")
    if common_hit:
        print(f"  已略去 {len(common_hit)} 个常见符号（不列也不会读错）："
              + "、".join(common_hit[:10]) + ("…" if len(common_hit) > 10 else "")
              + "；要保留它们加 --keep-common")
    if not args.out:
        for r in rows[:args.max]:
            print(f"  第 {r['first_line']:>5} 行  {r['symbol']:<16} ×{r['count']:<4} "
                  f"{r['context'][:50]}")
        return 0

    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["symbol", "base", "count", "first_line",
                                           "context", "meaning"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"已写出 {os.path.abspath(args.out)}")
    print("下一步：补 meaning 列（中文，术语与术语表一致），再按 first_line 顺序抄进译文开头的符号一览。")
    return 0


def cmd_prune(args):
    """删掉符号表里只含常见符号的行。

    表一旦写长，人就不看了——而符号表的价值完全取决于"读者遇到不认识的符号
    时愿意去查"。所以宁短勿长：只保留真正需要查的。
    """
    with open(args.target, "r", encoding="utf-8") as fh:
        text = fh.read()
    block = notation_block(text)
    if not block.strip():
        print("[XX] 没找到符号一览。")
        return 1

    keep, drop, in_body = [], [], False
    for line in block.split("\n"):
        s2 = line.strip()
        if not s2.startswith("|"):
            keep.append(line)
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", s2.strip("|"))]
        if len(cells) < 3 or set(cells[0]) <= set("-: "):
            keep.append(line)
            continue
        if cells[0] in ("符号", "记号", "Symbol", "symbol"):
            keep.append(line)
            continue
        spans = scan(cells[0])
        pairs = [(b, f) for sp in spans for b, f, _ in atoms(sp.body)]
        # 整行每个符号都「常见且无上下标」才删；一格里混了 `$d$` 就留着，
        # 因为读者仍需要查 `$d$`。
        if pairs and all(is_common(b, [f]) for b, f in pairs) and not args.keep:
            drop.append((cells[0], cells[1] if len(cells) > 1 else ""))
            continue
        keep.append(line)

    for sym, meaning in drop:
        print(f"  删：{sym:<28} {meaning[:40]}")
    if not drop:
        print("  没有只含常见符号的行，表不用动。")
        return 0

    new_block = "\n".join(keep)
    text = text.replace(block, new_block, 1)
    if args.apply:
        with open(args.target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"  已删除 {len(drop)} 行，写出 {args.target}")
    else:
        print(f"  共 {len(drop)} 行可删（加 --apply 写回）")
    return 0


def cmd_check(args):
    with open(args.source, "r", encoding="utf-8") as fh:
        src = fh.read()
    with open(args.target, "r", encoding="utf-8") as fh:
        tgt = fh.read()

    block = notation_block(tgt)
    if not block.strip():
        print("[XX] 译文里没有找到符号一览（应为 `## 符号一览`，建议用 "
              "<!-- notation:start --> … <!-- notation:end --> 包住）。")
        return 1 if args.strict else 0

    body = strip_notation(tgt)
    body_info = collect(body)
    listed, bare = table_symbols(block)
    exempt = [b for b in body_info
              if is_common(b, body_info[b]["forms"]) and b not in listed]
    missing = [(b, r["count"], r["first_line"], r["context"])
               for b, r in body_info.items()
               if b not in listed and not is_common(b, r["forms"])]
    missing.sort(key=lambda x: (-x[1], x[2]))

    def used_only_as_script(base):
        """`j` 通常只以 `_{j}` 的形式出现，原子抽取不会单独数它。"""
        if not re.fullmatch(r"[A-Za-z]|\\[A-Za-z]+", base):
            return False
        pat = r"[_^]\s*\{?\s*" + re.escape(base.strip("\\{}")) + r"\s*\}?"
        return re.search(pat, body) is not None

    extra = sorted(b for b in listed if b not in body_info and not used_only_as_script(b))

    print(f"译文：{args.target}")
    print(f"  符号表条目：{len(listed)} 个符号；正文符号：{len(body_info)} 个"
          + (f"（另有 {len(exempt)} 个常见符号按规则不入表）" if exempt else ""))
    if bare:
        print(f"  [!] 表里有 {len(bare)} 个单元格没加 $…$，渲染不成公式："
              + "、".join(bare[:8]))
    if missing:
        print(f"\n  正文用到、表里没有（{len(missing)} 个，按出现次数排）：")
        for base, n, line, ctx in missing[:args.max]:
            print(f"    {base:<16} ×{n:<4} 首见第 {line} 行   {ctx[:44]}")
        if len(missing) > args.max:
            print(f"    …另有 {len(missing) - args.max} 个，见 CSV。")
        print("\n  其中出现一次的多半是临时记号，可以不进表；出现多次又没进表的，"
              "读者只能靠上下文猜，务必补上。")
    else:
        print("  [OK] 正文符号都进了表")
    if extra:
        print(f"\n  [!] 表里有、正文没有（{len(extra)} 个）：{'、'.join(extra[:10])}"
              "\n      多半是符号抄错或表里写的是上一版的记号——逐个回正文核对。")
    else:
        print("  [OK] 表里没有正文用不到的符号")

    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["符号", "类型", "出现次数", "首次行", "上下文"])
            for base, n, line, ctx in missing:
                w.writerow([base, "缺失", n, line, ctx])
            for base in extra:
                w.writerow([base, "多余", 0, "", ""])
            for cell in bare:
                w.writerow([cell, "未用$包裹", 0, "", ""])
        print(f"\n已写出 {os.path.abspath(args.csv)}")

    bad = len(missing) + len(extra) + len(bare)
    if args.strict and bad:
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成与核对符号一览表。")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="从原文抽符号，生成待填 CSV")
    e.add_argument("input")
    e.add_argument("-o", "--out", default="", help="输出 CSV；不给则只打印")
    e.add_argument("--min-count", type=int, default=1)
    e.add_argument("--top", type=int, default=0, help="只保留前 N 个（按首次出现）")
    e.add_argument("--max", type=int, default=40, help="控制台最多列多少条")
    e.add_argument("--keep-common", action="store_true",
                   help="连常见符号（ℝ、𝔼、索引 i…）一起列出")
    e.set_defaults(func=cmd_extract)

    p2 = sub.add_parser("prune", help="删掉符号表里只含常见符号的行")
    p2.add_argument("target")
    p2.add_argument("--apply", action="store_true", help="写回文件（默认只演习）")
    p2.add_argument("--keep", action="store_true", help="不删，只看看会删哪些")
    p2.set_defaults(func=cmd_prune)

    c = sub.add_parser("check", help="核对译文的符号表与正文")
    c.add_argument("source")
    c.add_argument("target")
    c.add_argument("--csv", default="")
    c.add_argument("--max", type=int, default=25)
    c.add_argument("--strict", action="store_true")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
