#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把"只属于原刊、不属于文章"的块从 Markdown 里剔掉。

成品译文只留：标题（H1）、作者行、正文、附录。以下两类一律不进译文，
其信息要么进 YAML front matter，要么本来就不必给读者看：

1. 版头区（H1 之后、第一个章节标题之前）：刊名、卷期页码、版权行、
   复用指引、DOI、刊物网址、出版社标记、收稿/接受日期、机构与邮箱；
2. 版尾声明：JEL 分类、关键词、致谢、资助、利益冲突、伦理/可复现性声明、
   数据可用性、ORCID、作者简介。

**作者行保留**，只去掉姓名后的编号与角标（`Basu1` → `Basu`）——读者拿到
的是一篇署名文章，不是一份无署名的内部稿。

用法：
    python scripts/strip_meta.py _work/<stem>_原文_正文.md --check
    python scripts/strip_meta.py _work/<stem>_原文_正文.md --meta _work/meta.yaml --apply
    python scripts/strip_meta.py <stem>_zh.md --apply          # 译文侧同样跑一遍

**译前就该跑在源文件上**：译文从第一段起就是干净的，`fidelity_check.py`
的基准也干净，不需要事后拿"发布口径副本"去追。源准与译文两侧都跑一遍，
块序列仍然一一对应。

`--dump-yaml` 把识别到的著录信息打印成 YAML 片段，供人工并进 `meta.yaml`；
它只认死格式（DOI、版权行、JEL、关键词、卷期页码），认不出的留空，不要猜。

`--check` 有块可删返回 1，干净返回 0，可直接当门禁用。
"""
import argparse
import os
import re
import sys

# 版尾声明：标题行本身参与匹配，整块删到下一个任意级标题之前。
DROP_HEADINGS = [
    r"keywords?", r"key\s*words?", r"关键词",
    r"jel\s*(classification|codes?|分类|分类号)?", r"jel\s*分类",
    r"orcids?(\s*i?d)?", r"orcid\s*i\s*d",
    r"authors?'?\s*biograph(y|ies)", r"author\s*biograph(y|ies)", r"作者简介", r"作者介绍",
    r"acknowledge?ments?", r"acknowledg(e)?ments?", r"致谢", r"谢辞",
    r"funding(\s*statement)?", r"funding\s*information", r"资助", r"基金资助", r"资金支持",
    r"declaration\s+of\s+(competing|conflicting)\s+interests?", r"conflicts?\s+of\s+interest",
    r"competing\s+interests?", r"利益冲突(声明)?", r"利益声明",
    r"author'?s?\s+note", r"作者说明", r"作者注",
    r"ethics\s+statement", r"伦理(声明|审查)", r"伦理批准",
    r"reproducibility\s+statement", r"可复现性声明", r"可重复性声明",
    r"data\s+availability(\s+statement)?", r"数据可用性(声明)?",
    r"data,?\s*privacy,?\s*(and\s*)?security", r"数据、?隐私与安全",
    r"supplementary\s+material", r"补充材料",
    r"about\s+the\s+authors?", r"notes?\s+on\s+contributors?", r"作者贡献",
    r"citation", r"引用格式",
]
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
DROP_HEAD_RE = re.compile(
    r"^(?:" + "|".join(DROP_HEADINGS) + r")\s*[:：.。]?\s*$", re.I)

# 版头单行：命中即删。
MASTHEAD = [
    r"^©", r"^\(c\)\s*\d{4}", r"copyright", r"版权所有",
    r"article\s+reuse\s+guidelines", r"reuse\s+guidelines", r"文章复用指引", r"复用指引",
    r"^https?://(dx\.)?doi\.org/", r"doi\.org/10\.", r"^doi\s*[:：]",
    r"^https?://\S+$",                              # 独占一行的网址
    r"sagepub\.com", r"tandfonline\.com", r"journals\.", r"onlinelibrary\.wiley",
    r"springer\.com", r"sciencedirect\.com", r"cambridge\.org", r"jstor\.org",
    r"^s\s*sage$", r"^sage\b", r"^sage\s+publications",
    r"^\d{4}\s*,\s*vol\.", r"^vol\.\s*\d+", r"^\d{4}\s*年\s*第?\s*\d+\s*卷",
    r"^issn", r"^e-?issn",
    r"^(received|accepted|revised|published(\s+online)?|first\s+published)\b",
    r"^(收稿|接受|录用|修回|出版)日期",
    r"^jel\s*(classification|分类)", r"^keywords?\s*[:：]", r"^key\s*words?\s*[:：]",
    r"^关键词\s*[:：]",
    r"^creative\s+commons", r"^cc[ -]by", r"^this\s+is\s+an\s+open\s+access",
    r"^(corresponding\s+author|通讯作者)", r"^e-?mail\s*[:：]",
    r"^available\s+(online|at)\b", r"^submitted\s+to\b",
]
MASTHEAD_RE = [re.compile(p, re.I) for p in MASTHEAD]

STATEMENT = re.compile(
    r"^(?:ethics\s+statement|reproducibility\s+statement|acknowledge?ments?|"
    r"data,?\s*privacy,?\s*and\s*security|author\s+contributions?|funding)\s*[.。:]",
    re.I)

MARK = r"[\d*∗†‡§¶#]+"


def looks_author(line):
    """版头区里的作者行：一串首字母大写的人名，可带编号/角标，行内无句读。"""
    s = line.strip()
    if not s or len(s) > 200 or len(s) < 6:
        return False
    if any(ch in s for ch in "。；：?!;"):
        return False
    core = re.sub(MARK, "", s).strip()
    core = re.sub(r"\s+", " ", core)
    if not re.fullmatch(r"[A-Za-z\u00c0-\u024f'’.\-\s,]+", core):
        return False
    parts = [p for p in re.split(r",|\band\b", core) if p.strip()]
    if not parts:
        return False
    for p in parts:
        words = p.split()
        if not 2 <= len(words) <= 4:
            return False
        if any(len(w.strip(".")) < 2 for w in words):
            return False          # `S Sage` 这类出版社标记不当作人名
        if not all(w[0].isupper() for w in words):
            return False
    return True


def tidy_author(line):
    s = line.strip()
    s = re.sub(r"(?<=[a-z])" + MARK, "", s)      # Basu1 → Basu
    s = re.sub(MARK, "", s)                       # 行首角标、∗†
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r",\s*and\s+", " 和 ", s)          # 末位 and 收成「和」
    s = re.sub(r"\s*,\s*", "、", s)               # 顿号连排
    return s


def head_region(lines):
    """H1 之后、第一个章节标题之前的区间 [start, end)。"""
    h1 = next((i for i, l in enumerate(lines) if re.match(r"^#\s+\S", l)), None)
    if h1 is None:
        return None
    end = len(lines)
    for j in range(h1 + 1, len(lines)):
        if re.match(r"^#{1,6}\s+\S", lines[j]) or lines[j].startswith("<!--"):
            end = j
            break
    return h1 + 1, end


def drop_heading_blocks(lines):
    """按标题名找要整块删的区间，返回 [(start, end)]，end 不含。"""
    out, i = [], 0
    while i < len(lines):
        m = HEAD_RE.match(lines[i])
        if m and DROP_HEAD_RE.match(m.group(2).strip()):
            j = i + 1
            while j < len(lines):
                if re.match(r"^#{1,6}\s+\S", lines[j]) or lines[j].startswith("<!--") \
                        or re.match(r"^\[\^\d+\]:", lines[j]):
                    break
                j += 1
            # 标题后面的空行一并吃掉，但保留与前文的空行
            out.append((i, j))
            i = j
            continue
        i += 1
    return out


def plan(lines, journal=None):
    """返回 (new_lines, removed, kept_author)。removed 为 [(lineno, reason, text)]。"""
    removed, kept = [], None
    drop = [False] * len(lines)

    # YAML front matter 整段保护：里面的 keywords:/jel: 是要保留的元信息，
    # 不能当成"版尾声明"删掉。
    fm_end = -1
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break

    reg = head_region(lines)
    if reg:
        start, end = reg
        for i in range(start, end):
            s = lines[i].strip()
            if not s:
                continue
            if looks_author(s):
                kept = i
                continue
            if journal and s.lower() == journal.lower():
                drop[i] = True
                removed.append((i + 1, "刊名", s))
                continue
            if any(p.search(s) for p in MASTHEAD_RE):
                drop[i] = True
                removed.append((i + 1, "版头", s))

    for a, b in drop_heading_blocks(lines):
        if a <= fm_end:
            continue
        for i in range(a, b):
            if lines[i].strip():
                drop[i] = True
                reason = "版尾声明" if i == a else "版尾声明（续）"
                removed.append((i + 1, reason, lines[i].strip()))

    # JEL 与关键词常以单行出现（摘要之后、正文之前），不在版头区也不带标题。
    INLINE = re.compile(r"^(?:jel\s*(?:classification|codes?|分类|分类号)?|"
                        r"key\s*words?|关键词)\s*[:：]", re.I)
    for i, l in enumerate(lines):
        if i <= fm_end or drop[i] or not INLINE.match(l.strip()):
            continue
        if len(l.strip()) > 160:
            continue                  # 长句是正文在讨论 JEL，不是分类行
        drop[i] = True
        removed.append((i + 1, "JEL／关键词单行", l.strip()))

    # 段首带标记的声明段：ICLR/NeurIPS 体例不给标题，直接
    # `Acknowledgments. This paper is supported by…` 起一段。
    for i, l in enumerate(lines):
        if i <= fm_end or drop[i]:
            continue
        s = l.strip()
        if len(s) > 40 and STATEMENT.match(s):
            drop[i] = True
            removed.append((i + 1, "版尾声明（段首标记）", s[:70]))

    # 作者行：清理角标；它前后若被删空了，保证与下一个标题之间恰好一个空行
    if kept is not None:
        lines = list(lines)
        lines[kept] = tidy_author(lines[kept])

    out, blank = [], False
    for i, l in enumerate(lines):
        if drop[i]:
            continue                        # 空行状态不动：删掉的块不制造空行
        if l.strip() == "" and blank:
            continue                        # 连续空行压成一个
        blank = (l.strip() == "")
        out.append(l)
    return out, removed, kept


def dump_yaml(text):
    """从原文里抠出可靠的著录字段，打印 YAML 片段。认不出的留空。"""
    def grab(pat, flags=re.M | re.I):
        m = re.search(pat, text, flags)
        return m.group(1).strip() if m else ""

    doi = grab(r"doi\.org/(10\.[^\s]+)") or grab(r"^doi\s*[:：]\s*(10\.\S+)")
    doi = doi.rstrip(")．,.；;")
    copyright_ = grab(r"^(©.*)$") or grab(r"^(copyright.*)$")
    jel = grab(r"^jel\s*(?:classification|codes?|分类|分类号)?\s*[:：]\s*(.+)$")
    kw = grab(r"^(?:key\s*words?|关键词)\s*[:：]\s*(.+)$")
    vol = grab(r"\bvol\.?\s*(\d+)") or grab(r"第\s*(\d+)\s*卷")
    issue = grab(r"\((\d+)\)\s*\d") or grab(r"第\s*\d+\s*期")
    pages = grab(r"\((?:\d+)\)\s*([0-9]+[–\-—][0-9]+)") or grab(r"[:：]\s*(\d+[–\-—]\d+)\s*$")
    rows = [("doi", doi), ("copyright", copyright_), ("volume", vol),
            ("issue", issue), ("pages", pages), ("jel", jel), ("keywords", kw)]
    print("# 从刊头／版尾抢救出的著录信息，并进 _work/meta.yaml；认不出的留空，不要猜")
    for k, v in rows:
        print(f'{k}: "{v}"' if v else f'{k}: ""')


def main(argv=None):
    ap = argparse.ArgumentParser(description="剔掉刊头与版尾声明，成品只留标题、作者、正文、附录")
    ap.add_argument("path", help="Markdown 文件（源文工作副本或译文）")
    ap.add_argument("--apply", action="store_true", help="写回文件（留 .bak_strip_meta 备份）")
    ap.add_argument("--check", action="store_true", help="只报告；有块可删返回 1")
    ap.add_argument("--meta", help="读 meta.yaml 里的 journal，用来认出刊名那一行")
    ap.add_argument("--dump-yaml", action="store_true", help="打印抢救出的著录信息")
    args = ap.parse_args(argv)

    text = open(args.path, encoding="utf-8").read()
    journal = None
    if args.meta and os.path.isfile(args.meta):
        m = re.search(r"^journal:\s*(.+)$", open(args.meta, encoding="utf-8").read(), re.M)
        if m:
            journal = m.group(1).strip().strip('"').strip("'")

    lines = text.split("\n")
    new, removed, kept = plan(lines, journal)

    if args.dump_yaml:
        dump_yaml(text)

    if not removed:
        print(f"✓ {args.path}：没有要剔的块")
        return 0

    print(f"{args.path}：{len(removed)} 行待剔")
    for ln, reason, s in removed:
        print(f"  L{ln:<5} [{reason}] {s[:70]}")
    if kept is not None:
        print(f"  保留作者行 → {tidy_author(lines[kept])}")

    if not args.apply:
        print("\n（未写回；确认无误后加 --apply）")
        return 1

    bak = args.path + ".bak_strip_meta"
    if not os.path.exists(bak):
        open(bak, "w", encoding="utf-8").write(text)
    open(args.path, "w", encoding="utf-8").write("\n".join(new))
    print(f"已写回 {args.path}（备份 {os.path.basename(bak)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
