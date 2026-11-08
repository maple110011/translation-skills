"""多卷构建：把 MEA 每一卷与对应 MECW 卷对齐，产出统一的句级索引。

输出 corpus/vol{N}_sent.jsonl，字段：
    vol, chapter, en, zh, zh_doc, zh_i, zh_s, en_doc, en_i, en_s, unaligned

卷配置写在 VOLS 里。第 5 卷用人工校对过的映射（序跋是 1:6 合并），
第 6、7 卷用"按章号配对 + 顺序补配"自动生成。
"""
import os, re, json, glob, html, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import align as para_align, load_glossary, load
from align_sent import align_sent_pairs, sents_en, sents_zh, expand_span

ROOT = os.path.dirname(os.path.abspath(__file__))

# (卷号, MECW 卷号, 卷名)
VOLS = {
    5: (35, "《资本论》第一卷"),
    6: (36, "《资本论》第二卷 资本的流通过程"),
    7: (37, "《资本论》第三卷 资本主义生产的总过程"),
}

# 第 5 卷的映射是人工校对过的，含多处多对一
MANUAL = {
    5: [
        (["MECW35-004"], "MEA5-007"), (["MECW35-005"], "MEA5-008"), (["MECW35-006"], "MEA5-009"),
        (["MECW35-007", "MECW35-008", "MECW35-009"], "MEA5-010"),
        (["MECW35-010"], "MEA5-011"), (["MECW35-011"], "MEA5-012"), (["MECW35-012"], "MEA5-013"),
        (["MECW35-013"], "MEA5-014"), (["MECW35-014"], "MEA5-015"), (["MECW35-015"], "MEA5-016"),
        (["MECW35-016"], "MEA5-017"), (["MECW35-017"], "MEA5-018"), (["MECW35-018"], "MEA5-019"),
        (["MECW35-019"], "MEA5-020"), (["MECW35-020"], "MEA5-021"), (["MECW35-021"], "MEA5-022"),
        (["MECW35-022"], "MEA5-023"), (["MECW35-023"], "MEA5-024"), (["MECW35-024"], "MEA5-025"),
        (["MECW35-025"], "MEA5-026"), (["MECW35-026"], "MEA5-027"), (["MECW35-027"], "MEA5-028"),
        (["MECW35-028"], "MEA5-029"),
        (["MECW35-029", "MECW35-030", "MECW35-031", "MECW35-032",
          "MECW35-033", "MECW35-034", "MECW35-035"], "MEA5-030"),
        (["MECW35-036"], "MEA5-031"),
    ]
}

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    if not s:
        return None
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (CN.get(a, 1) if a else 1) * 10 + (CN.get(b, 0) if b else 0)
    v = 0
    for ch in s:
        if ch in CN:
            v = CN[ch]
    return v or None


def h1(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
    return re.sub(r"\s+", " ", t).strip()


def n_paras(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    return len(re.findall(r"<p[^>]*>", s, re.I))


def auto_map(mea_vol, mecw_vol):
    """按章号配对；剩下的"第X篇"标题页若含正文，按顺序承接未配对的英文章。"""
    A = {p: h1(p) for p in sorted(glob.glob(f"{ROOT}/raw/mea{mea_vol}/*.html"))}
    B = {p: h1(p) for p in sorted(glob.glob(f"{ROOT}/raw/mecw{mecw_vol}/*.html"))}
    amap, bmap = {}, {}
    for p, t in A.items():
        m = re.search(r"第([一二三四五六七八九十]+)章", t)
        if m:
            amap[cn2int(m.group(1))] = p
    for p, t in B.items():
        m = re.search(r"\bCh(?:apter)?\.?\s*(\d+)", t)
        if m:
            bmap[int(m.group(1))] = p
    pairs = []
    stem = lambda x: os.path.splitext(os.path.basename(x))[0]
    for n in sorted(set(amap) & set(bmap)):
        pairs.append(([stem(bmap[n])], stem(amap[n]), n))
    used_a = {p[1] for p in pairs} | {stem(v) for v in amap.values()}
    used_b = {d for d, _, _ in [(x[0][0], x[1], x[2]) for x in pairs]}
    SKIP = ("序言", "序", "跋", "说明", "索引", "附录", "目录", "注释", "凡例")
    def is_body(p):
        t = A[p]
        if re.search(r"第[一二三四五六七八九十]+章", t):
            return True                      # 明确是章，正文
        if any(w in t for w in SKIP):
            return False                     # 序言/跋/索引之类，即使含"第X版"
        return n_paras(p) > 3
    free_a = [stem(p) for p in sorted(A) if stem(p) not in used_a and is_body(p)]
    free_b = [(n, stem(p)) for n, p in sorted(bmap.items()) if stem(p) not in used_b]
    for (fa, (n, fb)) in zip(free_a, free_b):
        pairs.append(([fb], fa, n))
        print(f"   补配 Ch.{n}: {fb} → {fa}")
    if len(free_b) > len(free_a):
        print(f"   ⚠ 仍有 {len(free_b)-len(free_a)} 章无中文对应:", free_b[len(free_a):])
    pairs.sort(key=lambda x: x[2])
    return pairs


def build(vol):
    mecw_vol, label = VOLS[vol]
    if vol in MANUAL:
        pairs = [(a, b, None) for a, b in MANUAL[vol]]
    else:
        pairs = auto_map(vol, mecw_vol)
    en = load(os.path.join(ROOT, f"corpus/mecw{mecw_vol}.jsonl"))
    zh = load(os.path.join(ROOT, f"corpus/mea{vol}.jsonl"))
    entries = load_glossary(ROOT)
    rows, n_en_s = [], 0
    for en_docs, zh_doc, _n in pairs:
        if zh_doc not in zh:
            print("   跳过（无中文）", zh_doc); continue
        E, EID = [], []
        for d in en_docs:
            if d not in en:
                print("   跳过（无英文）", d); continue
            for k, t in enumerate(en[d]):
                E.append(t); EID.append((d, k))
        if not E:
            continue
        Z = zh[zh_doc]
        title = next((h1(p) for p in sorted(glob.glob(f"{ROOT}/raw/mea{vol}/{zh_doc}.html"))), zh_doc)
        # h1 里常带"第X篇/第X册"前缀，只保留"第X章"开始的部分
        m_ch = re.search(r"第[一二三四五六七八九十]+章.*$", title)
        if m_ch:
            title = m_ch.group(0)
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
                                 "zh_doc": zh_doc, "zh_i": None, "zh_s": None,
                                 "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                                 "unaligned": True})
                    continue
                pj, pk = zmap[jj]
                rows.append({"vol": vol, "chapter": title, "en": es[k],
                             "zh": sents_zh(Z[pj])[pk], "zh_doc": zh_doc, "zh_i": pj,
                             "zh_s": pk, "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                             "unaligned": False})
    got = sum(1 for r in rows if not r["unaligned"])
    print(f"卷 {vol}（{label}）: 英文句 {n_en_s}  配对 {got}  {got/max(n_en_s,1):.1%}")
    out = os.path.join(ROOT, f"corpus/vol{vol}_sent.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


if __name__ == "__main__":
    which = [int(x) for x in sys.argv[1:]] or sorted(VOLS)
    for v in which:
        build(v)
