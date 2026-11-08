"""客户端：本地直连或走 HTTP，两种模式同一个接口。

    from client import MarxRef
    mr = MarxRef()                      # 本地（直接 import engine，最快）
    mr = MarxRef(remote="http://127.0.0.1:8080")   # 远程

    mr.match("Force is the midwife of every old society pregnant with a new one.")
    mr.match_many(["...", "..."])       # 批量

命令行：
    python client.py "force is the midwife..."
    python client.py --remote http://127.0.0.1:8080 "..."
"""
import json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MarxRef:
    def __init__(self, remote=None, corpus_dir=None):
        self.remote = remote.rstrip("/") if remote else None
        self._eng = None
        self._dir = corpus_dir

    # ---- 本地 ----
    @property
    def engine(self):
        if self._eng is None:
            from engine import Engine
            self._eng = Engine(corpus_dir=self._dir)
        return self._eng

    def meta(self):
        if self.remote:
            return self._get("/v1/meta")
        return self.engine.meta()

    def match(self, text, topk=3, volumes=None, min_score=0.12):
        if self.remote:
            return self._post("/v1/match", {"text": text, "topk": topk,
                                            "volumes": volumes, "min_score": min_score})["matches"]
        return self.engine.match(text, topk=topk, volumes=volumes, min_score=min_score)

    def quotes(self, markdown):
        """只抽取 Markdown 里的英文引文，先看看会处理哪些，不落盘。"""
        if self.remote:
            return self._post("/v1/quotes", {"markdown": markdown})["quotes"]
        import quotes as Q
        return Q.extract(markdown)

    def article(self, markdown, mode="annotate", min_ok=0.80, min_hit=0.55):
        """整篇处理：返回 {stats, annotated, items}。mode=annotate 保留英文并列中文。"""
        if self.remote:
            return self._post("/v1/article", {"markdown": markdown, "mode": mode,
                                             "min_ok": min_ok, "min_hit": min_hit})
        import article as A
        out, items, stats = A.process(markdown, self.engine, mode=mode,
                                      min_ok=min_ok, min_hit=min_hit)
        return {"stats": stats, "annotated": out,
                "items": [{k: v for k, v in it.items() if k != "edit"} for it in items]}

    def match_many(self, texts, topk=1, volumes=None):
        if self.remote:
            return self._post("/v1/match/batch", {"texts": texts, "topk": topk,
                                                  "volumes": volumes})["results"]
        return [{"query": t, "matches": self.engine.match(t, topk=topk, volumes=volumes) if t else []}
                for t in texts]

    # ---- HTTP ----
    def _get(self, path):
        with urllib.request.urlopen(self.remote + path, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self, path, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.remote + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))


def fmt(m):
    pg = f"第 {m['page']} 页" if m.get("page") else "页码待核"
    zh = m.get("zh") or "（该句未对齐，需人工核）"
    return (f"[卷{m['vol']}] {m['chapter']} · {pg}   匹配度 {m['score']:.2f}\n"
            f"  {zh}\n  EN: {m['en'][:110]}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    remote = None
    if "--remote" in args:
        i = args.index("--remote")
        remote = args[i + 1]
        args = args[:i] + args[i + 2:]
    q = " ".join(args).strip()
    if not q:
        print(__doc__)
        return
    mr = MarxRef(remote=remote)
    for m in mr.match(q):
        print(fmt(m))
        print()


if __name__ == "__main__":
    main()
