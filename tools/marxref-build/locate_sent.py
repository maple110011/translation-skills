"""英文引文 → 中文《资本论》第一卷 句级定位。

与 locate.py 的区别：直接检索英文句、查句级对齐表，不再依赖段级点映射。
段级只用来限定范围（见 align_sent.py），定位精度到句。
"""
import json, re, os, collections
from locate import STOP, WORD, content, grams, norm_words

EN_S = re.compile(r'(?<=[.!?])\s+(?=["\u201c\u2018]?[A-Z0-9])')


def sents_en(t):
    return [x.strip() for x in EN_S.split(t) if x.strip()]


class SentLocator:
    def __init__(self, root):
        self.pmap = {}
        pp = os.path.join(root, "corpus/mea5_pages.jsonl")
        if os.path.exists(pp):
            for l in open(pp, encoding="utf-8"):
                r = json.loads(l)
                self.pmap[(r["doc"], r["i"])] = r
            self.pidx = json.load(open(os.path.join(root, "corpus/pages_index.json"), encoding="utf-8"))
        else:
            self.pidx = {}
        path = os.path.join(root, "corpus/align_sent.jsonl")
        self.rows = []
        for l in open(path, encoding="utf-8"):
            r = json.loads(l)
            r["_c"] = set(content(r["en"]))
            r["_g"] = grams(norm_words(r["en"]))
            r["_w"] = set(norm_words(r["en"]))
            self.rows.append(r)
        # 同一英文段内按句序排，便于合并跨句引文
        self.rows.sort(key=lambda r: (r["en_doc"], r["en_i"], r["en_s"]))
        self.units = []
        byseg = collections.defaultdict(list)
        for r in self.rows:
            byseg[(r["en_doc"], r["en_i"])].append(r)
        for _k, seg in byseg.items():
            seg.sort(key=lambda r: r["en_s"])
            for a in range(len(seg)):
                for w in (1, 2, 3):
                    if a + w > len(seg):
                        break
                    win = seg[a:a + w]
                    txt = " ".join(x["en"] for x in win)
                    self.units.append({
                        "text": txt,
                        "partial": any(x["zh"] is None for x in win),
                        "zh_doc": win[0].get("zh_doc"), "zh_i": win[0].get("zh_i"),
                        "zh_s": win[0].get("zh_s"),
                        "zh": " ".join(x["zh"] for x in win if x["zh"]),
                        "chapter": win[0]["chapter"],
                        "span": w,
                        "_c": set(content(txt)),
                        "_g": grams(norm_words(txt)),
                        "en": txt,
                    })

    def page_of(self, doc, i, sent_idx):
        """句子在段内的位置按字符比例插值到页——只用段的起始页，
        在跨 4 页的长段落里会偏得很离谱（实测差 4 页）。"""
        m = self.pmap.get((doc, i))
        if not m or not m.get("b_start"):
            return None, None
        span = max(1, m["pdf_page_end"] - m["pdf_page"])
        ratio = min(1.0, sent_idx / max(1, span * 6))
        p = m["pdf_page"] + round(ratio * span)
        return p, self.pidx.get(str(p))

    def _score(self, qs, qg, r):
        cover = len(qs & r["_c"]) / len(qs) if qs else 0.0
        ng = len(qg & r["_g"]) / len(qg) if qg else 0.0
        # 含未对齐句的窗口降权：它的中文来自相邻句，直接给出会误导
        pen = 0.72 if r.get("partial") else 1.0
        return (0.45 * cover + 0.55 * ng) * pen, cover, ng

    def locate(self, quote, topk=3):
        qs = set(content(quote))
        qg = grams(norm_words(quote))
        if not qs:
            return []
        cands = []
        for r in self.units:
            s, cover, ng = self._score(qs, qg, r)
            if s > 0.10:
                cands.append((s, cover, ng, r))
        cands.sort(key=lambda x: -x[0])
        out, seen = [], set()
        for s, cover, ng, r in cands:
            key = (r["chapter"], r["en"][:48], r["span"])
            if key in seen:
                continue
            seen.add(key)
            pg, pr = self.page_of(r.get("zh_doc"), r.get("zh_i"), r.get("zh_s") or 0)
            out.append({"score": round(s, 3), "cover": round(cover, 2), "ngram": round(ng, 2),
                        "unaligned": not r["zh"], "pdf_page": pg, "print_page": pr,
                        "chapter": r["chapter"], "en": r["en"], "zh": r["zh"], "span": r["span"],
                        "evidence": sorted(qg & r["_g"], key=len)[-3:]})
            if len(out) >= topk:
                break
        return out


TESTS = [
    ('The wealth of those societies in which the capitalist mode of production prevails, '
     'presents itself as "an immense accumulation of commodities," its unit being a single commodity.',
     "资本主义生产方式占统治地位的社会的财富"),
    ('Labour is, in the first place, a process in which both man and Nature participate, and in '
     'which man of his own accord starts, regulates, and controls the material re-actions between '
     'himself and Nature.', "劳动首先是人和自然之间的过程"),
    ('Accumulate, accumulate! That is Moses and the prophets!', "积累啊，积累啊"),
    ('Force is the midwife of every old society pregnant with a new one.', "暴力是每一个孕育着新社会的旧社会的助产婆"),
    ('The rate of surplus-value is therefore an exact expression for the degree of exploitation of '
     'labour-power by capital, or of the labourer by the capitalist.', "剩余价值率是劳动力受资本剥削的程度"),
    ('The wealth of societies dominated by the capitalist mode of production appears as a huge '
     'collection of commodities, the single commodity being its elementary form.', "庞大的商品堆积"),
]


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    loc = SentLocator(root)
    ok = 0
    for q, gold in TESTS:
        res = loc.locate(q)
        hit = bool(res) and gold in (res[0]["zh"] or "")
        ok += hit
        print("=" * 76)
        print(("✓ " if hit else "✗ ") + "引文: " + q[:80])
        for k, r in enumerate(res[:2]):
            print(f"   {'★' if k==0 else ' '} [{r['chapter']}] 分数{r['score']:.3f} "
                  f"覆盖{r['cover']:.2f} 3gram{r['ngram']:.2f}")
            print(f"     中文: {r['zh'][:78]}")
            if k == 0:
                print(f"     期望含: {gold}")
    print(f"\n命中 {ok}/{len(TESTS)}")


if __name__ == "__main__":
    main()
