"""Marx 引文定位 · 后台服务。纯标准库，无第三方依赖。

作为常驻服务运行，供其他程序（网页、脚本、桌面工具）通过 HTTP 调用。

    python server.py                          # 127.0.0.1:8080
    python server.py --host 0.0.0.0 --port 8080   # 局域网可访问
    python server.py --token abc123           # 要求 Authorization: Bearer abc123

端点
----
GET  /healthz              健康检查（给 supervisor / 负载均衡用）
GET  /v1/meta              卷列表、句数、页码覆盖
GET  /v1/match?q=...       单条查询（便于浏览器/curl 直接试）
POST /v1/match             {"text": "...", "topk": 3, "volumes": [5,6]}
POST /v1/match/batch       {"texts": ["...", "..."], "topk": 1}
GET  /v1/openapi.json      机器可读的接口描述

设计约束
--------
* Engine 初始化后只读，多线程并发安全，因此用 ThreadingHTTPServer。
* 索引只建在单句上，查询时动态合并跨句窗口——批量和并发都不会放大内存。
* 所有错误都返回 JSON（含 4xx/5xx），调用方不必处理 HTML 错误页。
"""
import json, os, sys, time, signal, argparse, threading, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Engine
import quotes as Q
import article

ENGINE = None
CFG = {
    "token": None,          # 非空则校验 Authorization: Bearer
    "max_batch": 500,       # 单次批量上限
    "max_body": 8 << 20,    # 请求体上限 8 MB
    "log_fp": None,
}
LOG_LOCK = threading.Lock()


def log(msg):
    line = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    with LOG_LOCK:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()
        if CFG["log_fp"]:
            CFG["log_fp"].write(line + "\n")
            CFG["log_fp"].flush()


class Handler(BaseHTTPRequestHandler):
    server_version = "marxref/1.1"
    protocol_version = "HTTP/1.1"          # 支持长连接，批量调用省掉重复握手

    # ---------- 基础 ----------
    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = obj.encode("utf-8") if isinstance(obj, str) else \
            json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg, **extra):
        self._send(code, {"error": msg, **extra})

    def _authed(self):
        if not CFG["token"]:
            return True
        h = self.headers.get("Authorization") or ""
        return h == "Bearer " + CFG["token"] or h == CFG["token"]

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > CFG["max_body"]:
            raise ValueError(f"body too large ({n} > {CFG['max_body']})")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def log_message(self, fmt, *args):            # 屏蔽默认逐请求日志，自己记
        pass

    def _enter(self):
        self._t0 = time.time()
        self._status = 500

    def _done(self):
        ms = (time.time() - self._t0) * 1000
        log(f"{self.command} {self.path.split('?')[0]} {self._status} {ms:.0f}ms")

    # ---------- 路由 ----------
    def do_OPTIONS(self):
        self._enter()
        self._send(204, b"")
        self._status = 204
        self._done()

    def do_GET(self):
        self._enter()
        path, _, qs = self.path.partition("?")
        params = {}
        for kv in qs.split("&"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k] = v
        try:
            if path == "/healthz":
                self._status = 200
                self._send(200, {"ok": True, "sentences": len(ENGINE.units),
                                 "volumes": ENGINE.volumes, "uptime_s": int(time.time() - START)})
            elif path == "/v1/meta":
                self._status = 200
                self._send(200, ENGINE.meta())
            elif path == "/v1/openapi.json":
                self._status = 200
                self._send(200, SPEC)
            elif path in ("/", "/index.html"):
                self._status = 200
                self._send(200, INDEX_HTML, "text/html; charset=utf-8")
            elif path == "/v1/match":
                if not self._authed():
                    self._status = 401
                    return self._err(401, "unauthorized")
                q = params.get("q") or ""
                if not q.strip():
                    self._status = 400
                    return self._err(400, "missing 'q'")
                res = ENGINE.match(q.strip(), topk=int(params.get("topk", 3)))
                self._status = 200
                self._send(200, {"query": q, "count": len(res), "matches": res})
            else:
                self._status = 404
                self._err(404, "not found", paths=PATHS)
        except Exception:
            self._status = 500
            log("GET 异常 " + traceback.format_exc())
            self._err(500, "internal error")
        finally:
            self._done()

    def do_POST(self):
        self._enter()
        path = self.path.split("?")[0]
        try:
            if not self._authed():
                self._status = 401
                return self._err(401, "unauthorized")
            try:
                req = self._body()
            except Exception as e:
                self._status = 400
                return self._err(400, f"bad json: {e}")

            if path == "/v1/match":
                text = (req.get("text") or "").strip()
                if not text:
                    self._status = 400
                    return self._err(400, "missing 'text'")
                res = ENGINE.match(text, topk=int(req.get("topk", 3)),
                                   volumes=req.get("volumes"),
                                   min_score=float(req.get("min_score", 0.12)))
                self._status = 200
                self._send(200, {"query": text, "count": len(res), "matches": res})

            elif path == "/v1/quotes":
                md = req.get("markdown") or ""
                if not md.strip():
                    self._status = 400
                    return self._err(400, "missing 'markdown'")
                found = Q.extract(md)
                self._status = 200
                self._send(200, {"count": len(found),
                                 "quotes": [{"line": c["line"], "kind": c["kind"],
                                             "text": c["text"], "citation": c["citation"]}
                                            for c in found]})

            elif path == "/v1/article":
                md = req.get("markdown") or ""
                if not md.strip():
                    self._status = 400
                    return self._err(400, "missing 'markdown'")
                mode = req.get("mode") or "annotate"
                if mode not in ("annotate", "replace"):
                    self._status = 400
                    return self._err(400, "'mode' must be annotate or replace")
                out, items, stats = article.process(
                    md, ENGINE, mode=mode,
                    min_ok=float(req.get("min_ok", 0.80)),
                    min_hit=float(req.get("min_hit", 0.55)))
                self._status = 200
                self._send(200, {"stats": stats, "annotated": out,
                                 "items": [{k: v for k, v in it.items() if k != "edit"}
                                           for it in items]})

            elif path == "/v1/match/batch":
                texts = req.get("texts")
                if not isinstance(texts, list):
                    self._status = 400
                    return self._err(400, "'texts' must be a list")
                if len(texts) > CFG["max_batch"]:
                    self._status = 413
                    return self._err(413, f"too many texts ({len(texts)} > {CFG['max_batch']})",
                                     hint="分批提交，或启动时调大 --max-batch")
                topk = int(req.get("topk", 1))
                vols = req.get("volumes")
                out = []
                for t in texts:
                    t = (t or "").strip()
                    out.append({"query": t,
                                "matches": ENGINE.match(t, topk=topk, volumes=vols)
                                if t else []})
                self._status = 200
                self._send(200, {"count": len(out), "results": out})
            else:
                self._status = 404
                self._err(404, "not found", paths=PATHS)
        except Exception:
            self._status = 500
            log("POST 异常 " + traceback.format_exc())
            self._err(500, "internal error")
        finally:
            self._done()


PATHS = ["/healthz", "/v1/meta", "/v1/match", "/v1/match/batch",
         "/v1/quotes", "/v1/article", "/v1/openapi.json"]

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Marx Reference Locator", "version": "1.1",
             "description": "英文引文 → 《马克思恩格斯文集》中文译文、章次与页码。"
                            "返回的 zh 是候选译文，unaligned/numeric 两个字段用于判断结果是否可疑。"},
    "paths": {
        "/healthz": {"get": {"summary": "健康检查"}},
        "/v1/meta": {"get": {"summary": "卷与句数元数据"}},
        "/v1/match": {
            "get": {"summary": "单条引文定位（查询串）",
                    "parameters": [{"name": "q", "in": "query", "required": True,
                                    "schema": {"type": "string"}},
                                   {"name": "topk", "in": "query", "schema": {"type": "integer"}}]},
            "post": {"summary": "单条引文定位",
                     "requestBody": {"content": {"application/json": {"schema": {
                         "type": "object",
                         "properties": {"text": {"type": "string"},
                                        "topk": {"type": "integer", "default": 3},
                                        "volumes": {"type": "array", "items": {"type": "integer"}},
                                        "min_score": {"type": "number", "default": 0.12}},
                         "required": ["text"]}}}}}},
        "/v1/quotes": {"post": {"summary": "只抽取 Markdown 里的英文引文，不做匹配",
                                "requestBody": {"content": {"application/json": {"schema": {
                                    "type": "object", "properties": {"markdown": {"type": "string"}},
                                    "required": ["markdown"]}}}}}},
        "/v1/article": {"post": {"summary": "整篇 Markdown：抽取 → 匹配 → 回填中文与出处",
                                 "requestBody": {"content": {"application/json": {"schema": {
                                     "type": "object",
                                     "properties": {"markdown": {"type": "string"},
                                                    "mode": {"type": "string",
                                                             "enum": ["annotate", "replace"],
                                                             "default": "annotate"},
                                                    "min_ok": {"type": "number", "default": 0.8},
                                                    "min_hit": {"type": "number", "default": 0.55}},
                                     "required": ["markdown"]}}}}}},
        "/v1/match/batch": {"post": {"summary": "批量引文定位",
                                     "requestBody": {"content": {"application/json": {"schema": {
                                         "type": "object",
                                         "properties": {"texts": {"type": "array", "items": {"type": "string"}},
                                                        "topk": {"type": "integer", "default": 1},
                                                        "volumes": {"type": "array", "items": {"type": "integer"}}},
                                         "required": ["texts"]}}}}}},
    },
    "components": {"schemas": {"Match": {"type": "object", "properties": {
        "score": {"type": "number", "description": "英文侧相似度，0—1"},
        "coverage": {"type": "number"}, "ngram": {"type": "number"},
        "vol": {"type": "integer"}, "chapter": {"type": "string"},
        "page": {"type": "integer", "nullable": True, "description": "印刷页码，null 表示待核"},
        "en": {"type": "string"}, "zh": {"type": "string", "description": "候选中文译文"},
        "unaligned": {"type": "boolean", "description": "true 表示该句没配上中文，zh 与 page 都不可信"},
        "numeric": {"type": "string", "enum": ["ok", "mismatch", "n/a"],
                    "description": "引文数字与中文句是否一致，mismatch 多半是配错了段"},
        "warn": {"type": "string", "description": "可直接展示给用户的提示"},
    }}}},
}

INDEX_HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Marx 引文定位 · 服务在线</title><style>
body{font:14px/1.7 system-ui,"Segoe UI",sans-serif;max-width:720px;margin:48px auto;padding:0 24px;color:#222}
code,pre{background:#f5f3ee;border-radius:5px}code{padding:2px 5px}
pre{padding:14px 16px;overflow:auto;font-size:12.5px;line-height:1.6}
h1{font-size:19px}h2{font-size:14px;margin-top:26px;color:#555}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#2e9e5b;margin-right:6px}
</style></head><body>
<h1><span class="dot"></span>Marx 引文定位 · 服务在线</h1>
<p>输入英文引文，返回《马克思恩格斯文集》中的中文译文、章次与页码。本页仅用于确认服务状态，前端请在别处实现。</p>
<h2>单条</h2>
<pre>POST /v1/match
{"text":"Force is the midwife of every old society pregnant with a new one.","topk":3}</pre>
<h2>批量</h2>
<pre>POST /v1/match/batch
{"texts":["...","..."],"topk":1}</pre>
<h2>整篇 Markdown（主要用法）</h2>
<pre>POST /v1/article
{"markdown":"# 标题\n\n...\"a quote\"...","mode":"annotate"}</pre>
<p style="color:#666">返回 <code>annotated</code>（回填好的 Markdown）与 <code>items</code>（逐条核对信息）。</p>
<h2>元数据 / 健康</h2>
<pre>GET /v1/meta      GET /healthz      GET /v1/openapi.json</pre>
<p style="color:#666;margin-top:30px">返回中的 <code>unaligned</code>、<code>numeric</code> 是判断结果是否可疑的唯二自动信号，请务必展示给用户。</p>
</body></html>"""

START = time.time()


def main():
    global ENGINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("MARXREF_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MARXREF_PORT", 8080)))
    ap.add_argument("--token", default=os.environ.get("MARXREF_TOKEN"),
                    help="非空则要求 Authorization: Bearer <token>")
    ap.add_argument("--max-batch", type=int, default=int(os.environ.get("MARXREF_MAX_BATCH", 500)))
    ap.add_argument("--corpus", default=os.environ.get("MARXREF_CORPUS"),
                    help="语料目录，默认与本文件同级的 corpus/")
    ap.add_argument("--log", default=os.environ.get("MARXREF_LOG"),
                    help="日志文件路径，默认只输出到 stderr")
    ap.add_argument("--pid", default=None, help="写入 PID 文件，便于 stop 脚本结束进程")
    args = ap.parse_args()

    CFG["token"] = args.token
    CFG["max_batch"] = args.max_batch
    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)) or ".", exist_ok=True)
        CFG["log_fp"] = open(args.log, "a", encoding="utf-8")

    t0 = time.time()
    ENGINE = Engine(corpus_dir=args.corpus)
    log(f"索引加载完成 {len(ENGINE.units)} 句，卷 {ENGINE.volumes}，耗时 {time.time()-t0:.1f}s")

    if args.pid:
        with open(args.pid, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        log(f"pid {os.getpid()} → {args.pid}")

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    log(f"服务启动 http://{args.host}:{args.port}  token={'on' if args.token else 'off'}  "
        f"max_batch={args.max_batch}")

    def _stop(signum, frame):
        log(f"收到信号 {signum}，正在停止…")
        threading.Thread(target=srv.shutdown, daemon=True).start()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _stop)
        except (ValueError, AttributeError):
            pass

    try:
        srv.serve_forever()
    finally:
        srv.server_close()
        log("已停止")


if __name__ == "__main__":
    main()
