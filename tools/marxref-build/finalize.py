"""给各卷句表补印刷页码，并生成卷元数据 volumes.json。

页码按句子在段内的字符位置插值——只用段的起始页，在跨 4 页的长段落里会差出很远
（实测第 5 卷长段落差 4 页）。

页码来源：各卷 PDF 的页脚独立数字行。page_map.py 先把「段落 → PDF 物理页 →
印刷页」三级映射建好，这里只做查表与插值。
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

TITLES = {
    1: ("1843—1848 年著作", [3, 4, 5, 6, 7, 9, 27]),
    2: ("1848—1859 年著作", [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]),
    3: ("1864—1883 年著作", [18, 19, 20, 21, 22, 23, 24]),
    4: ("1884—1895 年著作", [25, 26, 27]),
    5: ("《资本论》第一卷", [35]),
    6: ("《资本论》第二卷 资本的流通过程", [36]),
    7: ("《资本论》第三卷 资本主义生产的总过程", [37]),
    10: ("书信选编", list(range(38, 51))),
}


def load_pages(vol):
    fp = os.path.join(ROOT, f"corpus/mea{vol}_pages.jsonl")
    ip = os.path.join(ROOT, f"corpus/pages_index{vol}.json")
    if not os.path.exists(fp):
        return None, None
    m = {}
    for l in open(fp, encoding="utf-8"):
        r = json.loads(l)
        m[(r["doc"], r["i"])] = r
    idx = json.load(open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
    return m, idx


def page_of(m, idx, doc, i, s):
    r = m.get((doc, i))
    if not r:
        return None
    if not r.get("b_start"):
        # 没锚上的段落（多为页首被 OCR 破坏）用映射表里的兜底页码；
        # 兜底页也没有页码时，向前找最近一页有印刷页码的，别返回 None
        p = r.get("print_page")
        if p:
            return p
        for back in range(1, 6):
            key = str(r.get("pdf_page") - back)
            if idx.get(key):
                return idx[key]
        return None
    span = max(1, r["pdf_page_end"] - r["pdf_page"])
    ratio = min(1.0, (s or 0) / max(1, span * 6))
    start = r["pdf_page"] + round(ratio * span)
    # 插值落点如果是没有印刷页码的页（图版、空白页），向前找最近一个有号页，
    # 否则接口会给出 page=None，前端只能显示"页码待核"
    for k in range(start, max(start - 4, 0), -1):
        if idx.get(str(k)):
            return idx[str(k)]
    return r.get("print_page")


def main():
    meta = {}
    for vol in sorted(TITLES):
        fp = os.path.join(ROOT, f"corpus/vol{vol}_sent.jsonl")
        if not os.path.exists(fp):
            continue
        rows = [json.loads(l) for l in open(fp, encoding="utf-8")]
        m, idx = load_pages(vol)
        n_page = 0
        if m:
            for r in rows:
                if r.get("zh_i") is not None:
                    p = page_of(m, idx, r.get("zh_doc"), r["zh_i"], r.get("zh_s"))
                    r["page"] = p
                    n_page += bool(p)
        with open(fp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        t, mecw = TITLES[vol]
        paired = sum(1 for r in rows if not r.get("unaligned"))
        meta[str(vol)] = {
            "title": t,
            "source": f"《马克思恩格斯文集》第 {vol} 卷（人民出版社，2009）",
            "mecw": mecw,
            "sentences": len(rows),
            "paired": paired,
            "with_page": n_page,
            "pdf": f"pdf/mea{vol}.pdf" if os.path.exists(os.path.join(ROOT, f"pdf/mea{vol}.pdf")) else None,
        }
        print(f"卷{vol:<3} {len(rows):6d} 句  配对 {paired:6d} ({paired/len(rows):.0%})  "
              f"有页码 {n_page:6d} ({n_page/len(rows):.0%})")

    with open(os.path.join(ROOT, "corpus/volumes.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    tot = sum(v["sentences"] for v in meta.values())
    print(f"合计 {len(meta)} 卷 {tot} 句 → corpus/volumes.json")


if __name__ == "__main__":
    main()
