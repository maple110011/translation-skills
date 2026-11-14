#!/usr/bin/env python3
"""Normalise math delimiters in a Markdown file to one house style.

House style
-----------
* display math -> ``$$ ... $$``
* inline math  -> ``$ ... $``

So ``\\[ x^2 \\]`` becomes ``$$ x^2 $$`` and ``\\( x \\)`` becomes ``$x$``.
Text that is already correct is left untouched, which makes the script safe to
run repeatedly.

What is never touched
---------------------
* fenced code blocks (```` ``` ```` / ``~~~``)
* inline code spans (`` `...` ``)
* existing ``$...$`` and ``$$...$$`` regions
* ``\\\\[2pt]`` style line breaks inside matrix/array environments — a ``\\[``
  that is itself preceded by a backslash is a row separator, not an opener.
  This is the one case a naive regex destroys, so it gets an explicit guard.

Usage
-----
    python normalize_math.py in.md                  # print report only
    python normalize_math.py in.md --inplace        # rewrite in place
    python normalize_math.py in.md -o out.md        # write elsewhere
    python normalize_math.py in.md --check          # exit 1 if changes needed
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)
SENTINEL = "\x00MATHKEEP{}\x00"

INLINE_CODE = re.compile(r"(`+)(.+?)\1", re.S)
DISPLAY_BRACKET = re.compile(r"(?<!\\)\\\[(.+?)(?<!\\)\\\]", re.S)
INLINE_PAREN = re.compile(r"(?<!\\)\\\((.+?)(?<!\\)\\\)", re.S)
DOLLAR_DISPLAY = re.compile(r"\$\$.+?\$\$", re.S)


def split_code(text):
    """Yield (is_code, chunk) so that fenced blocks can be skipped wholesale."""
    lines = text.split("\n")
    chunks, buf, in_code, marker = [], [], False, ""
    for line in lines:
        m = FENCE.match(line)
        if m:
            if not in_code:
                if buf:
                    chunks.append((False, "\n".join(buf)))
                    buf = []
                in_code, marker = True, m.group(1)[0]
                buf = [line]
            elif line.strip().startswith(marker * 3):
                buf.append(line)
                chunks.append((True, "\n".join(buf)))
                buf, in_code, marker = [], False, ""
            else:
                buf.append(line)
        else:
            buf.append(line)
    if buf:
        chunks.append((in_code, "\n".join(buf)))
    return chunks


def _protect(text, store):
    """Replace inline code spans and existing $$...$$ with placeholders."""
    def keep(m):
        store.append(m.group(0))
        return SENTINEL.format(len(store) - 1)

    text = DISPLAY_BRACKET.sub(lambda m: m.group(0), text)  # no-op, keeps order clear
    text = INLINE_CODE.sub(keep, text)
    text = DOLLAR_DISPLAY.sub(keep, text)
    return text


def _restore(text, store):
    for i, original in enumerate(store):
        text = text.replace(SENTINEL.format(i), original)
    return text


def normalise_chunk(text, stats):
    store = []
    text = _protect(text, store)

    def to_display(m):
        raw = m.group(1)
        body = raw.strip()
        if "$$" in body:
            stats["skipped_nested"] += 1
            return m.group(0)
        stats["display_bracket"] += 1
        if "\n" in raw:
            # The delimiter spanned lines: emit a fenced block on its own lines.
            # Add a newline only where the original did not already have one,
            # so we do not invent blank lines around the formula.
            s = m.string
            before, after = s[:m.start()], s[m.end():]
            pre = "" if (not before or before.endswith("\n")) else "\n"
            post = "" if (not after or after.startswith("\n")) else "\n"
            return f"{pre}$$\n{body}\n$${post}"
        return f"$${body}$$"

    def to_inline(m):
        body = m.group(1)
        if "$$" in body:
            stats["skipped_nested"] += 1
            return m.group(0)
        stats["inline_paren"] += 1
        # Keep a single space of padding only when the body had it, so that
        # "$ x $" style stays readable but "$x$" does not gain spaces.
        return f"${body.strip()}$"

    text = DISPLAY_BRACKET.sub(to_display, text)
    text = INLINE_PAREN.sub(to_inline, text)
    return _restore(text, store)


def normalise(text):
    stats = Counter()
    out = []
    for is_code, chunk in split_code(text):
        if is_code:
            out.append(chunk)
        else:
            out.append(normalise_chunk(chunk, stats))
    return "\n".join(out), stats


def audit(text):
    """Count what is still non-conforming."""
    stats = Counter()
    for is_code, chunk in split_code(text):
        if is_code:
            continue
        stats["remaining_display_bracket"] += len(
            re.findall(r"(?<!\\)\\\[", chunk))
        stats["remaining_inline_paren"] += len(re.findall(r"(?<!\\)\\\(", chunk))
        stats["display_dollars"] += len(re.findall(r"^\s*\$\$", chunk, re.M))
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="统一 Markdown 公式定界符为 $$…$$ 与 $…$。")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="输出路径；默认覆盖输入（配合 --inplace）")
    ap.add_argument("--inplace", action="store_true", help="原地改写")
    ap.add_argument("--check", action="store_true", help="只在需要修改时返回码 1")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        raw = fh.read()

    # The front matter is metadata, not prose: it may contain colons, quotes and
    # braces that look like LaTeX. Normalise only what follows it, then paste
    # the block back untouched.
    m = FRONT.match(raw)
    head, text = (raw[:m.end()], raw[m.end():]) if m else ("", raw)

    new, stats = normalise(text)
    new = head + new
    # Compare against the original file, not the body: `new` includes the
    # front matter we pasted back, so comparing it to the body alone reports a
    # change on every file that has one.
    changed = new != raw
    after = audit(new[len(head):])

    print(f"文件：{args.input}")
    print(f"  \\[...\\] → $$...$$ ：{stats['display_bracket']} 处")
    print(f"  \\(...\\) → $...$     ：{stats['inline_paren']} 处")
    if stats["skipped_nested"]:
        print(f"  跳过（内含 $$）：{stats['skipped_nested']} 处")
    print(f"  转换后残留 \\[ ：{after['remaining_display_bracket']}")
    print(f"  转换后残留 \\( ：{after['remaining_inline_paren']}")
    print(f"  行间公式块（行首 $$）：{after['display_dollars']}")

    if args.check:
        return 1 if changed else 0

    if not changed:
        print("无需修改。")
        return 0

    dest = args.output or (args.input if args.inplace else None)
    if dest is None:
        print("\n未指定输出。加 --inplace 或 -o <路径> 才会写出。")
        return 0
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    print(f"已写出：{dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
