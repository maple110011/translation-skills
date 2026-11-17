#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把交付译稿转换成可直接粘贴进微信公众号编辑器的片段。

用法：
    python build_wechat.py <译稿.md> <输出目录>

输出：
    wechat_article.html   完整网页（可预览，点按钮复制）
    wechat_article.md     纯文本备份

为什么全部内联样式：
    微信公众号编辑器粘贴时会清掉 <style> 标签、<link>、class 选择器，只保留
    标签自带的 style 属性。用 class 写样式在本地好看，粘过去会散成无格式
    纯文本——这是最常踩的坑。所以本脚本不生成样式表、不写 class，每个元素
    的观感都写在它自己的 style 里。同时避开微信不认的属性：position、flex、
    grid、box-shadow、overflow、CSS 变量。

处理规则（与发布口径一致）：
1. 去掉标题（微信后台有独立标题栏）
2. 去掉参考文献整节
3. 脚注移到所注段落之后，用引用框呈现；正文保留上标标记
4. 开头两行：翻译&编辑 / 文献来源（APA 7）

脚注的写法在各条流程里并不统一，本脚本一律先归一、再挂载，不要求上游
迁就某一种形态：

| 来源 | 形态 |
|---|---|
| MinerU 原稿 | 正文 `<sup>n</sup>`，文末可能没有脚注正文 |
| `footnotes.py --patch` | 正文 `[^n]`，文末 `[^n]: ...`（可带 `<!-- FOOTNOTES-RECOVERED -->`） |
| 人工整理 / Pandoc / Typora | `## 脚注` 节里 `1. ...`、`(1) ...`、`- ...`、`注 1 ...`、`<sup>1</sup> ...`、`[^1]: ...` |

`harvest_footnotes()` 把这些定义全部收齐并从正文剥离，`normalize_marks()`
再把正文里的 `[^n]` 统一成 `<sup>n</sup>`，后续环节只认这一种内部形态。
`audit_notes()` 在写文件前硬校验：只要"定义了脚注却一条没进版面"、
"输出残留字面 `[^n]`"或"残留裸 `<sup>`"，一律报错返回非零，绝不静默降级。
"""
from __future__ import annotations

import html
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None


# ---- 全篇统一观感，集中在这里改 ----
INK = "#3f3f3f"          # 正文
HEAD = "#1f1f1f"         # 标题
MUTE = "#8a8a8a"         # 次要信息
ACCENT = "#a0321e"       # 强调色（暗朱红，印刷品常用）
RULE = "#e6e2da"         # 分隔线
PANEL = "#f6f4f0"        # 浅底
NOTE_BG = "#faf8f4"      # 注释框底
NOTE_BD = "#d8cbb6"      # 注释框竖线
FONT = ("-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
        "'Microsoft YaHei',sans-serif")


# ---------------------------------------------------------------- 解析 markdown
def split_front(text: str):
    m = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", text, re.S)
    if not m:
        return {}, text
    raw = m.group(1)
    meta = {}
    if yaml:
        try:
            meta = yaml.safe_load(raw) or {}
        except Exception:
            meta = {}
    if not meta:
        for line in raw.split("\n"):
            mm = re.match(r"([a-z_]+):\s*\"?(.*?)\"?\s*$", line)
            if mm:
                meta[mm.group(1)] = mm.group(2)
    return meta, text[m.end():]


def paragraphs_of(body: str):
    """切成结构块：(kind, payload)。kind ∈ h2/h3/caption/p/table/list。"""
    lines = body.split("\n")
    out, buf, i = [], [], 0

    def flush():
        nonlocal buf
        if buf:
            out.append(("p", " ".join(x.strip() for x in buf).strip()))
            buf = []

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
            continue
        m = re.match(r"^(#{2,6})\s+(.*)$", line)
        if m:
            flush()
            out.append(("h3" if len(m.group(1)) == 3 else "h2", m.group(2).strip()))
            i += 1
            continue
        if line.startswith("**") and line.rstrip().endswith("**") and not buf:
            flush()
            out.append(("caption", line.strip().strip("*").strip()))
            i += 1
            continue
        if line.lstrip().startswith("!["):
            figs = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            if figs:
                flush()
                out.append(("figures", figs))
                i += 1
                continue
        if line.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(("table", rows))
            continue
        if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*(?:[-*+]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", lines[i]).strip())
                i += 1
            out.append(("list", items))
            continue
        buf.append(line)
        i += 1
    flush()
    return out


# ---------------------------------------------------------------- 脚注：归一与抽取
#
# 上游三种写法必须都能进：MinerU 的 <sup>n</sup>、footnotes.py --patch 与
# Pandoc 的 [^n] / [^n]:、人工整理的 ## 脚注 节。本节把这三种先收敛成
# "编号 → 正文" 的字典 + 只带 <sup>n</sup> 的正文，后面的挂载与渲染
# 就只需要处理一种形态。

NOTE_HEADINGS = {
    "脚注", "注释", "注", "尾注", "注解", "脚注与注释", "注释与说明",
    "notes", "note", "footnotes", "footnote", "endnotes", "endnote",
}
REF_HEADINGS = {
    "参考文献", "引用文献", "参考书目", "文献目录",
    "references", "reference", "bibliography", "works cited",
}
UNICODE_SUP = {"\u00b9": 1, "\u00b2": 2, "\u00b3": 3, "\u2074": 4,
               "\u2075": 5, "\u2076": 6, "\u2077": 7, "\u2078": 8, "\u2079": 9}
SUP_IN_TEXT = re.compile(r"<sup>[ \t]*([\w-]{1,8})[ \t]*</sup>", re.I)
FN_REF = re.compile(r"\[\^([\w-]{1,8})\](?![:：])")
FENCE = re.compile(r"^[ \t]*(?:```|~~~)")


def _norm_heading(text: str) -> str:
    """'## 7. 脚注' / '**Notes**' 一律还原成可比对的小写裸名。"""
    t = text.strip().strip("*_ \t")
    t = re.sub(r"^[\d一二三四五六七八九十]+\s*[.、．)）]\s*", "", t)
    t = re.sub(r"[\s\u3000]+", " ", t)
    return t.strip().lower()


def is_note_heading(text: str) -> bool:
    return _norm_heading(text) in NOTE_HEADINGS


def is_ref_heading(text: str) -> bool:
    return _norm_heading(text) in REF_HEADINGS


def _join_lines(parts) -> str:
    """把折行的脚注正文接成一段。

    行末连字符有两种来源，得分开处理：PDF 硬断词（`abso-` + `lute`）要去掉
    连字符拼回去；复合专名（`Kaldor-` + `Verdoorn`）的连字符是词本身的一部分，
    去掉就成了 KaldorVerdoorn。判据取"下一行首字母是否大写"——硬断词的下半截
    永远是小写，能撞上大写的只有专名。
    """
    out = ""
    for raw in parts:
        cur = raw.strip()
        if not cur:
            continue
        if not out:
            out = cur
        elif out.endswith("-") and cur[:1].isalpha():
            if cur[:1].isupper():
                out = out + cur            # Kaldor- + Verdoorn -> Kaldor-Verdoorn
            else:
                out = out[:-1] + cur       # abso- + lute -> absolute
        else:
            out += " " + cur
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _entry_head(line: str):
    """这一行是不是一条脚注的开头？返回 (编号或 None, 行内正文) / None。

    形态按"越具体越先试"排：`<sup>1</sup>`、`[^1]:`、`注 1`、`- `、`1.`。
    编号统一按字符串处理——脚注号偶尔是字母（作者单位角标）。
    """
    m = re.match(r"^[ \t]*<sup>[ \t]*([\w-]{1,4})[ \t]*</sup>[ \t\u3000]*(.*)$", line, re.I)
    if m:
        return (m.group(1), m.group(2))
    m = re.match(r"^[ \t]*\[\^([\w-]{1,8})\][:：]?[ \t]*(.*)$", line)
    if m:
        return (m.group(1), m.group(2))
    m = re.match(r"^[ \t]*注[ \t\u3000]*(\d{1,3})[ \t\u3000:：.．、)）]*(.*)$", line)
    if m:
        return (m.group(1), m.group(2))
    m = re.match(r"^[ \t]*(?:[-*+])[ \t]+(.*)$", line)
    if m:
        return (None, m.group(1))
    # 1. / 1) / 1、/ 1．/ (1) / （1）——限定 1-3 位，挡掉 "2020. xxx" 这类年份开头
    m = re.match(r"^[ \t]*[(（]?(\d{1,3})[)）.．、][ \t]*(.*)$", line)
    if m:
        return (m.group(1), m.group(2))
    return None


def _max_num_key(defs) -> int:
    nums = [int(k) for k in defs if str(k).isdigit()]
    return max(nums) if nums else 0


def _parse_note_block(lines, defs: dict) -> None:
    """把 `## 脚注` 节里的行拆成一条条定义，写进 defs。

    条目之间的分界靠 `_entry_head`；不是条目开头的行一律算上一条的续行
    （脚注折行很常见）。没有显式编号的条目（`- xxx`）按出现次序顺延，
    且顺延值会跟着显式编号跳，避免 `1. 2. -` 这种混排撞号。
    """
    seq = _max_num_key(defs) + 1
    key, parts = None, []

    def flush():
        nonlocal key, parts
        if key is not None:
            body = _join_lines(parts)
            if body:
                prev = defs.get(key)
                defs[key] = (prev + " " + body).strip() if prev else body
        key, parts = None, []

    for raw in lines:
        if not raw.strip():
            continue
        if re.fullmatch(r"[ \t]*([-*_])\1{2,}[ \t]*", raw):   # --- / *** / ___ 分隔线
            continue
        head = _entry_head(raw)
        if head:
            flush()
            num, rest = head
            if num:
                key = str(num)
                if num.isdigit():
                    seq = int(num) + 1
            else:
                key = str(seq)
                seq += 1
            parts = [rest]
        elif key is not None:
            parts.append(raw)
    flush()


def harvest_footnotes(body: str):
    """收齐全篇脚注定义并从正文剥离。返回 (defs, 正文)。

    顺序不能反：先把 `## 脚注` 整节和 `[^n]:` 定义都摘走，再走块解析。
    否则 `1. xxx` 会被 paragraphs_of 当成普通有序列表，`[^1]: A` 与
    `[^2]: B` 相邻时又会被 flush() 拼成一段，编号信息直接烂掉。
    """
    lines = body.split("\n")
    defs: dict = {}
    keep: list = []
    i, n = 0, len(lines)
    in_fence = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if FENCE.match(line):
            in_fence = not in_fence
            keep.append(line)
            i += 1
            continue
        if in_fence:
            keep.append(line)
            i += 1
            continue

        # HTML 注释不进版面：<!-- FOOTNOTES-RECOVERED --> 是 footnotes.py --patch
        # 留下的补回标记，留着会被转义成一行可见的乱码。
        if re.fullmatch(r"<!--.*?-->", stripped):
            i += 1
            continue

        m = re.match(r"^(#{2,6})[ \t]+(.*?)[ \t]*$", line)
        if m and is_note_heading(m.group(2)):
            level = len(m.group(1))
            i += 1
            block = []
            while i < n:
                nxt = lines[i]
                if re.match(r"^(#{1,%d})[ \t]" % level, nxt):
                    break            # 同级或更高级标题：本节到头
                if FENCE.match(nxt):
                    break            # 节内冒代码块，交回主循环，别吞掉代码
                block.append(nxt)
                i += 1
            _parse_note_block(block, defs)
            continue

        # Pandoc 式定义：[^1]: 正文，续行以 2+ 空格 / tab 缩进
        mm = re.match(r"^[ \t]{0,3}\[\^([\w-]{1,8})\]:[ \t]*(.*)$", line)
        if mm:
            key = mm.group(1)
            parts = [mm.group(2)]
            i += 1
            while i < n:
                nxt = lines[i]
                if not nxt.strip():
                    break
                if re.match(r"^[ \t]{0,3}\[\^[\w-]{1,8}\]:", nxt):
                    break
                if not re.match(r"^(?:[ \t]{2,}|\t)\S", nxt):
                    break
                parts.append(nxt)
                i += 1
            txt = _join_lines(parts)
            if txt:
                defs[key] = (defs[key] + " " + txt).strip() if key in defs else txt
            continue

        keep.append(line)
        i += 1

    return defs, "\n".join(keep)


def normalize_marks(body: str, defs) -> str:
    """正文脚注标记统一成 `<sup>n</sup>`，后续环节只认这一种内部形态。"""
    known = {str(k) for k in defs}
    out, in_fence = [], False
    for line in body.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        line = FN_REF.sub(lambda m: f"<sup>{m.group(1)}</sup>", line)
        # Unicode 上标只在确有同号脚注时转换，否则 x² 会被当成脚注 2
        for ch, num in UNICODE_SUP.items():
            if str(num) in known and ch in line:
                line = line.replace(ch, f"<sup>{num}</sup>")
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- 节处理
def split_sections(blocks):
    """删掉参考文献整节。脚注节已在 harvest_footnotes 里剥离。

    这里保留 notes 分支只是兜底：万一某节标题不在 NOTE_HEADINGS 里，
    或者层级深到 harvest 没认出来，也不该把"## 脚注"几个字印到版面上。
    """
    keep, mode = [], None
    for kind, payload in blocks:
        if kind in ("h2", "h3"):
            if is_ref_heading(payload):
                mode = "refs"
                continue
            if is_note_heading(payload):
                mode = "notes"
                continue
            mode = None
        if mode:
            continue
        keep.append((kind, payload))
    return keep


def attach_notes(blocks, notes):
    """脚注挂到"首次带 <sup>n</sup> 标记的那一段"之后。上标本身保留。"""
    used, out = set(), []
    for kind, payload in blocks:
        if kind == "p":
            out.append(("p", payload))
            for n in SUP_IN_TEXT.findall(payload):
                if n in notes and n not in used:
                    used.add(n)
                    out.append(("note", (n, notes[n])))
            continue
        out.append((kind, payload))
    for n, text in notes.items():          # 正文无标记的，落到末尾，不丢内容
        if n not in used:
            out.append(("note", (n, text)))
    return out


def prepare(body: str):
    """正文 → (脚注定义, 已挂好脚注的块序列)。build 与 to_markdown 共用。"""
    defs, body = harvest_footnotes(body)
    body = normalize_marks(body, defs)
    blocks = paragraphs_of(body)
    blocks = split_sections(blocks)
    blocks = attach_notes(blocks, defs)
    return defs, blocks


def _num_key(x):
    s = str(x)
    return (0, int(s), "") if s.isdigit() else (1, 0, s)


def audit_notes(defs, blocks, inner):
    """脚注不许静默消失。返回 (错误, 提醒)——错误会让脚本不写文件。"""
    errs, warns = [], []
    rendered = [str(p[0]) for k, p in blocks if k == "note"]
    marked = set()
    for k, p in blocks:
        if k == "p":
            marked.update(SUP_IN_TEXT.findall(p))

    if defs and not rendered:
        errs.append(f"抽出 {len(defs)} 条脚注，一条也没进版面——正文标记与脚注编号对不上")
    lost = [k for k in defs if str(k) not in set(rendered)]
    if lost:
        errs.append(f"脚注 {sorted(lost, key=_num_key)} 有定义却未进版面")
    if re.search(r"\[\^[\w-]{1,8}\]", inner):
        errs.append("输出里残留字面 [^n] 标记，读者会看到方括号编号")
    if "<sup>" in inner.lower() or "</sup>" in inner.lower():
        errs.append("输出里残留裸 <sup> 标签，未转成带样式的 span")

    orphan = [k for k in defs if str(k) not in marked]
    if orphan:
        warns.append(f"脚注 {sorted(orphan, key=_num_key)} 在正文里找不到对应标记，"
                     "已放到文末，请对照原文确认是不是漏了上标")
    defined = {str(k) for k in defs}
    unbacked = sorted((m for m in marked if m.isdigit() and m not in defined),
                      key=_num_key)
    if unbacked:
        warns.append(f"正文上标 {unbacked} 没有对应的脚注定义——版面会留一个无注释的编号，"
                     "检查脚注正文是不是在提取时丢了")
    return errs, warns


# ---------------------------------------------------------------- 行内标记
def inline(text: str) -> str:
    """转义 + 行内标记。sup 先占位保住，转义之后再还原成真标签。"""
    text = text.replace("<sup>", "\x00S").replace("</sup>", "S\x00")
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", text)   # 中文不用斜体
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 微信保留 <sup> 标签但不带样式，颜色与字号要自己给
    text = re.sub(r"\x00S[ \t]*([\w-]+)[ \t]*S\x00",
                  rf'<span style="font-size:11px;line-height:0;vertical-align:super;'
                  rf'color:{ACCENT};padding-left:1px;">\1</span>',
                  text)
    return text


# ---------------------------------------------------------------- 组件
def sec(text, style=""):
    return f'<section style="{style}">{text}</section>'


def heading(text, level=2):
    if level == 2:
        return sec(
            f'<strong style="font-size:17px;color:{HEAD};font-weight:600;">{inline(text)}</strong>',
            f"margin:34px 0 14px;padding-left:10px;border-left:4px solid {ACCENT};"
            "line-height:1.5;")
    return sec(
        f'<strong style="font-size:15.5px;color:#2e2e2e;font-weight:600;">{inline(text)}</strong>',
        "margin:26px 0 12px;line-height:1.5;")


def para(text):
    if text.startswith("*摘要*"):
        body = re.sub(r"^\*摘要\*[\s\u3000]*", "", text)
        return sec(
            f'<strong style="color:{ACCENT};">摘要</strong>　{inline(body)}',
            f"margin:0 0 24px;padding:14px 16px;background:{PANEL};font-size:14.5px;"
            "line-height:1.85;color:#4f4a44;text-align:justify;")
    if text.startswith("——"):
        return sec(inline(text),
                   f"margin:0 0 24px;text-align:right;color:{MUTE};font-size:14px;"
                   "line-height:1.7;")
    return sec(inline(text),
               f"margin:0 0 17px;font-size:15px;line-height:1.85;color:{INK};"
               "text-align:justify;")


def note(n, text):
    return sec(
        f'<strong style="color:{ACCENT};font-weight:600;">注 {n}</strong>　{inline(text)}',
        f"margin:0 0 20px;padding:11px 14px;background:{NOTE_BG};"
        f"border-left:3px solid {NOTE_BD};font-size:13.5px;line-height:1.8;"
        "color:#6a655e;text-align:justify;")


def render_table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    if not cells:
        return ""
    head, body = cells[0], cells[1:]
    td = (f"border:1px solid {RULE};padding:8px 9px;vertical-align:top;"
          "font-size:13px;line-height:1.7;word-break:break-word;text-align:left;")
    th = (f"border:1px solid {RULE};padding:8px 9px;background:{PANEL};"
          "font-size:13px;line-height:1.7;font-weight:600;color:#3a3a3a;"
          "text-align:left;word-break:break-word;")
    # 微信不认百分比宽度，窄屏会把四列压成一列；正文区宽 637px，按实际像素切
    h = ['<section style="margin:0 0 22px;">'
         '<table style="width:637px;border-collapse:collapse;">',
         "<tr>"]
    for i, c in enumerate(head):
        w = "width:88px;" if i == 0 else "width:183px;"
        h.append(f'<td style="{th}{w}">{inline(c)}</td>')
    h.append("</tr>")
    for r in body:
        h.append("<tr>")
        for c in r:
            h.append(f'<td style="{td}">{inline(c)}</td>')
        h.append("</tr>")
    h.append("</table></section>")
    return "".join(h)


# ---------------------------------------------------------------- APA
def apa(meta):
    """APA 7 期刊论文条目。题名只给原文，中译不进引用。"""
    authors = meta.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    author = (authors[0] if authors else "").strip()
    year = meta.get("year")
    title = (meta.get("title") or "").strip()
    journal = (meta.get("journal") or "").strip()
    volume = (meta.get("volume") or "").strip()
    issue = (meta.get("issue") or "").strip()
    pages = (meta.get("pages") or "").strip()
    s = f"{author} ({year}). {title}. <em>{journal}</em>"
    if volume:
        s += f", {volume}"
    if issue:
        s += f"({issue})"
    if pages:
        s += f", {pages}"
    return s + "."


def apa_plain(meta):
    return re.sub(r"<[^>]+>", "", apa(meta))


# ---------------------------------------------------------------- 组装
def render_figures(figs):
    """一行一张或并排几张。并排图（原刊的多联图）靠 inline-block 横排，
    不能指望 flex——公众号编辑器会把 display:flex 剥掉。"""
    n = len(figs)
    # 公众号编辑器会剥掉百分比宽度（self_check 也会拦），只能给 px。
    # 正文栏约 637px，并排时留出 6px 间隙。
    width = 620 if n == 1 else max(120, int((620 - 6 * (n - 1)) / n))
    cells = []
    for alt, src in figs:
        style = (f"display:inline-block;vertical-align:top;width:{width}px;"
                 f"height:auto;margin:0 {'3px' if n > 1 else 'auto'};")
        cells.append(f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" '
                     f'style="{style}">')
    return sec("".join(cells), "margin:18px 0 8px;text-align:center;line-height:0;")


def build(meta, blocks, translator, editor):
    if translator and editor and translator == editor:
        by = f"翻译&amp;编辑：{html.escape(translator)}"
    else:
        by = f"翻译：{html.escape(translator)}　编辑：{html.escape(editor)}"

    # 开头两行：署名、来源。浅灰小字，下压一条细线，不抢正文
    header = sec(
        sec(by, f"line-height:1.95;color:{MUTE};")
        + sec("文献来源：" + apa(meta), f"line-height:1.95;color:{MUTE};"),
        f"margin:0 0 26px;padding:0 0 16px;border-bottom:1px solid {RULE};"
        "font-size:13px;")

    parts = []
    for kind, payload in blocks:
        if kind == "h2":
            parts.append(heading(payload, 2))
        elif kind == "h3":
            parts.append(heading(payload, 3))
        elif kind == "caption":
            parts.append(sec(
                f'<strong style="font-size:14.5px;color:{HEAD};">{inline(payload)}</strong>',
                "margin:22px 0 10px;line-height:1.6;"))
        elif kind == "p":
            parts.append(para(payload))
        elif kind == "note":
            parts.append(note(*payload))
        elif kind == "list":
            parts.append(sec("".join(
                f'<section style="margin:0 0 6px;line-height:1.8;color:{INK};">'
                f'· {inline(x)}</section>' for x in payload), "margin:0 0 18px;"))
        elif kind == "figures":
            parts.append(render_figures(payload))
        elif kind == "table":
            parts.append(render_table(payload))

    root_style = (f"font-size:15px;line-height:1.85;letter-spacing:0.4px;color:{INK};"
                  f"font-family:{FONT};text-align:justify;")
    return sec(header + "\n".join(parts), root_style)


BAR = """<div style="max-width:677px;margin:0 auto;padding:16px 20px 0;
     font:14px/1.6 system-ui,sans-serif;color:#666;">
  <button id="copy" style="border:1px solid #a0321e;background:#a0321e;color:#fff;
          border-radius:4px;padding:8px 16px;font-size:14px;cursor:pointer;">复制全文</button>
  <span id="tip" style="margin-left:10px;color:#999;">复制后到公众号编辑器 Ctrl/⌘+V</span>
</div>
<script>
// 只复制根 section：按钮与页面底色都不进剪贴板
document.getElementById('copy').onclick = async () => {
  const root = document.getElementById('wx-root');
  try {
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([root.outerHTML], {type: 'text/html'}),
      'text/plain': new Blob([root.innerText], {type: 'text/plain'})
    })]);
    document.getElementById('tip').textContent = '已复制，去编辑器粘贴';
  } catch (e) {
    const r = document.createRange(); r.selectNodeContents(root);
    const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    document.execCommand('copy'); s.removeAllRanges();
    document.getElementById('tip').textContent = '已复制（兼容模式）';
  }
};
</script>"""


def page(inner, title):
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}｜公众号版</title></head>
<body style="margin:0;background:#eceae5;">
{BAR}
<div style="max-width:677px;margin:0 auto;background:#fff;padding:8px 20px 48px;">
<section id="wx-root">{inner}</section>
</div>
</body></html>
"""


def to_markdown(meta, blocks, translator, editor):
    if translator and editor and translator == editor:
        out = [f"翻译&编辑：{translator}", ""]
    else:
        out = [f"翻译：{translator}　编辑：{editor}", ""]
    out += [f"文献来源：{apa_plain(meta)}", "", "---", ""]
    for kind, payload in blocks:
        if kind == "h2":
            out += [f"## {payload}", ""]
        elif kind == "h3":
            out += [f"### {payload}", ""]
        elif kind == "caption":
            out += [f"**{payload}**", ""]
        elif kind == "p":
            out += [payload, ""]
        elif kind == "note":
            n, t = payload
            out += [f"> **注 {n}**　{t}", ""]
        elif kind == "list":
            out += [f"- {x}" for x in payload] + [""]
        elif kind == "figures":
            out += [" ".join(f"![{a}]({p})" for a, p in payload), ""]
        elif kind == "table":
            out += payload + [""]
    return "\n".join(out)


def self_check(inner):
    """粘贴前自检：任何一条不过，微信那边就会掉样式。"""
    bad = []
    if "<style" in inner:
        bad.append("输出里有 <style> 标签，微信会整块丢掉")
    if "class=" in inner:
        bad.append("输出里有 class 属性，微信不认选择器")
    for prop in ("position:", "display:flex", "display:grid", "box-shadow", "overflow:",
                 "table-layout:", "transform:"):
        if prop in inner:
            bad.append(f"用了微信不支持的属性 {prop}")
    # 百分比宽度在窄屏会被压变形，微信里可用宽度按 637px 计，一律写 px
    for m in re.finditer(r"width:\s*[\d.]+%", inner):
        bad.append(f"用了百分比宽度 {m.group(0)}，改成 px")
    if "var(--" in inner:
        bad.append("用了 CSS 变量，微信不解析")
    return bad


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, outdir = argv[1], argv[2]
    text = open(src, encoding="utf-8").read()
    meta, body = split_front(text)
    translator = str(meta.get("translator") or "").strip()
    editor = str(meta.get("editor") or "").strip() or translator
    os.makedirs(outdir, exist_ok=True)

    defs, blocks = prepare(body)
    inner = build(meta, blocks, translator, editor)

    problems = self_check(inner)
    errs, warns = audit_notes(defs, blocks, inner)
    if problems or errs:
        print("自检未通过：")
        for p in problems + errs:
            print("  ✗", p)
        print("未写出任何文件。")
        return 1
    for w in warns:
        print("  !", w)
    print(f"自检通过：全内联、无 class、无 style 标签、无微信禁用属性；"
          f"脚注 {len(defs)} 条全部落位")

    title = (meta.get("title_zh") or meta.get("title") or "公众号版").strip()
    p1 = os.path.join(outdir, "wechat_article.html")
    open(p1, "w", encoding="utf-8").write(page(inner, title))
    p2 = os.path.join(outdir, "wechat_article.md")
    open(p2, "w", encoding="utf-8").write(to_markdown(meta, blocks, translator, editor))
    print("写出：", p1)
    print("写出：", p2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
