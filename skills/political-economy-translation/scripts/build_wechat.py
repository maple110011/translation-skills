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


# ---------------------------------------------------------------- 节处理
def split_sections(blocks):
    """抽出文末脚注，删掉参考文献整节。返回 (notes, 剩余块)。"""
    notes, keep, mode = {}, [], None
    for kind, payload in blocks:
        if kind == "h2":
            name = payload.strip()
            if name in ("参考文献", "References", "Bibliography"):
                mode = "refs"
                continue
            if name in ("脚注", "注释", "Notes"):
                mode = "notes"
                continue
            mode = None
        if mode == "refs":
            continue
        if mode == "notes":
            if kind == "p":
                payload = re.sub(r"^(?:\d+\.\s*)?", "", payload)
            m = re.match(r"<sup>(\d+)</sup>[\s\u3000]*(.*)$", payload, re.S)
            if m:
                notes[m.group(1)] = m.group(2).strip()
            continue
        keep.append((kind, payload))
    return notes, keep


def attach_notes(blocks, notes):
    """脚注挂到"首次带 <sup>n</sup> 标记的那一段"之后。上标本身保留。"""
    used, out = set(), []
    for kind, payload in blocks:
        if kind == "p":
            out.append(("p", payload))
            for n in re.findall(r"<sup>(\d+)</sup>", payload):
                if n in notes and n not in used:
                    used.add(n)
                    out.append(("note", (n, notes[n])))
            continue
        out.append((kind, payload))
    for n, text in notes.items():          # 正文无标记的，落到末尾，不丢内容
        if n not in used:
            out.append(("note", (n, text)))
    return out


# ---------------------------------------------------------------- 行内标记
def inline(text: str) -> str:
    """转义 + 行内标记。sup 先占位保住，转义之后再还原成真标签。"""
    text = text.replace("<sup>", "\x00S").replace("</sup>", "S\x00")
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", text)   # 中文不用斜体
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 微信保留 <sup> 标签但不带样式，颜色与字号要自己给
    text = re.sub(r"\x00S(\d+)S\x00",
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
def build(meta, body, translator, editor):
    blocks = paragraphs_of(body)
    notes, blocks = split_sections(blocks)
    blocks = attach_notes(blocks, notes)

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


def to_markdown(meta, body, translator, editor):
    blocks = paragraphs_of(body)
    notes, blocks = split_sections(blocks)
    blocks = attach_notes(blocks, notes)
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

    inner = build(meta, body, translator, editor)
    problems = self_check(inner)
    if problems:
        print("自检未通过：")
        for p in problems:
            print("  ✗", p)
        return 1
    print("自检通过：全内联、无 class、无 style 标签、无微信禁用属性")

    title = (meta.get("title_zh") or meta.get("title") or "公众号版").strip()
    p1 = os.path.join(outdir, "wechat_article.html")
    open(p1, "w", encoding="utf-8").write(page(inner, title))
    p2 = os.path.join(outdir, "wechat_article.md")
    open(p2, "w", encoding="utf-8").write(to_markdown(meta, body, translator, editor))
    print("写出：", p1)
    print("写出：", p2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
