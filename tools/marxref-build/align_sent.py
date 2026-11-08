"""句级对齐：段级定范围，句级定位置。

段级对齐只能给出"这一片大致对应哪一片"——因为英文一个 <p> 常常等于中文六段，
点对点映射在体例差异处必然失真。真正稳定的锚是句子：译文逐句对应，中英句数比
在实测中稳定在 1.05 左右（Ch.8: 143 vs 150）。

所以分两步：
  1. 段级 DP（1:1..1:2）给出英文段 → 中文段区间，再按长度比把区间补足；
  2. 在每个区间内做句级单调 DP，输出英文句 → 中文句。

输出 align_sent.jsonl，一行一对句。
"""
import json, re, math, collections, os, csv
from align import (C0, MAX_MERGE, CHAPTER_MAP, ZH_TITLE, load, feats, merge_feats,
                   seg_cost, load_glossary, build_hits, nums, EN_S, ZH_S, align as para_align)

C0S = 0.235          # 中文汉字 / 英文字符，句级标定


def sents_en(t):
    return [x.strip() for x in EN_S.split(t) if x.strip()]


def sents_zh(t):
    return [x.strip() for x in re.split(r'(?<=[。！？；])', t) if x.strip()]


def sent_cost(e, z, ne, nz):
    el, zl = e, z
    c = abs(math.log((zl + 1.0) / (el * C0S + 1.0)))
    if ne and nz:
        c += 1.2 * (1.0 - len(ne & nz) / len(ne | nz))
    return c


def align_sent_pairs(es, zs):
    """两串句子做单调 DP，允许 1:1 / 1:0 / 0:1。返回 [(i, j or None)]"""
    n, m = len(es), len(zs)
    EF = [len(x) for x in es]
    ZF = [len(x) for x in zs]
    EN = [nums(x) for x in es]
    ZN = [nums(x) for x in zs]
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur == INF:
                continue
            if i < n and j < m:
                c = cur + sent_cost(EF[i], ZF[j], EN[i], ZN[j])
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c; bk[i + 1][j + 1] = (1, 1)
            if i < n:
                c = cur + 0.9
                if c < dp[i + 1][j]:
                    dp[i + 1][j] = c; bk[i + 1][j] = (1, 0)
            if j < m:
                c = cur + 0.9
                if c < dp[i][j + 1]:
                    dp[i][j + 1] = c; bk[i][j + 1] = (0, 1)
    i, j, path = n, m, []
    while i or j:
        a, b = bk[i][j]
        path.append((i - a, i, j - b, j))
        i, j = i - a, j - b
    path.reverse()
    out = []
    for a, b, c, d in path:
        for k in range(a, b):
            out.append((k, c if c < d else None))
    return out


def expand_span(i, cs, ce, E, Z):
    """段级 DP 只给出区间起点，按长度比把区间补足到与英文段等量。"""
    target = len(E[i]) * C0
    acc = sum(len(Z[j]) for j in range(cs, ce)) if ce > cs else 0
    while acc < target * 0.88 and ce < len(Z):
        acc += len(Z[ce]); ce += 1
    if ce == cs and ce < len(Z):
        ce = cs + 1
    return cs, ce


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    en = load(os.path.join(root, "corpus/mecw35.jsonl"))
    zh = load(os.path.join(root, "corpus/mea5.jsonl"))
    entries = load_glossary(root)
    out = []
    tallies = []
    for en_docs, zh_doc in CHAPTER_MAP:
        E, EID = [], []
        for d in en_docs:
            for k, t in enumerate(en[d]):
                E.append(t); EID.append((d, k))
        Z = zh[zh_doc]
        path, _tot = para_align(E, Z, entries, max_merge=2)
        # 英文段 → 中文区间
        span = {}
        for a, b, c, d in path:
            for i in range(a, b):
                span[i] = (c, max(d, c))
        pairs = 0
        for i in range(len(E)):
            cs, ce = span.get(i, (0, 0))
            cs, ce = expand_span(i, cs, ce, E, Z)
            es = sents_en(E[i])
            zs = [s for j in range(cs, ce) for s in sents_zh(Z[j])]
            zmap = [(j, k) for j in range(cs, ce) for k, s in enumerate(sents_zh(Z[j]))]
            for k, jj in align_sent_pairs(es, zs):
                if jj is None:
                    # 保留未配对的英文句：宁可说"这句没对上"，也不要让它凭空消失、
                    # 被检索层退而求其次指到一段无关的中文上去。
                    out.append({"en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                                "en": es[k], "zh_doc": zh_doc, "zh_i": None,
                                "zh_s": None, "zh": None,
                                "chapter": ZH_TITLE[zh_doc], "unaligned": True})
                    continue
                pj, pk = zmap[jj]
                out.append({"en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                            "en": es[k], "zh_doc": zh_doc, "zh_i": pj, "zh_s": pk,
                            "zh": sents_zh(Z[pj])[pk], "chapter": ZH_TITLE[zh_doc]})
                pairs += 1
        n_en_s = sum(len(sents_en(t)) for t in E)
        tallies.append((ZH_TITLE[zh_doc], n_en_s, pairs))
        print(f"{ZH_TITLE[zh_doc]:28s} EN句{n_en_s:5d}  配到{pairs:5d}  {pairs/max(n_en_s,1):.0%}")
    with open(os.path.join(root, "corpus/align_sent.jsonl"), "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tot_en = sum(t[1] for t in tallies)
    tot_p = sum(t[2] for t in tallies)
    print(f"\n英文句 {tot_en}  句对 {tot_p}  覆盖率 {tot_p/tot_en:.1%}")


if __name__ == "__main__":
    main()
