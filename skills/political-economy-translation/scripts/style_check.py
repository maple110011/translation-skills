#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫译文里的口语化痕迹，列出可疑句供人工判断。

不做替换——语体是判断，不是规则匹配。脚本只负责把"这句话读起来不像论文"的
地方找出来，改不改、怎么改，由译者定。

用法：
    python scripts/style_check.py 译文.md
    python scripts/style_check.py 译文.md -o _work/语体候选.md
    python scripts/style_check.py 译文.md --style _work/x_风格.md

--style 读本篇风格约定（references/style-sheet.md 的模板）「## 禁用」一节，
把它列的词并入检查。内置词表是通用底线，本篇约定的禁用词往往更具体
（比如这篇不许用"显而易见"，下篇不许用"众所周知"），只查内置表会漏。

跳过：YAML front matter、参考文献、公式块、表格、图片、代码块。
引号内的文字（直接引语）不计——那里保留作者或译者的原话风格。
"""
import argparse
import os
import re
import sys

# 口语词：出现即可能偏口语。按严重程度分两组，重的一组几乎总要改。
HEAVY = [
    "玩意儿", "大把", "满手", "运气", "搞", "弄", "折腾", "啥", "咱", "咋",
    "甭", "说白了", "别忘了", "压根", "愣", "掰", "扯", "甩", "扔", "攒",
    "赚", "买卖", "生意", "老板", "老百姓", "干活", "攒钱", "花钱",
    "好懂", "好办", "难办", "讲清楚", "说清楚", "看清楚", "看得出来",
    "看得出", "弄不清", "搞不清", "没什么两样", "一回事", "这么", "那么",
    "多得多", "得很", "极了", "才行", "好不好", "行不行",
]
# 轻的一组：书面文里也能用，但密集出现往往是口语化的信号。
LIGHT = [
    "其实", "到底", "究竟", "所幸", "好在", "反正", "偏偏", "竟然", "居然",
    "干脆", "差不多", "一下子", "多半", "无非", "只不过", "罢了", "挺",
    "蛮", "有点", "一点儿", "好多", "好些", "不免", "不妨", "难免",
    "这样一来", "这样的话", "不用说", "可想而知", "可以说",
]
# 句式：英文口语结构的直译残留。
PATTERNS = [
    (r"要[^。；]{0,12}的(东西|事情|地方)不(少|多)", "「要……的东西不少」"),
    (r"还[得要有][^。；]{0,6}(说|讲|提|记)[^。；]{0,4}句", "「还得说几句」"),
    (r"[^。；]{0,10}得多[，。；]", "「……得多」"),
    (r"没(有)?什么(两样|区别)的?", "「没什么两样」"),
    (r"不(太|怎么)?(容易|好)(做|办|懂|说)", "「不容易／不好办」"),
    (r"(看|读|听)(得|起来)[^。；]{0,6}(懂|清|明白)", "「看得懂／看得清」"),
    (r"把[^。；]{0,12}(给|弄|搞)[^。；]{0,8}", "「把……给……」"),
    # 词表里的子串匹配会把「才成立」判成「才成」，这里加边界单独处理
    (r"才成(?!立|为|本)", "「才成」"),
]

CITE = re.compile(r"“[^”]*”|\"[^\"]*\"|「[^」]*」|『[^』]*』")
SKIP = ("#", "!", "|", "<", "$", "Figure", "图 ", "```", ">", "[^")


def body_of(md):
    if md.startswith("---"):
        m = re.match(r"---\n.*?\n---\n", md, re.S)
        if m:
            md = md[m.end():]
    # 参考文献整段是原文，按规则 4 不译，也不评语体
    md = re.split(r"^#{1,6}\s*(?:参考文献|References)\s*$", md, flags=re.M)[0]
    return md


def sentences(md):
    """产出 (段号, 句)。跳过结构块。"""
    n = 0
    for blk in re.split(r"\n\s*\n", body_of(md)):
        blk = blk.strip()
        if not blk or blk.startswith(SKIP):
            continue
        n += 1
        for s in re.split(r"(?<=[。！？])", blk):
            s = s.strip()
            if len(s) >= 6:
                yield n, s


def load_style_words(path):
    """从风格约定的「## 禁用」一节取出词表与句式。

    返回 (词, [(正则, 原始写法)])。「对……进行……」这类用省略号写的句式
    转成正则：省略号当"中间可以隔几个字"，否则按字符串永远匹配不上。
    取不出来就返回空，不报错。
    """
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        sys.exit(f"找不到风格文件 {path}")
    m = re.search(r"^##\s*禁用.*?$(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if not m:
        print(f"· {path} 里没有「## 禁用」一节，只用内置词表")
        return [], []
    words, patterns = [], []
    for line in m.group(1).split("\n"):
        line = line.strip().lstrip("-*").strip()
        if not line or line.startswith(">"):
            continue
        line = re.sub(r"[（(][^）)]*[）)]", "", line)   # 去掉括注的判据
        line = line.replace("<", "").replace(">", "").replace("`", "")
        # 去掉「口语与随笔腔：」这类行首标签，否则标签会和第一个词黏在一起被整条丢掉
        line = re.sub(r"^[^：:]{1,14}[：:]\s*", "", line)
        for piece in re.split(r"[／/、，,；;]", line):
            p = piece.strip(" 　:：")
            if "…" in p:
                parts = [re.escape(x) for x in re.split(r"…+", p) if x.strip()]
                if len(parts) >= 2:
                    patterns.append((r"[^。；]{0,12}".join(parts), p))
                continue
            # 单字也收：用户手写的条目，收窄反而漏检（搞、弄这类正是要查的）
            if 1 <= len(p) <= 8 and not re.search(r"[。，、；：？！\s]", p):
                words.append(p)
    return list(dict.fromkeys(words)), patterns


def check(text, extra=(), extra_pat=()):
    hits = []
    bare = CITE.sub("□", text)  # 引号内不计
    for w in extra:
        if w in bare:
            hits.append((w, "禁用"))
    for pat, label in extra_pat:
        if re.search(pat, bare):
            hits.append((label, "禁用句式"))
    for w in HEAVY:
        if w in bare:
            hits.append((w, "重"))
    for w in LIGHT:
        if w in bare:
            hits.append((w, "轻"))
    for pat, label in PATTERNS:
        if re.search(pat, bare):
            hits.append((label, "句式"))
    return hits


def main():
    ap = argparse.ArgumentParser(description="扫口语化痕迹")
    ap.add_argument("target", help="译文 md")
    ap.add_argument("-o", "--out", default="", help="输出 Markdown 报告")
    ap.add_argument("--max", type=int, default=120, help="最多列多少条")
    ap.add_argument("--style", default="", help="本篇风格约定 md，读其「## 禁用」一节")
    args = ap.parse_args()

    if not os.path.exists(args.target):
        sys.exit(f"找不到 {args.target}")
    md = open(args.target, encoding="utf-8").read()
    extra_words, extra_pat = load_style_words(args.style) if args.style else ([], [])

    rows = []
    for n, s in sentences(md):
        h = check(s, extra_words, extra_pat)
        if h:
            rows.append((n, s, h))

    heavy = sum(1 for _, _, h in rows if any(t in ("重", "禁用", "禁用句式") for _, t in h))
    print(f"可疑句 {len(rows)} 条（其中含重度口语词或本篇禁用词 {heavy} 条）")
    for n, s, h in rows[:args.max]:
        tag = "、".join(f"{w}" for w, _ in h)
        print(f"  [§{n}] {tag}｜{s[:110]}")

    if args.out:
        L = ["# 语体自查", "",
             f"共 {len(rows)} 条可疑，其中含重度口语词或本篇禁用词 {heavy} 条。"
             "引号内的直接引语不计；参考文献不计。", "",
             "逐条判断：改，或说明为何保留（原文语气如此、术语、引文）。", ""]
        for n, s, h in rows:
            L += [f"- **§{n}**　触发：{'、'.join(w for w, _ in h)}", f"  - {s}", ""]
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w", encoding="utf-8").write("\n".join(L))
        print(f"\n报告已写入 {args.out}")


if __name__ == "__main__":
    main()
