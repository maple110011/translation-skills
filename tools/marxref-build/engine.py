"""检索内核。纯标准库，可被任何程序直接 import。

    from engine import Engine
    eng = Engine()
    eng.match("Force is the midwife of every old society pregnant with a new one.")

设计要点
--------
1. 索引只建在「单句」上，用词级倒排把候选压到千级，再做 n-gram 精排。
   线性扫全库在批量场景（一篇论文几十条引文）会慢到不可用。
2. 跨句引文在查询时动态合并相邻句，不在索引里预建窗口——
   否则索引会膨胀三倍，而且合并逻辑不好维护。
3. 结果永远带 confidence 和 unaligned 标记，低分不假装确定。
"""
import os, re, json, glob, math

STOP = set("""a an the of to in on at by for with from as is are was were be been being
that this these those it its his her their our your my he she they we you i him them us
and or but if then than so such not no nor only own same very can will just should now
which who whom whose what when where why how all any both each few more most other some
does do did doing done has have had having would could may might must shall into upon
there here out up down over under again further once also thus therefore however although
because while during before after above below between through against about within without
""".split())

WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")
NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")


def words(t):
    return [w.lower() for w in WORD.findall(t or "")]


def nums(t):
    """抽出数字并归一化（10,000 / 10 000 / 10000 视为同一个）。
    数字是唯一不依赖词表、又能跨语言直接比对的证据，用来给结果做自检。"""
    out = set()
    for x in NUM.findall(t or ""):
        x = re.sub(r"[, ]", "", x).strip(".")
        if x:
            out.add(x)
    return out


def num_check(q, zh):
    """引文里的数字在中文句里对不上，多半是句子配对错了。"""
    qn, zn = nums(q), nums(zh)
    if len(qn) < 2:
        return "n/a"                    # 引文没数字，无从检验
    return "ok" if qn and len(qn & zn) / len(qn) >= 0.6 else "mismatch"


def content(t):
    return [w for w in words(t) if w not in STOP and len(w) > 2]


def grams(ws, n=3):
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


class Engine:
    def __init__(self, corpus_dir=None, use_index=True):
        self.dir = corpus_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
        self.units = []
        self.by_doc = {}
        for fp in sorted(glob.glob(os.path.join(self.dir, "vol*_sent.jsonl"))):
            vol = int(re.search(r"vol(\d+)_sent", os.path.basename(fp)).group(1))
            for line in open(fp, encoding="utf-8"):
                r = json.loads(line)
                u = {
                    "vol": vol, "chapter": r["chapter"], "en": r["en"], "zh": r.get("zh") or "",
                    "page": r.get("page"), "doc": r.get("en_doc"), "i": r.get("en_i"),
                    "s": r.get("en_s"), "unaligned": bool(r.get("unaligned")),
                }
                w = words(u["en"])
                u["_c"] = set(content(u["en"]))
                u["_g"] = grams(w)
                self.units.append(u)
                self.by_doc.setdefault((vol, u["doc"], u["i"]), []).append(u)
        self.volumes = sorted({u["vol"] for u in self.units})
        self.index = {}
        if use_index:
            for k, u in enumerate(self.units):
                for w in u["_c"]:
                    self.index.setdefault(w, set()).add(k)
        self.titles = self._load_titles()
        print(f"[engine] {len(self.units)} 句  卷 {self.volumes}  词表 {len(self.index)}")

    def _load_titles(self):
        p = os.path.join(self.dir, "volumes.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return {}

    def _candidates(self, qc):
        """用最短的几个倒排链求并集，把候选压到千级。"""
        if not self.index:
            return range(len(self.units))
        posts = sorted((self.index[w] for w in qc if w in self.index), key=len)
        if not posts:
            return []
        cand = set(posts[0])
        for p in posts[1:4]:
            cand |= p
            if len(cand) > 4000:
                break
        return cand

    def _score(self, qc, qg, u):
        cover = len(qc & u["_c"]) / len(qc) if qc else 0.0
        ng = len(qg & u["_g"]) / len(qg) if qg else 0.0
        return 0.45 * cover + 0.55 * ng, cover, ng

    def match(self, text, topk=3, volumes=None, min_score=0.12):
        qc, qw = set(content(text)), words(text)
        qg = grams(qw)
        if not qc:
            return []
        # 实词不足 4 个时信息量太低，命中率天然虚高：像 "the rate of profit"
        # 这种短语全库几百句都有，不该给满分。按实词数打折并加提示。
        nq = len(qc)
        damp = 1.0 if nq >= 4 else {1: 0.60, 2: 0.75, 3: 0.90}[nq]
        warn = "引文过短，仅作候选参考" if nq < 4 else ""
        picked = []
        for k in self._candidates(qc):
            u = self.units[k]
            if volumes and u["vol"] not in volumes:
                continue
            sc, cover, ng = self._score(qc, qg, u)
            if u["unaligned"]:
                sc *= 0.85          # 没对上中文的句子降权，避免把"空结果"排到第一
            sc *= damp
            if sc >= min_score:
                picked.append((sc, cover, ng, u))
        picked.sort(key=lambda x: -x[0])

        # 跨句合并：把命中的句子与前后句拼起来重打一次分
        merged, seen = [], set()
        for sc, cover, ng, u in picked[:40]:
            key = (u["vol"], u["doc"], u["i"])
            group = self.by_doc.get(key, [u])
            try:
                s0 = [x["s"] for x in group].index(u["s"])
            except ValueError:
                s0 = 0
            best = (sc, cover, ng, u)
            for w in (2, 3):
                win = group[s0:s0 + w]
                if len(win) < 2:
                    continue
                txt = " ".join(x["en"] for x in win)
                wc, wg = set(content(txt)), grams(words(txt))
                if not wc:
                    continue
                c2 = len(qc & wc) / len(qc)
                g2 = len(qg & wg) / len(qg) if qg else 0.0
                # 窗口里只要有一句没对上中文，拼出来的中文就是残缺的，
                # 必须当成"未对齐"并降权——否则半截译文会被当成完整答案打高分。
                partial = any(x["unaligned"] for x in win)
                s2 = (0.45 * c2 + 0.55 * g2) * (0.72 if partial else 1.0) * damp
                if s2 > best[0] + 0.02:
                    best = (s2, c2, g2, {**win[0],
                                         "en": txt,
                                         # 中文句子之间不加空格，否则会出现"元素形式。 因此"
                                         "zh": "".join(x["zh"] for x in win if x["zh"]),
                                         "unaligned": partial})
            sc2, c2, g2, u2 = best
            k2 = (u2["vol"], u2.get("doc"), u2.get("i"), u2["en"][:40])
            if k2 in seen:
                continue
            seen.add(k2)
            # 数字自检：引文有数字而中文对不上，几乎都是配对错位。降权并明示，
            # 避免"看着满分、其实错页"这种最坏的失败模式。
            nchk = num_check(text, u2.get("zh"))
            wn = warn                       # 每个候选独立，否则提示会越滚越长
            if nchk == "mismatch":
                sc2 *= 0.75
                wn = (wn + "；" if wn else "") + "数字与中文对不上，可能配对有误"
            merged.append({"score": round(sc2, 3), "coverage": round(c2, 3),
                           "ngram": round(g2, 3), "nq": nq, "numeric": nchk,
                           "warn": wn,
                           **{k: v for k, v in u2.items() if not k.startswith("_")}})
            if len(merged) >= topk:
                break
        return merged

    def meta(self):
        per = {}
        for u in self.units:
            d = per.setdefault(u["vol"], {"sentences": 0, "aligned": 0, "with_page": 0})
            d["sentences"] += 1
            d["aligned"] += not u["unaligned"]
            d["with_page"] += bool(u["page"])
        for v, d in per.items():
            t = self.titles.get(str(v), {})
            d["title"] = t.get("title", f"第{v}卷")
            d["source"] = t.get("source", "《马克思恩格斯文集》")
        return {"volumes": per, "total_sentences": len(self.units),
                "engine": "marxref/1.0", "edition": "《马克思恩格斯文集》（人民出版社，2009）"}


if __name__ == "__main__":
    import sys
    eng = Engine()
    q = " ".join(sys.argv[1:]) or "Force is the midwife of every old society pregnant with a new one."
    print(json.dumps(eng.match(q), ensure_ascii=False, indent=2))
