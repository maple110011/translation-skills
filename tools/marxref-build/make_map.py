"""自动生成 MEA 卷 ↔ MECW 卷的篇目映射。

《资本论》二、三卷的中文篇目都带"第X章"，MECW 带 "Ch. N"，直接按章号配对，
比人工列表可靠。配对不上的（序言、篇标题页、索引）单独列出，人工处理。
"""
import re, os, json, html, glob, sys

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    """第二十一 → 21，十 → 10，五十二 → 52"""
    if not s:
        return None
    if s == "十":
        return 10
    total, section = 0, 0
    if "十" in s:
        a, _, b = s.partition("十")
        tens = CN.get(a, 1) if a else 1
        ones = CN.get(b, 0) if b else 0
        return tens * 10 + ones
    for ch in s:
        if ch in CN:
            section = CN[ch]
    return section or None


def h1(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
    return re.sub(r"\s+", " ", t).strip()


def mea_chapter(t):
    m = re.search(r"第([一二三四五六七八九十]+)章", t)
    return cn2int(m.group(1)) if m else None


def mecw_chapter(t):
    m = re.search(r"\bCh(?:apter)?\.?\s*(\d+)", t)
    return int(m.group(1)) if m else None


def build(mea_vol, mecw_vol):
    A = {p: h1(p) for p in sorted(glob.glob(f"raw/mea{mea_vol}/*.html"))}
    B = {p: h1(p) for p in sorted(glob.glob(f"raw/mecw{mecw_vol}/*.html"))}
    amap = {mea_chapter(t): p for p, t in A.items() if mea_chapter(t)}
    bmap = {mecw_chapter(t): p for p, t in B.items() if mecw_chapter(t)}
    pairs, miss_a, miss_b = [], [], []
    for n in sorted(set(amap) | set(bmap)):
        pa, pb = amap.get(n), bmap.get(n)
        if pa and pb:
            pairs.append((os.path.basename(pb), os.path.basename(pa), n))
        elif pa:
            miss_a.append((n, os.path.basename(pa), A[pa]))
        else:
            miss_b.append((n, os.path.basename(pb), B[pb]))
    print(f"── MEA{mea_vol} × MECW{mecw_vol}: 按章号配对 {len(pairs)} 章")
    if miss_a:
        print("   只有中文:", [(n, f, t[:30]) for n, f, t in miss_a])
    if miss_b:
        print("   只有英文:", [(n, f, t[:30]) for n, f, t in miss_b])
    print("   中文未配对篇目（序言/篇标题/索引）:")
    used = {p for p in pairs for p in p[:2]} | {f for _, f, _ in miss_a}
    for p, t in A.items():
        if os.path.basename(p) not in used:
            print(f"     {os.path.basename(p):16s} {t[:52]}")
    return pairs, A, B


if __name__ == "__main__":
    for mv, wv in [(6, 36), (7, 37)]:
        build(mv, wv)
        print()
