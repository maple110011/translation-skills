"""按内容为未映射的中文篇目找英文候选，不依赖我对英文篇名的猜测。

只用两个跨语言、免词表的信号：
1. **数字重合**：中文篇目里的数字出现在英文篇目里的比例。数字是唯一字面可比的东西，
   马克思文本里数字密度不低（年份、金额、百分比、卷次），是最硬的锚。
2. **长度比**：中文正文字数 / 英文字数，正常落在 0.15—0.45。

这一步只产出候选清单供人工确认，不直接写 works.csv——
标题猜错会静默产生错对齐，比不给结果更糟。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")


def nums(t):
    return {re.sub(r"[, ]", "", x).strip(".") for x in NUM.findall(t or "") if x.strip(".")}


def load_corpus(path):
    d = {}
    if not os.path.exists(path):
        return d
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r["kind"] == "para":
            d.setdefault(r["doc"], []).append(r["text"])
    return d


def main():
    resolved = json.load(open(os.path.join(ROOT, "index/works_resolved.json"), encoding="utf-8"))
    titles = {r["file"]: r for r in
              (json.loads(l) for l in open(os.path.join(ROOT, "index/mecw_titles.jsonl"),
                                           encoding="utf-8"))}
    # 允许卷：按文集卷次与年代的大致对应（宽一点，宁多勿漏）
    ALLOW = {
        1: {3, 4, 5, 6, 7, 9},
        2: {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16},
        3: {20, 21, 22, 23, 24, 25, 26},
        4: {25, 26, 27},
    }
    zh_cache, en_cache = {}, {}

    def zh_docs(v):
        if v not in zh_cache:
            zh_cache[v] = load_corpus(os.path.join(ROOT, f"corpus/mea{v}.jsonl"))
        return zh_cache[v]

    def en_docs(v):
        if v not in en_cache:
            en_cache[v] = load_corpus(os.path.join(ROOT, f"corpus/mecw{v}.jsonl"))
        return en_cache[v]

    ZH_TITLES = {}
    mt = os.path.join(ROOT, "index/mea_titles.jsonl")
    if os.path.exists(mt):
        for line in open(mt, encoding="utf-8"):
            r = json.loads(line)
            ZH_TITLES[(r["vol"], r["file"])] = r["title"]

    wanted = {}
    for key, it in resolved.items():
        if it["en"]:
            continue
        wanted[key] = it

    # 也把"未纳入映射"的中文档一起找（卷1/3 各有一两个漏的）
    covered = {it["zh"] for it in resolved.values()}
    for v in (1, 3):
        for doc in zh_docs(v):
            if doc not in covered:
                wanted[f"x{v}-{doc}"] = {"vol": v, "zh": doc, "en": [], "how": "未列入 works.csv"}

    out = []
    for key, it in wanted.items():
        vol, zdoc = it["vol"], it["zh"]
        Z = zh_docs(vol).get(zdoc, [])
        if not Z:
            continue
        zn = set()
        for t in Z:
            zn |= nums(t)
        zl = sum(len(x) for x in Z)
        pool = []
        for mv in ALLOW.get(vol, set()):
            for doc, E in en_docs(mv).items():
                if not E:
                    continue
                el = sum(len(x) for x in E)
                if not el:
                    continue
                en = set()
                for t in E:
                    en |= nums(t)
                ov = len(zn & en) / len(zn) if zn else 0.0
                ratio = zl / el
                pen = 0.0 if 0.10 <= ratio <= 0.60 else min(1.0, abs(ratio - 0.30) / 0.35)
                score = ov * 0.75 + (1.0 - pen) * 0.25
                if score <= 0:
                    continue
                t = titles.get(f"{doc}.html") or {}
                pool.append((score, ov, ratio, mv, doc, (t.get("title") or "")[:58],
                             len(zn), len(E)))
        pool.sort(key=lambda x: -x[0])
        out.append({"key": key, "vol": vol, "zh": zdoc,
                    "zh_title": ZH_TITLES.get((vol, zdoc), ""),
                    "zh_len": zl, "zh_nums": len(zn), "how": it.get("how", ""),
                    "cands": pool[:4]})

    out.sort(key=lambda x: (x["vol"], x["zh"]))
    with open(os.path.join(ROOT, "index/unmapped_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for o in out:
        print(f"\n[卷{o['vol']}] {o['zh']} {o['zh_title'][:40]}  字{o['zh_len']} 数字{o['zh_nums']}  ({o['how']})")
        if not o["cands"]:
            print("   无候选")
        for sc, ov, ratio, mv, doc, title, zn, en in o["cands"]:
            print(f"   分{sc:.2f} 数字{ov:.2f} 长度比{ratio:.2f}  MECW{mv}-{doc}  {title}")


if __name__ == "__main__":
    main()
