"""把 MECW35 / 文集第5卷 的 HTML 解析成块级 JSONL。

只取 h1 / h3 / p，天然跳过 MECW 的导航块（那块只有 ul/li/a）和中文的 aside 注释。
"""
import re, json, html, glob, os, sys

WS = re.compile(r"[ \t\r\n\u00a0]+")
BLOCK = re.compile(r"<(h1|h3|p)\b[^>]*>(.*?)</\1>", re.S | re.I)


def clean(s: str, lang: str = "zh") -> str:
    # 脚注锚（<sup><a ...>N</a></sup>）整体删除，两侧都有
    s = re.sub(r"<sup\b[^>]*>\s*<a\b.*?</a>\s*</sup>", "", s, flags=re.S | re.I)
    if lang == "zh":
        # 中文分数写作 <sup>4</sup>/<sub>5</sub>，必须还原成 4/5，否则分子丢失
        s = re.sub(r"<sup\b[^>]*>(.*?)</sup>\s*[/／]\s*<sub\b[^>]*>(.*?)</sub>",
                   r"\1/\2", s, flags=re.S | re.I)
        s = re.sub(r"</?(sup|sub)\b[^>]*>", "", s, flags=re.I)
    else:
        # 英文侧裸 <sup>N</sup> 是脚注序号，删掉，避免污染数字锚
        s = re.sub(r"<sup\b[^>]*>.*?</sup>", "", s, flags=re.S | re.I)
        s = re.sub(r"</?sub\b[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)                                        # 其余标签留内容
    s = html.unescape(s)
    s = s.replace("\u3000", " ").replace("\u00ad", "")
    s = WS.sub(" ", s)
    # 千分位归一化：中文 "10 000"、英文 "10,000" 统一成 10000，否则数字锚全部对不上
    while True:
        t = re.sub(r"(?<=\d)[ ,\u2009](?=\d{3}(?!\d))", "", s)
        if t == s:
            break
        s = t
    return s.strip()


def parse(path, lang, doc_id):
    raw = open(path, encoding="utf-8", errors="replace").read()
    raw = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<head\b.*?</head>", " ", raw, flags=re.S | re.I)
    out, idx = [], 0
    for tag, body in BLOCK.findall(raw):
        t = clean(body, lang)
        if not t:
            continue
        kind = "heading" if tag.lower() in ("h1", "h3") else "para"
        out.append({"doc": doc_id, "lang": lang, "i": idx,
                    "kind": kind, "text": t, "chars": len(t)})
        idx += 1
    return out


def run(src_dir, lang, prefix, dst):
    rows = []
    for p in sorted(glob.glob(os.path.join(src_dir, "*.html"))):
        doc = os.path.splitext(os.path.basename(p))[0]
        blocks = parse(p, lang, doc)
        if not blocks:
            continue
        rows.extend(blocks)
        npar = sum(1 for b in blocks if b["kind"] == "para")
        nch = sum(b["chars"] for b in blocks if b["kind"] == "para")
        print(f"{doc:14s} blocks={len(blocks):4d} paras={npar:4d} chars={nch:7d}")
    with open(dst, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"-> {dst}  {len(rows)} blocks")


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    print("=== MECW35 ===")
    run(os.path.join(root, "raw/mecw35"), "en", "", os.path.join(root, "corpus/mecw35.jsonl"))
    print("=== MEA5 ===")
    run(os.path.join(root, "raw/mea5"), "zh", "", os.path.join(root, "corpus/mea5.jsonl"))
