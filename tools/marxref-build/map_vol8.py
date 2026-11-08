"""第 8 卷（《资本论》手稿选编）映射：在 MECW 28—34 的正文里定位中文摘选对应的段落区间。

为什么不能像第 5—7 卷那样按章号配对：中文第 8 卷是**摘选**，一段中文对应的
是英文手稿里任意位置的一小段；中文的小标题（[货币的产生和本质] 之类）
是编译局后加的，英文里根本没有。

三条约束把搜索空间压到可用：
1. **年代分组**　中文的三大块分别对应 MECW 28-29（1857-58 手稿）、
   30-33（1861-63 手稿）、34（1863-65 手稿），不允许跨组。
2. **单调游标**　中文摘选按手稿顺序排列，英文文件也按顺序，所以后一篇的
   起点不能早于前一篇的终点（允许少量回退）。
3. **数字 F1**　窗口得分用 2|Z∩E|/(|Z|+|E|)，而不是「中文数字被覆盖多少」。
   后者会让宽窗口把全部数字包进去，得分虚高——实测所有候选都能拿 1.00，等于没区分度。

没有数字的段落拿不到锚，沿用上一篇的文件与游标顺延。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_works as B

ROOT = os.path.dirname(os.path.abspath(__file__))
NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")

# 中文篇号 → (对应 MECW 卷组, 分组名)
GROUPS = [
    (4, 31, [28, 29], "1857—1858 年手稿"),
    (32, 54, [30, 31, 32, 33], "1861—1863 年手稿"),
    (55, 66, [34], "1863—1865 年手稿"),
]
SKIP = re.compile(r"索引|说明|目录")


def nums(t):
    return {re.sub(r"[, ]", "", x).strip(".") for x in NUM.findall(t or "") if x.strip(".")}


def scan(Z, E, EN, ZN, cursor, back=60):
    """在 E 上从 cursor-back 起滑窗，返回 (F1, 起, 止)。"""
    n = len(E)
    if not n:
        return 0.0, 0, 0
    lo = max(1, len(Z))
    hi = min(n - max(0, cursor - back), max(lo, int(len(Z) * 2.2)))
    start_min = max(0, cursor - back)
    best = (0.0, start_min, min(n - 1, start_min + lo))
    for w in range(lo, max(lo, hi) + 1):
        for s in range(start_min, max(start_min + 1, n - w + 1)):
            acc = set()
            for k in range(s, min(n, s + w)):
                acc |= EN[k]
            if not acc:
                continue
            inter = len(ZN & acc)
            if not inter:
                continue
            f1 = 2.0 * inter / (len(ZN) + len(acc))
            if f1 > best[0]:
                best = (f1, s, min(n - 1, s + w - 1))
    return best


def main():
    zh = B.load(os.path.join(ROOT, "corpus/mea8.jsonl"))
    en = {}
    for v in range(28, 35):
        for d, paras in B.load(os.path.join(ROOT, f"corpus/mecw{v}.jsonl")).items():
            if paras:
                en[d] = (v, paras)
    order = []
    for v in range(28, 35):
        order += [d for d, (vv, _) in en.items() if vv == v]

    mea_titles = {}
    for line in open(os.path.join(ROOT, "index/mea_titles.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        if r["vol"] == 8:
            mea_titles[r["file"]] = r["title"]

    rows = []
    for a, b, vols, label in GROUPS:
        docs = [f"MEA8-{i:03d}" for i in range(a, b + 1)]
        files = [d for d in order if en[d][0] in vols]
        fpos = {d: i for i, d in enumerate(files)}
        cur_file = 0
        cur_para = 0
        print(f"\n== {label}  候选文件 {len(files)} 个")
        for doc in docs:
            Z = zh.get(doc) or []
            title = mea_titles.get(doc, doc)
            if not Z or SKIP.search(title):
                continue
            ZN = set()
            for t in Z:
                ZN |= nums(t)
            if len(ZN) < 5:
                d = files[cur_file]
                v, E = en[d]
                w = max(6, int(len(Z) * 1.5))
                s = min(cur_para, max(0, len(E) - w - 1))
                rows.append({"vol": "8", "zh": doc, "note": title,
                             "en": f"P:{v}-{int(d[7:10]):03d}:{s}-{s + w}", "auto": "跟随"})
                cur_para = s + w
                print(f"  {doc} {title[:24]:26s} 无数字 → 跟随 MECW{v}-{d[7:10]} 段{s}")
                continue
            best = (0.0, None, 0, 0)
            for k in range(cur_file, len(files)):
                d = files[k]
                v, E = en[d]
                EN = [nums(t) for t in E]
                back = cur_para if k == cur_file else 0
                f1, s, e = scan(Z, E, EN, ZN, back)
                if f1 > best[0] + 1e-9:
                    best = (f1, k, s, e)
            f1, k, s, e = best
            if k is None or f1 < 0.12:
                print(f"  {doc} {title[:24]:26s} 无可靠候选（最高 {f1:.2f}），跳过")
                continue
            d = files[k]
            v, E = en[d]
            cur_file, cur_para = k, e + 1
            rows.append({"vol": "8", "zh": doc, "note": title,
                         "en": f"P:{v}-{int(d[7:10]):03d}:{s}-{e}", "auto": f"{f1:.2f}"})
            print(f"  {doc} {title[:24]:26s} → MECW{v}-{d[7:10]} 段{s}-{e}  F1={f1:.2f}")

    with open(os.path.join(ROOT, "index/vol8_map.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"\n映射 {len(rows)} 篇 → index/vol8_map.json")


if __name__ == "__main__":
    main()
