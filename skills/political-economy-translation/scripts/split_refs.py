#!/usr/bin/env python3
"""Take the bibliography out of the translation payload, then put it back verbatim.

Why
---
The bibliography is the one part of a paper that must survive *unchanged*: rule 4
already says every reference entry stays in its original language, character for
character. Sending it through the model buys nothing and costs three things:

* tokens — a long bibliography is often 10-20% of a paper's length;
* risk — a model asked to reproduce a hundred English entries will eventually
  "helpfully" translate a title, reorder a name, or normalise a dash;
* attention — effort spent on entries that need no effort is effort not spent
  on the argument.

So the region is cut before translating and spliced back as original bytes. No
model ever sees an entry.

How: one placeholder line, not a separate file
----------------------------------------------
The region is replaced by a single marker line::

    <!-- REFS-ORIGINAL lines=74 -->

Everything else — body, appendix, author biography, tables — stays in the file
and gets translated as usual. This matters because the bibliography is *not*
always the last block: ``## References`` is often followed by an appendix or a
note on the author, both of which must be translated. A hard "cut to EOF" would
silently drop them; a placeholder keeps them in place.

Restore replaces the marker with the original entries. If the marker is missing
or altered, restore stops and says where to look — it never guesses.

What gets cut
-------------
One region: from the last line that looks like a bibliography heading
(``## References``, ``## Bibliography``, ``**References**``, ``## 参考文献`` ...)
to the next heading of the same or shallower level, or to the end of file.

The script refuses to guess. It will not cut when

* no heading is found (reports and writes nothing);
* the region does not look like a bibliography (fewer than a quarter of its
  non-empty lines carry a four-digit year) — usually a false positive on a body
  section that happens to be titled "References".

Every cut is self-checking: body-with-placeholder plus the cut region must
rebuild the source line for line before anything is written.

Usage
-----
    python split_refs.py paper_en.md --check
    python split_refs.py paper_en.md -o _work/
    python split_refs.py --restore _work/paper_en_正文.md -o paper_zh.md
    python split_refs.py --restore body_zh.md -o out.md --heading 参考文献
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MARKER_PREFIX = "REFS-ORIGINAL"
MARKER = f"<!-- {MARKER_PREFIX} lines={{n}} -->"
MARKER_RE = re.compile(r"^\s*<!--\s*" + MARKER_PREFIX + r"[^>]*-->\s*$", re.IGNORECASE)

# A bibliography heading: optional hashes, optional bold markers, the word,
# an optional trailing colon, nothing else on the line.
HEADING = re.compile(
    r"^\s*(?P<hashes>#{1,6})?\s*(?:\*\*|__)?\s*"
    r"(?P<title>references?|bibliography|works\s+cited|literature\s+cited|"
    r"reference\s+list|参考文献|引用文献|主要参考文献)"
    r"\s*(?:\*\*|__)?\s*[：:]?\s*$",
    re.IGNORECASE,
)
ANY_HEADING = re.compile(r"^\s*(?P<hashes>#{1,6})\s+\S")
YEAR = re.compile(r"(?:1[6-9]|20)\d{2}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def split_lines(text: str) -> tuple[list[str], bool]:
    crlf = "\r\n" in text
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), crlf


def looks_like_bibliography(lines: list[str]) -> tuple[bool, float, int]:
    body = [ln for ln in lines if ln.strip()]
    if not body:
        return False, 0.0, 0
    with_year = sum(1 for ln in body if YEAR.search(ln))
    return with_year / len(body) >= 0.25, with_year / len(body), len(body)


def find_cut(lines: list[str]) -> dict:
    """Locate the bibliography region. Returns a report; never mutates input."""
    report = {
        "cut_line": None,
        "heading": None,
        "heading_level": None,
        "refs_end": None,
        "refs_lines": 0,
        "year_ratio": None,
        "warnings": [],
        "ok": False,
    }
    candidates = []
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        if match:
            candidates.append((i, len(match.group("hashes") or ""), line.strip()))
    if not candidates:
        report["warnings"].append("未找到参考文献标题，文件按原样处理（未切分）")
        return report

    # Last occurrence wins: the bibliography sits at the end of the front matter.
    cut, level, heading = candidates[-1]
    report.update(cut_line=cut + 1, heading=heading, heading_level=level)

    # Region ends at the next heading of the same or shallower level.
    refs_end = len(lines)
    for i in range(cut + 1, len(lines)):
        match = ANY_HEADING.match(lines[i])
        if not match:
            continue
        inner = len(match.group("hashes"))
        if (level and inner <= level) or (not level and inner <= 2):
            refs_end = i
            report["warnings"].append(
                f"参考文献后还有一节：{lines[i].strip()}（第 {i + 1} 行），"
                "它留在正文里照常翻译"
            )
            break

    refs = lines[cut:refs_end]
    ok, ratio, checked = looks_like_bibliography(refs[1:])
    report.update(refs_end=refs_end, refs_lines=len(refs),
                  year_ratio=round(ratio, 2), checked_lines=checked)
    if not ok:
        report["warnings"].append(
            f"切出的 {checked} 行里只有 {ratio:.0%} 含四位年份，不像书目；"
            "可能命中了正文里同名小节，未切分"
        )
        return report

    report["ok"] = True
    return report


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_output_name(body_path: Path) -> str:
    """paper_原文_正文.md -> paper_原文_zh.md, never back onto the source."""
    stem = source_stem(body_path)
    if not stem.endswith("_zh"):
        stem += "_zh"
    return stem + ".md"


def source_stem(body_path: Path) -> str:
    """Recover the split-time stem from a body or translated-body file name."""
    stem = body_path.stem
    if stem.endswith("_zh"):
        stem = stem[:-3]
    return stem.replace("_正文", "")


def do_check(args) -> int:
    path = Path(args.source)
    lines, _ = split_lines(read_text(path))
    rep = find_cut(lines)
    print(f"原文：{path}")
    if rep["cut_line"]:
        print(f"  切点：第 {rep['cut_line']} 行  {rep['heading']}")
        if rep["ok"]:
            print(f"  参考文献区 {rep['refs_lines']} 行"
                  f"（占全文 {rep['refs_lines'] / max(len(lines), 1):.0%}），"
                  f"正文 {len(lines) - rep['refs_lines']} 行")
    for w in rep["warnings"]:
        print(f"  · {w}")
    print("  结论：" + ("可以切分" if rep["ok"] else "不切分"))
    return 0 if rep["ok"] else 1


def do_split(args) -> int:
    path = Path(args.source)
    text = read_text(path)
    lines, crlf = split_lines(text)
    rep = find_cut(lines)

    print(f"原文：{path}")
    if not rep["ok"]:
        for w in rep["warnings"]:
            print(f"  ! {w}")
        print("  未写出文件。")
        return 1

    cut, end = rep["cut_line"] - 1, rep["refs_end"]
    body_lines = lines[:cut]
    refs_lines = lines[cut:end]
    tail_lines = lines[end:]
    marker = MARKER.format(n=len(refs_lines))
    new_lines = body_lines + [marker] + tail_lines

    # Self-check: body-with-marker plus the cut region must rebuild the source.
    if new_lines[:cut] + refs_lines + new_lines[cut + 1:] != lines:
        print("  ! 自检失败：切分后无法拼回原文，未写出文件")
        return 2

    out = Path(args.output or path.parent / "_work")
    out.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    body_path = out / f"{stem}_正文.md"
    refs_path = out / f"{stem}_参考文献.md"
    meta_path = out / f"{stem}_切分.json"

    body_text = "\n".join(new_lines).rstrip("\n") + "\n"
    refs_text = "\n".join(refs_lines).rstrip("\n") + "\n"
    body_path.write_text(body_text, encoding="utf-8")
    refs_path.write_text(refs_text, encoding="utf-8")

    meta = {
        "source": str(path.resolve()),
        "source_sha256": sha256(text),
        "newline": "CRLF" if crlf else "LF",
        "cut_line": rep["cut_line"],
        "refs_end_line": end,
        "heading": rep["heading"],
        "marker": marker,
        "body": str(body_path.name),
        "refs": str(refs_path.name),
        "refs_lines": rep["refs_lines"],
        "refs_chars": len(refs_text),
        "refs_sha256": sha256(refs_text),
        "year_ratio": rep["year_ratio"],
        "warnings": rep["warnings"],
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"  切点：第 {rep['cut_line']} 行  {rep['heading']}")
    print(f"  翻译用稿：{body_path}")
    print(f"    参考文献换成一行标记 {marker}，其余（含附录）原样保留")
    print(f"  参考文献（不进上下文）：{refs_path}  "
          f"{rep['refs_lines']} 行 / {len(refs_text)} 字符")
    print(f"  切分记录：{meta_path}")
    for w in rep["warnings"]:
        print(f"  · {w}")
    print("  翻译时只读翻译用稿；交付前用 --restore 原样拼回。")
    return 0


def do_restore(args) -> int:
    body_path = Path(args.restore)
    body = read_text(body_path)

    meta_path = body_path.parent / f"{source_stem(body_path)}_切分.json"
    refs_path = body_path.parent / f"{source_stem(body_path)}_参考文献.md"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        refs_path = body_path.parent / meta.get("refs", refs_path.name)
    else:
        print(f"  ! 未找到切分记录 {meta_path.name}，按默认文件名找参考文献")
    if not refs_path.exists():
        print(f"  ! 找不到参考文献文件：{refs_path}")
        return 2

    refs = read_text(refs_path)
    if meta.get("refs_sha256") and meta["refs_sha256"] != sha256(refs):
        print(f"  ! 参考文献文件与切分时不一致（{refs_path.name} 被改过？）")
        return 2

    lines = body.split("\n")
    hits = [i for i, line in enumerate(lines) if MARKER_RE.match(line)]
    if not hits:
        print("  ! 译文里找不到参考文献标记。可能被模型删掉或改写。")
        print(f"    应在原第 {meta.get('cut_line', '?')} 行附近插入："
              f"{meta.get('marker', MARKER.format(n=0))}")
        print("    手工补回该行后重跑，或直接把参考文献文件内容贴在原位置。")
        return 2
    if len(hits) > 1:
        print(f"  ! 标记出现 {len(hits)} 次（第 "
              f"{'、'.join(str(h + 1) for h in hits)} 行），无法判断插哪一处")
        return 2

    head, _, tail = refs.partition("\n")
    if args.heading and HEADING.match(head):
        refs = f"{args.heading}\n{tail}"

    replacement = refs.rstrip("\n").split("\n")
    # Keep the blank line that separates the bibliography from whatever follows
    # (appendix, note on the author); the marker line replaced exactly one line,
    # so the separator would otherwise be lost.
    if hits[0] + 1 < len(lines) and lines[hits[0] + 1].strip():
        replacement.append("")

    result = lines[:hits[0]] + replacement + lines[hits[0] + 1:]
    output = "\n".join(result).rstrip("\n") + "\n"

    out = Path(args.output) if args.output else body_path.with_name(
        default_output_name(body_path)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(output, encoding="utf-8")
    print(f"  已拼回：{out}")
    print(f"    译文正文 {len(lines) - 1} 行 + 参考文献 {refs.count(chr(10))} 行")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="切出参考文献区（不进翻译上下文），交付前原样拼回"
    )
    parser.add_argument("source", nargs="?", type=Path, help="原文 Markdown")
    parser.add_argument("-o", "--output", type=Path,
                        help="切分时是输出目录（默认 _work/）；拼回时是输出文件")
    parser.add_argument("--check", action="store_true", help="只报告切点，不写文件")
    parser.add_argument("--restore", metavar="译文",
                        help="把参考文献原样拼回译稿")
    parser.add_argument("--heading", help="拼回时替换参考文献标题，如 参考文献")
    args = parser.parse_args(argv)

    if args.restore:
        return do_restore(args)
    if not args.source:
        parser.error("需要原文路径，或使用 --restore")
    return do_check(args) if args.check else do_split(args)


if __name__ == "__main__":
    sys.exit(main())
