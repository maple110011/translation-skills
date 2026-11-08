"""第 8 卷（《资本论》手稿选编）构建。

与第 1—4、10 卷的根本区别：中文是**摘选**，一篇中文只对应英文手稿里的一小段，
而且摘选的边界由编译局划定，英文侧没有对应标记。逐篇独立搜索会各说各话，
所以改成**按年代分组整体对齐**：

  1857—58 手稿 → MECW 28—29
  1861—63 手稿 → MECW 30—33
  1863—65 手稿 → MECW 34

每组把英文全部段落按卷/文件顺序串起来，中文按篇号顺序串起来，做一次全局单调 DP。
英文段落数远多于中文（约 4:1），靠 skip 转移吸收；中文是摘选，几乎每段都该配上。
对齐后每个英文段落得到一段中文区间，再在段内做句级配对。

输出格式与其他卷一致，引擎无需改动。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from align import load_glossary, load
from align_vol8 import align_monotone
from align_sent import align_sent_pairs, sents_en, sents_zh, expand_span

ROOT = os.path.dirname(os.path.abspath(__file__))

# 只列出手稿正文所在文件。整卷纳入会串味——MECW 29 后半是 1859 年
# 《政治经济学批判》一书，不属于 1857—58 手稿；MECW 30/33/34 的卷首说明、
# 附录、笔记本索引同理。实测整卷纳入会让中文「资本主义生产以前的各种形式」
# 落到讲商品交换的段落上。
GROUPS = [
    (4, 31, ["MECW28-004", "MECW28-005", "MECW28-006", "MECW28-007", "MECW28-008",
             "MECW29-004", "MECW29-006"], "1857—1858 年手稿"),
    (32, 54, ["MECW30-003", "MECW30-004", "MECW30-005", "MECW30-006",
              "MECW30-009", "MECW30-010", "MECW30-011",
              "MECW31-004", "MECW31-005", "MECW31-006", "MECW31-007", "MECW31-008",
              "MECW31-009", "MECW31-010", "MECW31-011", "MECW31-012", "MECW31-013",
              "MECW31-014", "MECW31-015",
              "MECW32-003", "MECW32-005", "MECW32-006", "MECW32-007", "MECW32-008",
              "MECW32-009", "MECW32-010", "MECW32-012",
              "MECW33-003", "MECW33-004", "MECW33-005", "MECW33-008", "MECW33-009",
              "MECW33-010", "MECW33-011"], "1861—1863 年手稿"),
    (55, 66, ["MECW34-004", "MECW34-005", "MECW34-006", "MECW34-007", "MECW34-008",
              "MECW34-009"], "1863—1865 年手稿"),
]
# 卷首说明、目录、附录、笔记本索引之类，不参与对齐
SKIP_EN = re.compile(r"preface to marx-engels collected works|^das kapital$|"
                     r"^appendix|references to my own notebooks|^contents of the manuscript|"
                     r"^preface$|^addenda to part", re.I)
SKIP_ZH = re.compile(r"索引|说明|目录")


def zh_title(doc):
    import html
    p = os.path.join(ROOT, f"raw/mea8/{doc}.html")
    if not os.path.exists(p):
        return doc
    s = open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else doc
    return t or doc


def main():
    zh_all = load(os.path.join(ROOT, "corpus/mea8.jsonl"))
    en_all = {}
    for v in range(28, 35):
        en_all.update(load(os.path.join(ROOT, f"corpus/mecw{v}.jsonl")))
    entries = load_glossary(ROOT)

    rows = []
    n_en_s = n_pairs = 0
    for a, b, vols, label in GROUPS:
        E, EID = [], []
        for d in vols:
            for k, t in enumerate(en_all.get(d, [])):
                E.append(t)
                EID.append((d, k, int(d[4:6])))
        Z, ZID = [], []
        for i in range(a, b + 1):
            doc = f"MEA8-{i:03d}"
            if doc not in zh_all or SKIP_ZH.search(zh_title(doc)):
                continue
            for k, t in enumerate(zh_all[doc]):
                Z.append(t)
                ZID.append((doc, k))
        if not E or not Z:
            print(f"  {label}: 缺语料（英 {len(E)} 中 {len(Z)}）")
            continue

        pairs, _ = align_monotone(E, Z)
        span = {i: (j, j) for i, j in pairs}
        hit = sum(1 for i in range(len(E)) if i in span)
        print(f"  {label}: 英 {len(E)} 段 / 中 {len(Z)} 段，配上 {hit} 英文段（{hit/len(E):.0%}）")

        for i in range(len(E)):
            cs, ce = expand_span(i, *span.get(i, (0, 0)), E, Z)
            es = sents_en(E[i])
            n_en_s += len(es)
            zs, zmap = [], []
            for j in range(cs, ce):
                for k, s in enumerate(sents_zh(Z[j])):
                    zs.append(s)
                    zmap.append((j, k))
            if not zs:
                for k, s in enumerate(es):
                    rows.append({"vol": 8, "chapter": "", "en": s, "zh": "",
                                 "zh_doc": None, "zh_i": None, "zh_s": None,
                                 "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                                 "unaligned": True})
                continue
            for k, jj in align_sent_pairs(es, zs):
                if jj is None:
                    rows.append({"vol": 8, "chapter": "", "en": es[k], "zh": "",
                                 "zh_doc": None, "zh_i": None, "zh_s": None,
                                 "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                                 "unaligned": True})
                    continue
                pj, pk = zmap[jj]
                zdoc = ZID[pj][0]
                rows.append({"vol": 8, "chapter": zh_title(zdoc), "en": es[k],
                             "zh": sents_zh(Z[pj])[pk], "zh_doc": zdoc,
                             "zh_i": ZID[pj][1], "zh_s": pk,
                             "en_doc": EID[i][0], "en_i": EID[i][1], "en_s": k,
                             "unaligned": False})
                n_pairs += 1

    got = sum(1 for r in rows if not r["unaligned"])
    print(f"卷 8（《资本论》手稿选编）: 英文句 {n_en_s}  配对 {got}  {got/max(n_en_s,1):.1%}")
    out = os.path.join(ROOT, "corpus/vol8_sent.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("→", out)


if __name__ == "__main__":
    main()
