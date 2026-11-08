"""英文引文 → 中文《资本论》第一卷 定位。

流程：引文 → 英文段打分(top-k) → 查对齐表 → 中文段 + 章名 + 置信度

打分不依赖嵌入模型，纯词面：
  cover  = 引文内容词有多少出现在候选段（对语序变化不敏感）
  ngram  = 引文 3-gram 有多少原样出现在候选段（对措辞忠实度敏感，精度高）
两者加权。既容忍不同英译的用词差异，又能在措辞接近时明确胜出。
"""
import json, re, os, sys, math, collections

STOP = set("""a an the of to in on at by for with from as is are was were be been being
that this these those it its his her their our your my he she they we you i him them us
and or but if then than so such not no nor only own same very can will just should now
which who whom whose what when where why how all any both each few more most other some
does do did doing done has have had having would could may might must shall into upon
there here out up down over under again further once also thus therefore however although
because while during before after above below between through against about within without
""".split())

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")
EN_SENT = re.compile(r'(?<=[.!?])\s+(?=["\u201c\u2018]?[A-Z0-9])')
ZH_SENT = re.compile(r'(?<=[。！？；])')


def split_sent_en(t):
    return [x for x in EN_SENT.split(t) if x.strip()]


def split_sent_zh(t):
    return [x for x in ZH_SENT.split(t) if x.strip()]


def norm_words(t):
    return [w.lower() for w in WORD.findall(t)]


def content(t):
    return [w for w in norm_words(t) if w not in STOP and len(w) > 2]


def grams(ws, n=3):
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def load_corpus(p):
    d = collections.defaultdict(list)
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if r["kind"] == "para":
            d[r["doc"]].append(r["text"])
    return d


def load_align(p):
    m = {}
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        m[(r["en_doc"], r["en_i"])] = r
    return m


class Locator:
    def __init__(self, root):
        self.en = load_corpus(os.path.join(root, "corpus/mecw35.jsonl"))
        self.zh = load_corpus(os.path.join(root, "corpus/mea5.jsonl"))
        self.align = load_align(os.path.join(root, "corpus/align_mecw35_mea5.jsonl"))
        self.docs = [d for d in sorted(self.en) if any(k[0] == d for k in self.align)]
        self.cache = {}
        for d in self.docs:
            for i, t in enumerate(self.en[d]):
                w = norm_words(t)
                self.cache[(d, i)] = (set(content(t)), grams(w), w)

    def sentence_hit(self, quote, en_text, zh_text):
        """段内句级定位：英文段里哪一句最接近引文，按句序比例映射到中文句。"""
        es = split_sent_en(en_text)
        zs = split_sent_zh(zh_text) if zh_text else []
        if not es:
            return None, None, ""
        qg = grams(norm_words(quote))
        qs = set(content(quote))
        best, bi = -1.0, 0
        sp = max(1, len(es))
        for k, s0 in enumerate(es):
            cgs, cs = grams(norm_words(s0)), set(content(s0))
            ng = len(qg & cgs) / len(qg) if qg else 0.0
            cov = len(qs & cs) / len(qs) if qs else 0.0
            v = 0.6 * ng + 0.4 * cov - 0.02 * abs(k - sp / 2) / sp
            if v > best:
                best, bi = v, k
        zj = None
        if zs:
            zj = min(int(round(bi * len(zs) / len(es))), len(zs) - 1)
        return (es[bi] if es else None), (zs[zj] if zs else None), f"{bi+1}/{len(es)}"

    def locate(self, quote, topk=3):
        qw = content(quote)
        qg = grams(norm_words(quote))
        if not qw:
            return []
        qs = set(qw)
        scored = []
        for (d, i), (cs, cg, _w) in self.cache.items():
            if (d, i) not in self.align:
                continue
            cover = len(qs & cs) / len(qs)
            ng = (len(qg & cg) / len(qg)) if qg else 0.0
            score = 0.45 * cover + 0.55 * ng
            if score > 0.08:
                scored.append((score, cover, ng, d, i))
        scored.sort(reverse=True)
        out, seen = [], set()
        for score, cover, ng, d, i in scored:
            a = self.align[(d, i)]
            key = (a["zh_doc"], a["zh_i"])
            if key in seen:
                continue
            seen.add(key)
            j = a["zh_i"]
            ev = sorted(qg & self.cache[(d, i)][1], key=len)[-3:]
            zt = self.zh[a["zh_doc"]][j] if j is not None else None
            en_s, zh_s, sp = self.sentence_hit(quote, self.en[d][i], zt)
            out.append({
                "score": round(score, 3), "cover": round(cover, 3), "ngram": round(ng, 3),
                "chapter": a["chapter"], "en_doc": d, "en_i": i,
                "zh_doc": a["zh_doc"], "zh_i": j,
                "en": self.en[d][i],
                "zh": zt, "en_sent": en_s, "zh_sent": zh_s, "sent_pos": sp,
                "evidence": ev,
            })
            if len(out) >= topk:
                break
        return out


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    loc = Locator(root)
    tests = [
        ('The wealth of those societies in which the capitalist mode of production prevails, '
         'presents itself as "an immense accumulation of commodities," its unit being a single commodity.'),
        ('Labour is, in the first place, a process in which both man and Nature participate, and in '
         'which man of his own accord starts, regulates, and controls the material re-actions between '
         'himself and Nature.'),
        ('Accumulate, accumulate! That is Moses and the prophets!'),
        ('Force is the midwife of every old society pregnant with a new one.'),
        ('The rate of surplus-value is therefore an exact expression for the degree of exploitation of '
         'labour-power by capital, or of the labourer by the capitalist.'),
        ('The wealth of societies dominated by the capitalist mode of production appears as a huge '
         'collection of commodities, the single commodity being its elementary form.'),
    ]
    for q in tests:
        print("=" * 78)
        print("引文:", q[:96] + ("..." if len(q) > 96 else ""))
        for k, r in enumerate(loc.locate(q)):
            tag = "★" if k == 0 else " "
            print(f" {tag} [{r['chapter']}] 分数{r['score']:.3f} 词覆盖{r['cover']:.2f} 3gram{r['ngram']:.2f}")
            print(f"    EN: {r['en'][:88]}")
            if r["zh_sent"]:
                print(f"    中文句(段内第{r['sent_pos']}句): {r['zh_sent']}")
            else:
                print(f"    ZH段: {(r['zh'] or '-')[:60]}")
            if k == 0:
                print(f"    证据: {r['evidence']}")


if __name__ == "__main__":
    main()
