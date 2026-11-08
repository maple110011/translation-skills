"""给《文集》第 5 卷的每个段落标上 PDF 页码与书内印刷页码。

做法：
  1. pdftotext -layout 的输出按 \\f 分页，每页末尾独立数字行即印刷页码；
  2. 把各页正文去掉所有标点空白后拼成一条长串，并记录每页在串中的区间；
  3. 每个 HTML 段落取规范化后的前 14 个字，在这条长串里单调向后查找，
     落点所在的页就是该段的起始页。

单调查找很关键：同一句话在书里可能重复出现，单调推进能保证段落顺序不乱。
"""
import re, json, os, collections

HEAD = 22          # 兜底偏移（实测主偏移）
LIMIT = int(os.environ.get("PAGE_LIMIT", "2600"))   # 单次向后查找的最大跨度（字）
WIN = 14           # 锚定用的前缀长度


def norm(s):
    return re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", s)


def locate(text, big, cursor, limit=None):
    """段首常是 OCR 重灾区（缩进、多余空格、错字），所以不只用段首：
    先在开头 40 字内滑 14/12/10 字的窗口，取第一个能命中且位置合理的结果。

    limit 必须收得很紧：段落之间通常只前进几百字（一页约 680 字）。
    放太宽的话，索引卷里重复出现的正文句子会把游标一下带到书末，
    之后整篇的页码全错——这个坑实测踩过。"""
    limit = LIMIT if limit is None else limit
    s = norm(text)
    if not s:
        return -1
    # 短段落（"献给""亲爱的公民："之类）也要能锚定，只是窗口相应缩短
    lens = [w for w in (14, 12, 10, 6, 3) if w <= len(s)] or [len(s)]
    for wlen in lens:
        hi = min(40, max(1, len(s) - wlen + 1))
        for st in range(hi):
            frag = s[st:st + wlen]
            hit = big.find(frag, cursor)
            if hit < 0:
                hit = big.find(frag, max(0, cursor - 3000))
            if hit >= 0 and hit - cursor <= limit:
                return hit
    return -1


def page_number(lines):
    for l in reversed(lines[-2:]):
        if re.fullmatch(r"\d{1,4}", l):
            return int(l)
    for l in lines[:2]:
        if re.fullmatch(r"\d{1,4}", l):
            return int(l)
    return None


def main(vol=5):
    root = os.path.dirname(os.path.abspath(__file__))
    raw = open(os.path.join(root, f"pdf/mea{vol}.txt"), encoding="utf-8", errors="replace").read()
    pages = raw.split("\f")

    pn, spans, buf = [], [], []
    pos = 0
    for pg in pages:
        lines = [l.strip() for l in pg.split("\n") if l.strip()]
        pn.append(page_number(lines))
        t = norm(pg)
        spans.append((pos, pos + len(t)))
        buf.append(t)
        pos += len(t)
    big = "".join(buf)
    print(f"页数 {len(pages)}  规范化正文 {len(big)} 字  有页码 {sum(1 for x in pn if x)} 页")

    rows = [json.loads(l) for l in open(os.path.join(root, f"corpus/mea{vol}.jsonl"), encoding="utf-8")]
    rows = [r for r in rows if r["kind"] == "para"]

    out, cursor, miss = [], 0, 0
    last_page = 1
    page_of_off = [None] * len(big)
    for k, (a, b) in enumerate(spans):
        for p in range(a, b):
            page_of_off[p] = k

    by_doc = collections.defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)

    for doc in sorted(by_doc):
        for k, r in enumerate(by_doc[doc]):
            hit = locate(r["text"], big, cursor)
            if hit >= 0:
                cursor = hit
                end = min(hit + len(norm(r["text"])), len(big) - 1)
                ps, pe = page_of_off[hit] + 1, page_of_off[end] + 1
                last_page = ps
                out.append({"doc": doc, "i": k, "pdf_page": ps, "print_page": pn[ps - 1],
                            "pdf_page_end": pe, "b_start": hit, "b_len": end - hit,
                            "anchored": True})
            else:
                miss += 1
                out.append({"doc": doc, "i": k, "pdf_page": last_page,
                            "print_page": pn[last_page - 1] if last_page - 1 < len(pn) else None,
                            "pdf_page_end": last_page, "b_start": None, "b_len": None,
                            "anchored": False})

    good = [r for r in out if r["anchored"] and r["print_page"]]
    print(f"段落 {len(out)}  锚定 {len(good)}  未锚定 {miss}  锚定率 {len(good)/len(out):.1%}")
    if good:
        diffs = collections.Counter(r["pdf_page"] - r["print_page"] for r in good)
        print("偏移分布:", diffs.most_common(4))

    with open(os.path.join(root, f"corpus/pages_index{vol}.json"), "w", encoding="utf-8") as f:
        json.dump({str(i + 1): pn[i] for i in range(len(pn))}, f)

    with open(os.path.join(root, f"corpus/mea{vol}_pages.jsonl"), "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys
    for v in (int(x) for x in sys.argv[1:]) or [5]:
        print(f"── 卷 {v}")
        main(v)
