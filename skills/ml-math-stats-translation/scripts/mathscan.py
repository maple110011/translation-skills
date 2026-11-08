#!/usr/bin/env python3
"""Locate every math span in a Markdown document — shared by the other scripts.

`math_fidelity.py` needs it to compare source against target formula by
formula; `notation.py` needs it to build and check the notation table. Two
scanners would drift apart, and then "the formula is identical" would mean two
different things in the same delivery.

What counts as a span
---------------------
* display: ``$$ ... $$``, ``\\[ ... \\]``, and the LaTeX display environments
  (equation, align, gather, multline, eqnarray, displaymath, split, aligned)
* inline: ``$ ... $`` and ``\\( ... \\)``

Fenced code and inline code are blanked out first, so a ``$`` inside a shell
snippet is not mistaken for math. Overlaps are resolved in favour of the
longest match starting earliest, which is what makes a multi-line ``$$`` block
win over the inline ``$`` inside it.

The one thing this cannot do is parse LaTeX. It finds delimiters, not
structure; ``\\[2pt]`` inside a matrix is handled by the ``(?<!\\\\)`` guard,
not by understanding that it is a row separator.
"""

from __future__ import annotations

import re

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")

# Order matters only for the tie-break below; kind is reported, not used to
# decide precedence.
ENV_NAMES = (r"equation\*?|align\*?|aligned|gather\*?|multline\*?|eqnarray\*?"
             r"|displaymath|split")

PATTERNS = [
    ("display", re.compile(r"\\begin\{(" + ENV_NAMES + r")\}(.+?)\\end\{\1\}", re.S), 2),
    ("display", re.compile(r"\$\$(.+?)\$\$", re.S), 1),
    ("display", re.compile(r"(?<!\\)\\\[(.+?)(?<!\\)\\\]", re.S), 1),
    ("inline", re.compile(r"(?<!\\)\$(?!\$)([^$\n]+?)(?<!\\)\$"), 1),
    ("inline", re.compile(r"\\\((.+?)\\\)", re.S), 1),
]

NOTATION_START = re.compile(r"<!--\s*notation:start\s*-->", re.I)
NOTATION_END = re.compile(r"<!--\s*notation:end\s*-->", re.I)
NOTATION_HEAD = re.compile(r"^(#{1,6})\s*(?:符号一览|符号表|记号表|记号说明|notation|符号说明)\s*$",
                           re.I | re.M)

# 译文开头还有一张「保留英文术语一览」：同样是本次翻译新增的元信息，
# 原文没有对应物。若留在正文里，结构对账会把它算成「多一个标题 + N 行
# 表格」，公式比对会把表里的 $...$ 当成多出的公式。
KEPT_START = re.compile(r"<!--\s*kept-terms:start\s*-->", re.I)
KEPT_END = re.compile(r"<!--\s*kept-terms:end\s*-->", re.I)
KEPT_HEAD = re.compile(
    r"^(#{1,6})\s*(?:保留英文术语一览|保留英文术语|英文术语一览|未译术语一览|kept\s*terms?)\s*$",
    re.I | re.M)

FIGURE_START = re.compile(r"<!--\s*figure:start\s*-->", re.I)
FIGURE_END = re.compile(r"<!--\s*figure:end\s*-->", re.I)
FIGURE_BLOCK = re.compile(r"<!--\s*figure:start\s*-->.*?<!--\s*figure:end\s*-->", re.S | re.I)
# Sentinel path used when a figure block is collapsed for auditing. It is not a
# real file, so anything that looks at paths must skip it.
FIGURE_SENTINEL = "__figure_block__"


class Span:
    """One formula, with what is needed to report on it."""

    __slots__ = ("start", "end", "body", "kind", "line")

    def __init__(self, start, end, body, kind, line):
        self.start, self.end, self.body, self.kind, self.line = start, end, body, kind, line

    @property
    def text(self):
        """Canonical form used for comparison: whitespace collapsed only.

        Anything more — normalising ``\\left(`` to ``(``, ``\\dfrac`` to
        ``\\frac``, ``\\varepsilon`` to ``\\epsilon`` — would hide exactly the
        edits this module exists to catch.
        """
        return canon(self.body)

    def __repr__(self):
        return f"Span({self.kind}, line {self.line}, {self.text[:40]!r})"


def canon(body):
    return re.sub(r"\s+", " ", body or "").strip()


INLINE_CODE = re.compile(r"`[^`\n]+`")


def blank_code(text):
    """Replace fenced code (and inline code) with spaces, keeping offsets intact."""
    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(" " * len(line))
            continue
        if in_fence:
            out.append(" " * len(line))
            continue
        out.append(INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line))
    return "\n".join(out)


def scan(text):
    """Return the math spans of ``text`` in document order."""
    body = blank_code(text)
    found = []
    for kind, rx, group in PATTERNS:
        for m in rx.finditer(body):
            found.append((m.start(), m.end(), m.group(group), kind))
    # Longest-at-earliest wins: a $$...$$ block beats the $...$ inside it.
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    spans, last_end = [], -1
    for start, end, inner, kind in found:
        if start < last_end:
            continue
        spans.append(Span(start, end, inner, kind, body.count("\n", 0, start) + 1))
        last_end = end
    return spans


TEXT_CMD = re.compile(r"\\(?:text|mbox|textit|textbf|textrm|textnormal|textsf)\s*\{[^{}]*\}")


def strip_text_bodies(s):
    """Drop the prose inside ``\\text{...}`` so a translated label is not
    reported as a changed formula. The rest of the body must still match."""
    return TEXT_CMD.sub(lambda m: m.group(0).split("{")[0] + "{}", canon(s))


def _strip_meta_block(text, start_rx, end_rx, head_rx):
    """Remove one workflow-added metadata block from the document.

    Marked blocks are removed exactly; unmarked ones are removed from the
    heading down to the next heading of the same or a higher level, which is
    the best guess available.
    """
    m = start_rx.search(text)
    if m:
        e = end_rx.search(text, m.end())
        if e:
            return text[:m.start()] + text[e.end():]
    h = head_rx.search(text)
    if not h:
        return text
    level = len(h.group(1))
    tail = text[h.end():]
    stop = len(tail)
    for m2 in re.finditer(r"^(#{1,6})\s+\S", tail, re.M):
        if len(m2.group(1)) <= level:
            stop = m2.start()
            break
    return text[:h.start()] + tail[stop:]


def strip_notation(text):
    """Remove workflow-added metadata blocks before structural comparison.

    符号一览 and 保留英文术语一览 are both metadata that this workflow *adds* —
    neither has a counterpart in the source, so leaving them in makes the target
    look like it gained headings plus table rows (and the math inside them look
    like extra formulas).
    """
    text = _strip_meta_block(text, NOTATION_START, NOTATION_END, NOTATION_HEAD)
    return _strip_meta_block(text, KEPT_START, KEPT_END, KEPT_HEAD)


def notation_block(text):
    """Return the 符号一览 block as text, or ''."""
    m = NOTATION_START.search(text)
    if m:
        e = NOTATION_END.search(text, m.end())
        return text[m.end():e.start()] if e else text[m.end():]
    h = NOTATION_HEAD.search(text)
    if not h:
        return ""
    level = len(h.group(1))
    tail = text[h.end():]
    for m2 in re.finditer(r"^(#{1,6})\s+\S", tail, re.M):
        if len(m2.group(1)) <= level:
            return tail[:m2.start()]
    return tail


def figure_blocks(text):
    return FIGURE_BLOCK.findall(text)


def count_figure_blocks(text):
    return len(FIGURE_BLOCK.findall(text))


def collapse_figures(text):
    """Replace each 并排图块 with a single image line.

    A figure block is a three-line HTML table plus two comments; left alone it
    would count as one paragraph and zero images, while the source has one
    image paragraph. Collapsing it to one line keeps the block sequence aligned
    and lets the image count stay meaningful (one block = one logical figure,
    however many panels it holds).
    """
    return FIGURE_BLOCK.sub(f"![figure]({FIGURE_SENTINEL})", text)
