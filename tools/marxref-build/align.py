"""MECW35(英) 与 文集第5卷(中) 的段落级单调对齐。

思路：同一底本（德文第4版）→ 段落顺序严格单调；译文逐句对应 → 句数是强锚；
中文/英文字符比稳定 → 长度比是弱约束。用 DP 做全局单调对齐，
允许 1:1 / 1:0 / 0:1 / 2:1 / 1:2 五种转移，比逐段贪心稳，不会跳。

输出 align_mecw35_mea5.jsonl，每行 {en, en_i, zh, zh_i, kind}
"""
import json, re, math, collections, os

MAX_MERGE = 6
C0 = 0.24          # 中文汉字数 / 英文字符数（实测标定，见 README）
EN_S = re.compile(r'[.!?](?=[\s"\u201c\u2018]*[A-Z])')
ZH_S = re.compile(r'[。！？]')

# MECW 篇 → 中文篇。多对一表示英文侧多章合并成中文一章。
CHAPTER_MAP = [
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

ZH_TITLE = {
    "MEA5-007": "第一章 商品", "MEA5-008": "第二章 交换过程", "MEA5-009": "第三章 货币或商品流通",
    "MEA5-010": "第四章 货币转化为资本", "MEA5-011": "第五章 劳动过程和价值增殖过程",
    "MEA5-012": "第六章 不变资本和可变资本", "MEA5-013": "第七章 剩余价值率",
    "MEA5-014": "第八章 工作日", "MEA5-015": "第九章 剩余价值率和剩余价值量",
    "MEA5-016": "第十章 相对剩余价值的概念", "MEA5-017": "第十一章 协作",
    "MEA5-018": "第十二章 分工和工场手工业", "MEA5-019": "第十三章 机器和大工业",
    "MEA5-020": "第十四章 绝对剩余价值和相对剩余价值", "MEA5-021": "第十五章 劳动力价格和剩余价值的量的变化",
    "MEA5-022": "第十六章 剩余价值率的各种公式", "MEA5-023": "第十七章 劳动力的价值或价格转化为工资",
    "MEA5-024": "第十八章 计时工资", "MEA5-025": "第十九章 件工资".replace("件", "计件"),
    "MEA5-026": "第二十章 工资的国民差异", "MEA5-027": "第二十一章 简单再生产",
    "MEA5-028": "第二十二章 剩余价值转化为资本", "MEA5-029": "第二十三章 资本主义积累的一般规律",
    "MEA5-030": "第二十四章 所谓原始积累", "MEA5-031": "第二十五章 现代殖民理论",
}


GLOSSARY_FILES = [
    ("../政经术语表整理/_整理结果/verified_names.csv", ("src", "dst")),
    ("../政经术语表整理/_整理结果/glossary_core.csv", ("src", "dst")),
]


def load_glossary(root):
    """加载专名表。只用专有名词：英文侧要求首字母大写命中，
    否则 mill(工厂/穆勒)、smith(铁匠/斯密) 这类裸姓氏会大面积误锚。"""
    seen, out = set(), []
    for rel, (ks, kd) in GLOSSARY_FILES:
        fp = os.path.join(root, rel)
        if not os.path.exists(fp):
            continue
        import csv
        for row in csv.DictReader(open(fp, encoding="utf-8-sig")):
            src, dst = (row.get(ks) or "").strip(), (row.get(kd) or "").strip()
            if len(src) < 4 or len(dst) < 2 or " " in dst:
                continue
            if row.get("kind") in ("other",):
                continue
            key = (src.lower(), dst)
            if key in seen:
                continue
            seen.add(key)
            pat = re.compile(r"\b" + r"\s+".join(
                re.escape(w[:1].upper() + w[1:]) for w in src.split()) + r"\b")
            out.append((src.lower(), dst, pat))
    return out


def build_hits(texts, entries, side):
    hits = []
    for t in texts:
        if side == "en":
            hits.append(frozenset(k for k, (sl, d, pat) in enumerate(entries) if pat.search(t)))
        else:
            hits.append(frozenset(k for k, (sl, d, pat) in enumerate(entries) if d in t))
    return hits


def load(p):
    d = collections.defaultdict(list)
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if r["kind"] == "para":
            d[r["doc"]].append(r["text"])
    return d


NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")


def nums(t):
    return set(x.rstrip(".,") for x in NUM.findall(t))


def feats(t, lang):
    if lang == "en":
        s = len(EN_S.findall(t)) + 1
    else:
        s = len(ZH_S.findall(t))
    return len(t), max(s, 1)


def seg_cost(e, z, ne=None, nz=None, hit=0):
    """单段对单段的代价。e=(chars,sents) 英文，z 中文。

    长度比与句数是弱约束，数字是跨语强锚——数字对不上就重罚，
    这是唯一不依赖词表、又能跨语言直接比对的证据。
    """
    el, es = e
    zl, zs = z
    len_dev = abs(math.log((zl + 1.0) / (el * C0 + 1.0)))
    sent_dev = abs(zs - es) / max(es, zs, 1)
    c = 1.5 * len_dev + 1.0 * sent_dev
    if ne and nz:
        c += 2.5 * (1.0 - len(ne & nz) / len(ne | nz))
    c -= 0.45 * min(hit, 3)          # 专名锚：弱奖励，只用来打破平局
    return c


def merge_feats(items):
    return (sum(x[0] for x in items), sum(x[1] for x in items))


def align(en, zh, entries=None, skip_cost=1.4, merge_pen=0.55, max_merge=2):
    n, m = len(en), len(zh)
    EF = [feats(t, "en") for t in en]
    ZF = [feats(t, "zh") for t in zh]
    EN = [nums(t) for t in en]
    ZN = [nums(t) for t in zh]
    EH = build_hits(en, entries, "en") if entries else [frozenset()] * n
    ZH_ = build_hits(zh, entries, "zh") if entries else [frozenset()] * m
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        row = dp[i]
        for j in range(m + 1):
            cur = row[j]
            if cur == INF:
                continue
            if i < n and j < m:
                c = cur + seg_cost(EF[i], ZF[j], EN[i], ZN[j], len(EH[i] & ZH_[j]))
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c; bk[i + 1][j + 1] = (1, 1)
            if i < n:
                c = cur + skip_cost
                if c < dp[i + 1][j]:
                    dp[i + 1][j] = c; bk[i + 1][j] = (1, 0)
            if j < m:
                c = cur + skip_cost
                if c < dp[i][j + 1]:
                    dp[i][j + 1] = c; bk[i][j + 1] = (0, 1)
            # 分卷体例差异可能很大：英文一个 p 常等于中文好几段（反之亦然），
            # 因此合并上限放到 6，代价随 k 线性增长，避免无节制合并。
            if i < n and j < m:
                acc_e, acc_n = EF[i], set(EN[i])
                for k in range(2, max_merge + 1):
                    if i + k <= n:
                        acc_e = merge_feats([acc_e, EF[i + k - 1]])
                        acc_n |= EN[i + k - 1]
                        c = cur + seg_cost(acc_e, ZF[j], acc_n, ZN[j]) + merge_pen * (k - 1)
                        if c < dp[i + k][j + 1]:
                            dp[i + k][j + 1] = c; bk[i + k][j + 1] = (k, 1)
                    if j + k <= m:
                        acc_z = merge_feats(ZF[j:j + k])
                        c = cur + seg_cost(EF[i], acc_z, EN[i], set().union(*ZN[j:j + k])) \
                            + merge_pen * (k - 1)
                        if c < dp[i + 1][j + k]:
                            dp[i + 1][j + k] = c; bk[i + 1][j + k] = (1, k)
    i, j, path = n, m, []
    while i or j:
        a, b = bk[i][j]
        path.append((i - a, i, j - b, j))
        i, j = i - a, j - b
    return list(reversed(path)), dp[n][m]


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    en = load(os.path.join(root, "corpus/mecw35.jsonl"))
    zh = load(os.path.join(root, "corpus/mea5.jsonl"))
    entries = load_glossary(root)
    print(f"专名锚 {len(entries)} 条")
    out, stats = [], []
    for en_docs, zh_doc in CHAPTER_MAP:
        E, EID = [], []
        for d in en_docs:
            for k, t in enumerate(en[d]):
                E.append(t); EID.append((d, k))
        Z = zh[zh_doc]
        path, total = align(E, Z, entries)
        one = sum(1 for a, b, c, d in path if a < b and c < d)
        paird = sum(1 for a, b, c, d in path if a < b and c < d)
        for a, b, c, d in path:
            for i in range(a, b):
                out.append({"en_doc": EID[i][0], "en_i": EID[i][1],
                            "zh_doc": zh_doc, "zh_i": c if c < d else None,
                            "kind": f"{b-a}-{d-c}", "chapter": ZH_TITLE[zh_doc]})
        stats.append((ZH_TITLE[zh_doc], len(E), len(Z), one, total))
    with open(os.path.join(root, "corpus/align_mecw35_mea5.jsonl"), "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{'章':30s} {'EN':>4s} {'ZH':>4s} {'配对':>4s} {'代价':>7s}")
    for t, ne, nz, one, tot in stats:
        print(f"{t:30s} {ne:4d} {nz:4d} {one:4d} {tot:7.1f}")
    print(f"\n总英文段 {sum(s[1] for s in stats)}  对齐记录 {len(out)}")


if __name__ == "__main__":
    main()
