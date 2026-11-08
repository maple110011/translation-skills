"""选编卷构建：文集第 1、2、3、4、8、10 卷。

和资本论三卷（build_vol.py）的区别在于，这些卷是**选编**：
* 一卷要对应多个 MECW 卷；
* 篇目之间没有章号可配对，只能靠 works.csv 的显式映射；
* 不少篇是「节选」，中文只对应英文原作的某一段落区间，
  直接从头做 DP 会整体错位，所以先按数字锚找偏移，再对齐。

输出与 build_vol.py 完全一致的 corpus/vol{N}_sent.jsonl，引擎无需改动。
"""
import os, re, sys, json, glob, html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import align as para_align, load_glossary, load
from align_sent import align_sent_pairs, sents_en, sents_zh, expand_span

ROOT = os.path.dirname(os.path.abspath(__file__))

MECW_VOLS = {
    1: [3, 4, 5, 6, 7, 9, 27],
    2: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    3: [18, 19, 20, 21, 22, 23, 24],
    4: [25, 26, 27],
    8: [28, 29, 30, 31, 32, 33, 34],
    10: list(range(38, 51)),
}
LABEL = {
    1: "1843—1848 年著作", 2: "1848—1859 年著作", 3: "1864—1883 年著作",
    4: "1884—1895 年著作", 8: "《资本论》手稿选编", 10: "书信选编",
}

NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")


def nums(t):
    return {re.sub(r"[, ]", "", x).strip(".") for x in NUM.findall(t or "") if x.strip(".")}


def zh_title(vol, doc):
    p = os.path.join(ROOT, f"raw/mea{vol}/{doc}.html")
    if not os.path.exists(p):
        return doc
    s = open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))) if m else doc
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^\s*\*?\s*(?:卡·马克思和弗·恩格斯|弗·恩格斯和卡·马克思|卡·马克思、弗·恩格斯|"
               r"卡·马克思|弗·恩格斯|卡·马克思和弗-恩格斯)[　\s和与]*", "", t)   # 去掉作者前缀
    t = re.sub(r"\s+\d+$", "", t)          # 尾巴上的 OCR 页码
    return t.strip("* ").strip() or doc


def locate_offset(E, Z):
    """节选篇：中文只对应英文的一段。用段落里的数字找最可能的起始段落。

    数字是唯一跨语言可靠的锚。没有数字的篇目只能返回 0（从头对齐），
    这类篇目的对齐质量会在报告里体现出来。
    """
    zc = "".join(Z)
    zn = set()
    for t in Z:
        zn |= nums(t)
    if len(zn) < 5:                      # 数字太少，锚不住
        return 0, "无锚"
    n = len(E)
    win = max(20, int(len(Z) * 1.6))     # 英文段数通常比中文多
    if win >= n:
        return 0, "整篇"
    best, best_s = -1.0, 0
    step = max(1, win // 12)
    for s in range(0, n - win + 1, step):
        en = set()
        for t in E[s:s + win]:
            en |= nums(t)
        if not en:
            continue
        sc = len(zn & en) / len(zn)
        if sc > best:
            best, best_s = sc, s
    # 命中率不高就不要硬切片，避免把本来完整的篇目切坏
    if best < 0.5:
        return 0, f"锚定弱({best:.2f})"
    return best_s, f"偏移{best_s}({best:.2f})"


def build(vol, resolved):
    en_all = {}
    for mv in MECW_VOLS[vol]:
        fp = os.path.join(ROOT, f"corpus/mecw{mv}.jsonl")
        if os.path.exists(fp):
            for k, v in load(fp).items():
                en_all[k] = v
    zh = load(os.path.join(ROOT, f"corpus/mea{vol}.jsonl"))
    entries = load_glossary(ROOT)

    rows, n_en_s, n_pairs, skipped = [], 0, 0, []
    for key, item in resolved.items():
        if item["vol"] != vol:
            continue
        zdoc = item["zh"]
        if zdoc not in zh:
            skipped.append((zdoc, "无中文"))
            continue
        E, EID = [], []
        for fn in item["en"]:
            d = os.path.splitext(os.path.basename(fn))[0]
            if d not in en_all:
                continue
            for k, t in enumerate(en_all[d]):
                E.append(t); EID.append((d, k))
        if not E:
            skipped.append((zdoc, "无英文"))
            continue

        rng = item.get("range")
        if rng:
            E, EID = E[rng[0]:rng[1] + 1], EID[rng[0]:rng[1] + 1]

        Z = zh[zdoc]
        zf = item.get("zh_from") or 0
        if zf:
            Z = Z[zf:]          # 跳过中文前置序言（如《宣言》的 1872/1882 年序言）
        off, how = (0, "指定区间") if rng else locate_offset(E, Z)
        if off:
            E, EID = E[off:], EID[off:]

        title = zh_title(vol, zdoc)
        path, _ = para_align(E, Z, entries, max_merge=2)
        span = {}
        for a, b, c, d in path:
            for i in range(a, b):
                span[i] = (c, max(d, c))
        for i in range(len(E)):
            cs, ce = expand_span(i, *span.get(i, (0, 0)), E, Z)
            es = sents_en(E[i])
            n_en_s += len(es)
            zs, zmap = [], []
            for j in range(cs, ce):
                for k, s in enumerate(sents_zh(Z[j])):
                    zs.append(s); zmap.append((j, k))
            for k, jj in align_sent_pairs(es, zs):
                if jj is None:
                    rows.append({"vol": vol, "chapter": title, "en": es[k], "zh": "",
                                 "zh_doc": zdoc, "zh_i": None, "zh_s": None,
                                 "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                                 "unaligned": True})
                    continue
                pj, pk = zmap[jj]
                rows.append({"vol": vol, "chapter": title, "en": es[k],
                             "zh": sents_zh(Z[pj])[pk], "zh_doc": zdoc, "zh_i": pj + zf,
                             "zh_s": pk, "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                             "unaligned": False})
        n_pairs += 1
        if how.startswith("偏移"):
            print(f"   {zdoc} {title[:26]} … {how}  段 {len(E)}→{len(Z)}")

    got = sum(1 for r in rows if not r["unaligned"])
    print(f"卷 {vol}（{LABEL[vol]}）: 篇目 {n_pairs}  英文句 {n_en_s}  "
          f"配对 {got}  {got/max(n_en_s,1):.1%}"
          + (f"  跳过 {len(skipped)}" if skipped else ""))
    out = os.path.join(ROOT, f"corpus/vol{vol}_sent.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


if __name__ == "__main__":
    rp = os.path.join(ROOT, "index/works_resolved.json")
    resolved = json.load(open(rp, encoding="utf-8"))
    which = [int(x) for x in sys.argv[1:]] or sorted(MECW_VOLS)
    for v in which:
        build(v, resolved)
