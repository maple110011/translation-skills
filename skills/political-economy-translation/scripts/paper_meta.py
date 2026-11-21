#!/usr/bin/env python3
"""Write a YAML front matter block describing the paper being translated.

The point is not decoration. A translated paper gets reused for other things
later — building a bibliography, checking which texts used a given rendering,
re-translating after the source PDF changes, counting how much of a corpus is
already done. None of that works if the metadata only exists in a chat log.

What goes in, and why each field earns its place:

* Identity — title, authors, year, journal, DOI. Needed to cite the thing and
  to notice when two files are the same paper.
* Process — date, translator, how the text was extracted. Enough to say where
  this file came from without keeping a chat log alive.
* Fidelity — block/paragraph/citation/formula counts and the check verdict.
  Lets you filter a corpus by "translations that actually passed" instead of
  trusting filenames.

Deliberately **not** here: copyright line, funding, ORCID, school of thought,
source-file hash, glossary path, term count, review backlog, draft flag. Those
were either never read back by anything, or are derivable from the files
themselves; keeping them made every front matter block three times longer than
the information it carried. If a one-off detail really has to survive, put a
sentence in `notes`.

Nothing here is invented. Fields the script cannot read are left empty rather
than guessed.

Usage:
    python paper_meta.py --init paper_原文.md -o _work/meta.yaml
    python paper_meta.py --inject paper_zh.md --meta _work/meta.yaml
    python paper_meta.py --check paper_zh.md
"""

import argparse
import datetime
import hashlib
import os
import re
import sys

FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)
DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
YEAR = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
H1 = re.compile(r"^#\s+(.+)$", re.M)
KEYWORDS = re.compile(r"^\s*(?:key\s*words?|关键词)\s*[:：]\s*(.+)$", re.I | re.M)

FIELDS = [
    ("title", "原文标题，取自原文 H1；若 H1 是期刊名，手动改成论文标题"),
    ("title_zh", "中译标题"),
    ("authors", "作者，`姓, 名` 形式，列表"),
    ("year", "出版年"),
    ("journal", "期刊或出版社；书章填书名"),
    ("volume", ""), ("issue", ""), ("pages", ""),
    ("doi", ""),
    ("keywords", "关键词，列表"),
    ("jel", "JEL 分类号"),
    ("notes", "特刊名、会议地点、资助与审批号等无处可放、又确实要留档的一句话"),
    ("type", "article | chapter | review | lecture | working-paper"),
    ("translated_at", "翻译完成日期"),
    ("translator", ""),
    ("extraction", "mineru-vlm | mineru-ocr | docx | native-md"),
    ("fidelity", "块数、段落数、引用数、公式数、校验结论"),
]


def read(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def strip_frontmatter(text):
    m = FRONT.match(text)
    return text[m.end():] if m else text


def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def guess_title(text):
    """First H1. MinerU often puts the journal name there instead, so this is a
    starting point, not an answer — the caller is expected to correct it."""
    lines = text.strip().split("\n")[:40]
    for line in lines:
        m = H1.match(line.strip())
        if m:
            return m.group(1).strip()
    # No heading: the first non-empty, non-decorative line is usually the title.
    for line in lines:
        s = line.strip(" #>*|-")
        if len(s) > 15 and not DOI.search(s):
            return s
    return ""


def guess_year(text, path):
    """Year from the filename first, then from the opening lines.

    Scanning the whole body finds whatever year appears first — usually a
    citation from the 1970s in the introduction, not the paper's own date.
    """
    name = os.path.basename(os.path.dirname(path)) + " " + os.path.basename(path)
    for m in re.finditer(r"\b(19[5-9]\d|20[0-4]\d)\b", name):
        return m.group(1)
    # Fall back to the first year in the opening lines only.
    head = "\n".join(text.strip().split("\n")[:25])
    for m in re.finditer(r"\b(19[5-9]\d|20[0-4]\d)\b", head):
        return m.group(1)
    return ""


def guess_keywords(text):
    m = KEYWORDS.search(text[:8000])
    if not m:
        return []
    raw = m.group(1).strip().rstrip(".")
    return [k.strip() for k in re.split(r"[;,；、]", raw) if k.strip()][:8]


def stats(body):
    """Count what the fidelity checker counts, so the numbers mean the same
    thing in both places."""
    lines = body.split("\n")
    blocks = len([b for b in re.split(r"\n\s*\n", body) if b.strip()])
    paras = 0
    buf = []
    for line in lines:
        if not line.strip():
            if buf:
                paras += 1
                buf = []
            continue
        buf.append(line)
    if buf:
        paras += 1
    display = len(re.findall(r"^\$\$", body, re.M)) // 2
    inline = len(re.findall(r"(?<!\$)\$(?!\$)[^$\n]+\$(?!\$)", body))
    citations = len(set(re.findall(r"\((?:[A-Z][A-Za-z\-']+(?: et al\.|,)?[^()]{0,40})(?:19|20)\d{2}[a-z]?(?:, p{1,2}\. ?\d+)?\)", body)))
    images = len(re.findall(r"!\[[^\]]*\]\([^)]+\)", body))
    return {
        "blocks": blocks, "paragraphs": paras, "citations": citations,
        "math_display": display, "math_inline": inline, "images": images,
    }


def yaml_scalar(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if re.search(r"[:#\[\]{}&*!|>'\"%@`]|^\s|\s$", s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def render(meta, indent=0):
    out = []
    pad = "  " * indent
    for k, v in meta.items():
        if isinstance(v, dict):
            out.append(f"{pad}{k}:")
            out.extend(render(v, indent + 1))
        elif isinstance(v, list):
            if not v:
                out.append(f"{pad}{k}: []")
            else:
                out.append(f"{pad}{k}:")
                for item in v:
                    out.append(f"{pad}  - {yaml_scalar(item)}")
        else:
            out.append(f"{pad}{k}: {yaml_scalar(v)}")
    return out


def build(source_path, target_path=None):
    text = read(source_path)
    body = strip_frontmatter(text)
    # Fidelity numbers describe the translation, so take them from the target
    # when there is one. Before translating, they describe the source.
    st = stats(strip_frontmatter(read(target_path))) if target_path else stats(body)
    m = DOI.search(body)
    meta = {
        "title": guess_title(body),
        "title_zh": "",
        "authors": [],
        "year": guess_year(body, source_path),
        "journal": "",
        "volume": "", "issue": "", "pages": "",
        "doi": m.group(0) if m else "",
        "keywords": guess_keywords(body),
        "jel": "",
        "notes": "",
        "type": "article",
        "translated_at": datetime.date.today().isoformat(),
        "translator": "",
        "extraction": "",
        "fidelity": {**st, "status": ""},
    }
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成或写入译文的 YAML front matter")
    ap.add_argument("--init", metavar="原文路径", help="从原文生成一份元信息草稿")
    ap.add_argument("--inject", metavar="译文路径", help="把元信息写入译文开头")
    ap.add_argument("--meta", help="--inject 时读取的 YAML 文件")
    ap.add_argument("--check", metavar="译文路径", help="检查 front matter 是否齐全")
    ap.add_argument("-o", "--out", help="--init 的输出路径")
    args = ap.parse_args(argv)

    if args.init:
        meta = build(args.init)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write("---\n" + "\n".join(render(meta)) + "\n---\n")
            print(f"已写出 {args.out}")
            print("字段说明：")
            for k, desc in FIELDS:
                if desc:
                    print(f"  {k:16} {desc}")
            print("\ntitle 与 authors 常需要人工改：MinerU 的 H1 常是期刊名而不是论文标题。")
        else:
            print("---\n" + "\n".join(render(meta)) + "\n---")
        return

    if args.inject:
        if not args.meta or not os.path.isfile(args.meta):
            sys.exit("需要 --meta 指向一份 YAML。")
        meta_text = read(args.meta)
        m = FRONT.match(meta_text if meta_text.endswith("\n") else meta_text + "\n")
        block = m.group(1) if m else meta_text.strip().strip("-").strip()
        body = strip_frontmatter(read(args.inject))
        with open(args.inject, "w", encoding="utf-8") as fh:
            fh.write("---\n" + block.strip() + "\n---\n\n" + body.lstrip("\n"))
        print(f"已写入 {args.inject} 的 front matter（{len(block.strip().splitlines())} 行）")
        return

    if args.check:
        text = read(args.check)
        m = FRONT.match(text)
        if not m:
            print("✗ 没有 front matter")
            sys.exit(1)
        block = m.group(1)
        # 著录类字段是"有则必须留档"，但不必每篇都有（没有 JEL 的论文不该
        # 判失败），所以只做提示，不进 missing。
        optional = {"keywords", "jel", "notes", "extraction"}
        missing = [k for k, _ in FIELDS
                   if k not in optional and not re.search(rf"^{k}:", block, re.M)]
        soft = [k for k in optional if not re.search(rf"^{k}:", block, re.M)]
        empty = []
        for k in ("title", "title_zh", "year", "authors"):
            mm = re.search(rf"^{k}:\s*(.*)$", block, re.M)
            if mm and mm.group(1).strip() in ("", '""', "[]"):
                empty.append(k)
        print(f"字段 {len(block.splitlines())} 行，缺失 {len(missing)}，空值 {len(empty)}")
        if missing:
            print("缺失：", "、".join(missing))
        if soft:
            print("未著录（有则补，无则略）：", "、".join(soft))
        if empty:
            print("空值：", "、".join(empty))
        # 旧版留下的一堆字段：还留着就提一句，别让两份口径混着走。
        stale = [k for k in ("copyright", "school", "language", "orcid", "funding",
                             "source_file", "source_sha256", "glossary", "terms_used",
                             "review_open", "draft")
                 if re.search(rf"^{k}:", block, re.M)]
        if stale:
            print("已废弃字段仍在（建议删掉，信息进 notes）：", "、".join(stale))
        sys.exit(0 if not missing and not empty else 1)

    ap.error("需要 --init、--inject 或 --check 之一。")


if __name__ == "__main__":
    main()
