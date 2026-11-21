#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把人名补成中文名——**只补人名明确出现在句子里的那种**。

    Steedman（1977: ch. 6）      → 斯蒂德曼（Steedman, 1977: ch. 6）
    依照马克思（1992: 432）      → 依照马克思（Marx, 1992: 432）   （反向补英文姓）
    （Marx 1992: 534）           → 不动

**纯括号引用不改。** 括号里的姓是文献标识，作用是让读者去书目里找 `Marx,
Karl. 1992.` 那一条，不是句子成分；把它译成中文反而断了对回书目的线索。
只有姓名在句子里担任主语、宾语、定语（「依照 X 的说法」「X 认为」）时才译，
译完在括号里附英文姓与年份，读者两头都能对上。

判据是**这个名字在句子里有没有职务**：
- 有职务 → `斯蒂德曼（Steedman, 1977: ch. 6）`；
- 没职务、只是标出处 → `（Steedman 1977: ch. 6）` 原样保留。

译名只从 `references/glossary/verified_names.csv` 取（`form=surname`），
**查不到的不猜**：列进 `_work/<stem>_人名待补.md`，等人补表或裁决。
脚本幂等——已经写成 `中文名（English, 年份）` 的不会再套一遍。

`--brackets` 是例外开关：有些场合（比如面向非专业读者的普及本）希望连括号
里的姓也汉化，默认关闭。

用法::

    python scripts/zh_cite_names.py <stem>_zh.md                # 只报告，不改文件
    python scripts/zh_cite_names.py <stem>_zh.md --apply        # 就地改写（留 .bak）
    python scripts/zh_cite_names.py <stem>_zh.md --apply --glossary path/to/names.csv
"""
import argparse
import csv
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_GLOSSARY = HERE.parent / "references" / "glossary" / "verified_names.csv"

FRONT = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", re.S)
REFS_HEAD = re.compile(r"^#{1,6}\s*\**\s*(参考文献|references?|bibliography)\s*\**\s*$", re.I | re.M)
# 一个括号里的引用串：至少含一个四位年份，且不含中文（含中文说明已经处理过）
CITE = re.compile(r"[（(]([^（）()\n]{0,160}?(?:19|20)\d{2}[^（）()\n]{0,60}?)[）)]")
# 叙述式：`Steedman（1977: ch. 6）`、`马克思（1992: 432）`——人名在括号外。
# 括号里只有年份（可能带 `: ch. 6` 这类定位符），没有字母，否则就是已处理过的形态。
NARR = re.compile(r"(?P<sp>[ \t]*)"
                  r"(?P<name>[A-Z][A-Za-zÀ-ÿ\'\-]{1,20}|[\u4e00-\u9fff]{2,6})"
                  r"\s*[（(](?P<inner>(?:19|20)\d{2}[a-z]?(?::[^（）()\n]{0,40})?)[）)]")
GROUP = re.compile(r"^\s*(?P<names>.*?)\s*(?P<year>(?:19|20)\d{2}[a-z]?)\s*(?P<tail>[:：].*)?$", re.S)
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
# 「Fall 2004」「Spring 2019」是期刊期号，不是人名；月份同理。
NOT_A_NAME = {"fall", "spring", "summer", "winter", "autumn",
              "january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december",
              "vol", "no", "pp", "p", "ch", "chap", "ed", "eds"}


def load_names(path):
    """(fwd, rev)。fwd: {小写姓氏: (译名, 置信度, 依据)}；rev: {中文名: [英文姓氏]}。"""
    fwd, rev = {}, {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if (r.get("form") or "").strip().lower() != "surname":
                continue
            src = (r.get("src") or "").strip()
            dst = (r.get("dst") or "").strip()
            if not src or not dst:
                continue
            last = src.split()[0].rstrip(".").lower()
            fwd[last] = (dst, (r.get("confidence") or "").strip(), (r.get("basis") or "").strip())
            rev.setdefault(dst, set()).add(last)
            # alias 里可能挂着别的写法（`Marx, K.|K. Marx|marx`）
            for al in (r.get("alias") or "").split("|"):
                al = al.strip()
                if al and " " not in al:
                    fwd.setdefault(al.rstrip(".").lower(), fwd[last])
    return fwd, {k: sorted(v) for k, v in rev.items()}


def split_people(s):
    """`Philp, Slater, and Harvie` → 三个姓；`Mavroudeas and Ioannides` → 两个。

    `et al.` 单独剥掉，否则 `Green et al.` 会被当成一个叫「Green et al」的人。
    """
    s = re.sub(r"\s+et\s+al\.?", "", s)
    s = re.sub(r"\s+and\s+|\s*&\s*", ",", s)
    parts = [p.strip().strip(".") for p in re.split(r"[,，、]", s)]
    return [p for p in parts if p]


def fix_group(grp, names, miss):
    """处理一组「人名 年份」；返回改写后的文本，查不到则原样返回。"""
    m = GROUP.match(grp)
    if not m:
        return grp
    people = split_people(m.group("names"))
    if not people:
        return grp
    if all(p.lower() in NOT_A_NAME for p in people):   # Fall 2004 这类期号
        return grp
    if CJK.search(m.group("names")):        # 已经汉化过，幂等跳过
        return grp
    zh = []
    for p in people:
        hit = names.get(p.lower())
        if not hit:
            miss.add(p)
            return grp                       # 有一个人名没译名，整组不动
        zh.append(hit[0])
    year = m.group("year")
    tail = m.group("tail") or ""
    head = "、".join(zh) + " " + m.group("names").strip()
    return head + ", " + year + tail


def fix_cite(inner, names, miss):
    """一个括号里的内容：按 `;` 分组，逐组改写。"""
    parts = re.split(r"([;；])", inner)
    out = []
    for p in parts:
        if p in (";", "；"):
            out.append("；")
            continue
        out.append(fix_group(p, names, miss))
    return "".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="括号引用里的人名换成「中文名 原名, 年份」")
    ap.add_argument("md", help="译文 Markdown")
    ap.add_argument("--apply", action="store_true", help="就地改写（先留 .bak）")
    ap.add_argument("--glossary", default=str(DEFAULT_GLOSSARY), help="译名表，默认 verified_names.csv")
    ap.add_argument("--brackets", action="store_true",
                    help="同时给纯括号引用里的人名补中文名。默认不做：括号里的姓是"
                         "文献标识（给读者去书目里找），不是句子成分")
    ap.add_argument("--report", default=None, help="待补人名报告路径，默认 _work/<stem>_人名待补.md")
    args = ap.parse_args(argv)

    md = pathlib.Path(args.md)
    text = md.read_text(encoding="utf-8")
    m = FRONT.match(text)
    head, body = (text[:m.end()], text[m.end():]) if m else ("", text)
    rm = REFS_HEAD.search(body)
    main_part, refs_part = (body[:rm.start()], body[rm.start():]) if rm else (body, "")

    names, rev = load_names(args.glossary)
    miss = set()
    unreverse = set()
    changed = [0, 0]

    def repl(mt):
        inner = mt.group(1)
        new = fix_cite(inner, names, miss)
        if new != inner:
            changed[0] += 1
        return mt.group(0)[0] + new + mt.group(0)[-1]

    new_main = CITE.sub(repl, main_part) if args.brackets else main_part

    def nrepl(mt):
        """叙述式：`Steedman（1977: ch. 6）` → `斯蒂德曼（Steedman, 1977: ch. 6）`。"""
        name, inner = mt.group("name"), mt.group("inner")
        s = mt.string
        sp_at = mt.start("sp")
        # 名字前紧贴字母的（`and Harvie（2005）`）不是独立的叙述式引用，跳过。
        if sp_at > 0 and LATIN.match(s[sp_at - 1]):
            return mt.group(0)
        # 不能拿"inner 里有没有字母"当"已处理过"的判据：`（1977: ch. 6）` 的
        # `ch` 也是字母。NARR 的正则已经保证 inner 以年份开头，处理过的形态
        # （`（Marx, 1992）`）压根匹配不上。所以这里不需要再挡。
        if LATIN.search(name):
            hit = names.get(name.lower())
            if not hit:
                miss.add(name)
                return mt.group(0)
            changed[1] += 1
            # 英文名换成中文名后，前面那个西文空格要一起吃掉：
            # 「依照 Steedman（…）」→「依照斯蒂德曼（Steedman, …）」，不是
            # 「依照 斯蒂德曼（…）」。
            return "%s（%s, %s）" % (hit[0], name, inner)
        hits = rev.get(name) or []
        if len(hits) == 1:
            changed[1] += 1
            return "%s%s（%s, %s）" % (mt.group("sp"), name, hits[0].capitalize(), inner)
        # 中文没有词边界：`依照马克思（1992）` 里的连续汉字串会连「依照」一起
        # 抓进来。从右往左试 2–5 字的后缀，取第一个在译名表里对得上的，
        # 前面那截（「依照」）原样留在括号外。
        for n in range(min(5, len(name)) - 1, 1, -1):
            cand = name[-n:]
            ch = rev.get(cand) or []
            if len(ch) == 1:
                changed[1] += 1
                return "%s%s%s（%s, %s）" % (mt.group("sp"), name[:-n], cand,
                                             ch[0].capitalize(), inner)
            if len(ch) > 1:
                unreverse.add(cand)
                return mt.group(0)
        unreverse.add(name)
        return mt.group(0)

    new_main = NARR.sub(nrepl, new_main)

    print("译名表 %d 条（surname）" % len(names))
    if args.brackets:
        print("改写 %d 处括号引用、%d 处叙述式" % (changed[0], changed[1]))
    else:
        print("改写 %d 处叙述式（纯括号引用按口径不动；要动加 --brackets）" % changed[1])
    if miss:
        print("查不到译名 %d 个：%s" % (len(miss), "、".join(sorted(miss))))
    if unreverse:
        print("中文名反查英文失败（译名表里不唯一或缺失）%d 个：%s"
              % (len(unreverse), "、".join(sorted(unreverse))))
    miss |= unreverse

    rp = pathlib.Path(args.report) if args.report else (
        md.parent / "_work" / (md.stem.replace("_zh", "") + "_人名待补.md"))
    if miss and args.apply:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text("# 正文引用里查不到译名的人名\n\n"
                      "补进 `references/glossary/verified_names.csv`（`form=surname`），再重跑 "
                      "`zh_cite_names.py --apply`。\n\n"
                      + "".join("- `%s`\n" % n for n in sorted(miss)), encoding="utf-8")
        print("待补清单：%s" % rp)

    if not args.apply:
        print("（只报告，未改文件；加 --apply 生效）")
        return 0

    if not (changed[0] + changed[1]):
        print("没有可改的地方。")
        return 0
    if md.with_suffix(md.suffix + ".bak").exists():
        pass
    else:
        md.with_suffix(md.suffix + ".bak").write_text(text, encoding="utf-8")
    md.write_text(head + new_main + refs_part, encoding="utf-8")
    print("已写入 %s（备份 %s.bak）" % (md.name, md.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
