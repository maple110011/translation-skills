"""多义篇目裁决：同一部著作在 MECW 里常有多份（正文 / 草稿 / 不同版本），
标题一样，只能靠内容判。

两个跨语言、且不依赖词表的信号：
1. **长度比** 中文正文字数 / 英文字数。译文压缩率大致落在 0.15—0.45，偏离越远越可疑。
2. **数字重合** 中文段里的数字出现在对应英文段里的比例。数字是唯一字面可比的东西。

结果写回 index/works_resolved.json，并把每条裁决理由打进 index/works_decisions.csv。
"""
import os, re, sys, json, csv

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
    rp = os.path.join(ROOT, "index/works_resolved.json")
    resolved = json.load(open(rp, encoding="utf-8"))
    zh_cache, en_cache = {}, {}

    def zh_docs(v):
        if v not in zh_cache:
            zh_cache[v] = load_corpus(os.path.join(ROOT, f"corpus/mea{v}.jsonl"))
        return zh_cache[v]

    def en_docs(v):
        if v not in en_cache:
            en_cache[v] = load_corpus(os.path.join(ROOT, f"corpus/mecw{v}.jsonl"))
        return en_cache[v]

    rows, changed = [], 0
    for key, it in resolved.items():
        vol, zdoc, files = it["vol"], it["zh"], it["en"]
        if len(files) <= 1 or str(it.get("how", "")).startswith(("range", "list")):
            continue
        Z = zh_docs(vol).get(zdoc, [])
        if not Z:
            continue
        zat = "".join(Z)
        zn = set()
        for t in Z:
            zn |= nums(t)
        scored = []
        for fn in files:
            m = re.match(r"MECW(\d+)-(\d+)", os.path.basename(fn))
            if not m:
                continue
            mv = int(m.group(1))
            d = os.path.splitext(os.path.basename(fn))[0]
            E = en_docs(mv).get(d, [])
            if not E:
                continue
            eat = "".join(E)
            ratio = len(zat) / max(1, len(eat))
            en = set()
            for t in E:
                en |= nums(t)
            overlap = len(zn & en) / len(zn) if zn else None
            # 长度比落在 0.15—0.45 得满分，越远扣得越多
            len_pen = 0.0 if 0.15 <= ratio <= 0.45 else min(1.0, abs(ratio - 0.30) / 0.30)
            score = (1.0 - len_pen) * 0.6 + (overlap if overlap is not None else 0.5) * 0.4
            scored.append((score, ratio, overlap, fn, len(E)))
        if not scored:
            continue
        scored.sort(key=lambda x: -x[0])
        best = scored[0]
        keep = [best[3]]
        # 同一部作品被 MECW 拆成多篇（如手稿上/下册）时，第二名的长度比也合理就保留
        for s in scored[1:]:
            if s[0] >= best[0] - 0.08 and 0.10 <= s[1] <= 0.60:
                keep.append(s[3])
        if sorted(keep) != sorted(files):
            changed += 1
        it["en"] = keep
        it["how"] = f"裁决 {best[0]:.2f}"
        rows.append({
            "vol": vol, "zh": zdoc, "note": it.get("note", ""),
            "候选": " | ".join(f"{os.path.basename(s[3])}(分{s[0]:.2f},长度比{s[1]:.2f},"
                              f"数字{s[2] if s[2] is None else round(s[2],2)},段{s[4]})"
                              for s in scored),
            "选定": " | ".join(os.path.basename(x) for x in keep),
        })

    with open(rp, "w", encoding="utf-8") as f:
        json.dump(resolved, f, ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "index/works_decisions.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["vol", "zh", "note", "候选", "选定"])
        w.writeheader()
        w.writerows(rows)
    print(f"裁决 {len(rows)} 条，其中 {changed} 条改动了原始候选 → index/works_decisions.csv")
    for r in rows[:12]:
        print(f"  卷{r['vol']} {r['zh']} → {r['选定']}")
        print(f"        {r['候选'][:150]}")


if __name__ == "__main__":
    main()
