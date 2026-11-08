"""从 Markdown 里抽出英文引文（含引用串），供 article.py 逐条匹配。

只做抽取、不做匹配——单独用也行：先看看一篇文章里能抓到多少条、有没有漏。

处理的形态
----------
* 引用块：`> "The wealth of those societies..."`（可跨多行）
* 行内引号：`the "immense accumulation of commodities" ...`
* 引号后紧跟的引用串：`(MECW 35: 436)`、`(Capital I, p. 163)`、`(Marx 1976: 163)`

刻意跳过的
----------
* 代码块（``` 与 ~~~）、行内代码、HTML 注释、YAML front matter
* 已经含中文的引文（视为已译）
* 中文引号「」，以及 《》 里的书名
"""
import re

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
BQ = re.compile(r"^\s{0,3}>\s?")
# 行内引号：中英文引号都认，内部不允许跨行
INLINE = re.compile(r"(?:[“\"])([^“”\"\n]{12,})(?:[”\"])")
# 引号后面紧跟的引用串
CITE = re.compile(r"^[ \t]*[（(]\s*([^）)\n]{3,90}?)\s*[）)]")
CITE_HINT = re.compile(r"(MECW|MEW|MEGA|Marx|Engels|Capital|Grundrisse|p\.|pp\.|\d{4})", re.I)

STRIP_MD = [
    (re.compile(r"\*\*(.+?)\*\*", re.S), r"\1"),
    (re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S), r"\1"),
    (re.compile(r"__(.+?)__", re.S), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),      # [text](url) → text
    (re.compile(r"<[^>]+>"), " "),
]


def clean(text: str) -> str:
    """去掉 Markdown 修饰，压平空白，便于匹配。"""
    s = text
    for pat, rep in STRIP_MD:
        s = pat.sub(rep, s)
    s = s.replace("\u00ad", "").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\"'—–-")


def is_english(text: str) -> bool:
    if len(text) < 12:
        return False
    # LaTeX 片段常被引号包着（"\mathrm{P}\left(..."），不是引文
    if "\\" in text or text.count("{") >= 2 or text.count("_") >= 3:
        return False
    if len(re.findall(r"[A-Za-z]{2,}", text)) < 4:      # 至少几个真单词
        return False
    latin = len(LATIN.findall(text))
    cjk = len(CJK.findall(text))
    if cjk > 2:                       # 已含中文，视为已译或非目标
        return False
    return latin / max(1, len(text)) > 0.45


def _cite_after(s: str, pos: int):
    m = CITE.match(s[pos:pos + 120])
    if m and CITE_HINT.search(m.group(1)):
        return m.group(1).strip()
    return None


def extract(md: str):
    """返回 [{start, end, text, raw, kind, citation, line}]，start/end 是原文偏移。

    kind = "block"（引用块）| "inline"（行内引号）
    """
    out = []
    lines = md.splitlines(keepends=True)
    offs, acc = [], 0
    for ln in lines:
        offs.append(acc)
        acc += len(ln)

    i, in_fence, in_front = 0, False, False
    # YAML front matter
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() in ("---", "..."):
                i = k + 1
                in_front = True
                break

    while i < len(lines):
        line = lines[i]

        if FENCE.match(line):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue

        # ---- 引用块 ----
        if BQ.match(line):
            j = i
            while j < len(lines) and BQ.match(lines[j]):
                j += 1
            body_lines = [BQ.sub("", lines[k]).rstrip("\n") for k in range(i, j)]
            # 块里常把引用串单独放一行（"> （MECW 35: 125）"）。它是出处、不是正文，
            # 混进匹配文本会让"数字自检"误判（35、125 在中文里当然找不到）。
            cite_block = None
            used = body_lines
            if len(body_lines) > 1:
                last = body_lines[-1].strip()
                m = re.fullmatch(r"[（(]\s*([^）)]{3,90}?)\s*[）)]", last)
                if m and CITE_HINT.search(m.group(1)):
                    cite_block = m.group(1).strip()
                    used = body_lines[:-1]
            body = "\n".join(used)
            t = clean(body)
            if is_english(t) and len(t) >= 20:
                start = offs[i]
                end = offs[j - 1] + len(lines[j - 1].rstrip("\r\n"))
                out.append({
                    "start": start, "end": end, "kind": "block",
                    "text": t, "raw": body.strip(),
                    "citation": cite_block or _cite_after(md, end),
                    "line": i + 1,
                })
            i = j
            continue

        # ---- 行内（跳过 HTML 注释与行内代码）----
        seg = re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)
        seg = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), seg)
        for m in INLINE.finditer(seg):
            inner = m.group(1)
            t = clean(inner)
            if not is_english(t) or len(t) < 20:
                continue
            s = offs[i] + m.start()
            e = offs[i] + m.end()
            out.append({
                "start": s, "end": e, "kind": "inline",
                "text": t, "raw": m.group(0),
                "citation": _cite_after(md, e),
                "line": i + 1,
            })
        i += 1

    # 按位置排序，并丢弃被引用块包含的行内结果（块引用里常带引号，会重复抓）
    out.sort(key=lambda x: (x["start"], -x["end"]))
    dedup = []
    for c in out:
        if dedup and c["start"] < dedup[-1]["end"]:
            if c["end"] <= dedup[-1]["end"]:
                continue
        dedup.append(c)
    return dedup


if __name__ == "__main__":
    import sys, json
    md = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    items = extract(md)
    print(f"抽出 {len(items)} 条\n")
    for k, c in enumerate(items, 1):
        print(f"{k}. [{c['kind']}] L{c['line']}  {c['text'][:88]}")
        if c["citation"]:
            print(f"     引用串: {c['citation']}")
