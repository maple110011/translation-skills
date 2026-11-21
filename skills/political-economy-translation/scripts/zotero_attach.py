#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把译文 PDF 挂回 Zotero 父条目，作为子附件。

多数文献是从 Zotero 文献库里拖出来的。译文 PDF 出完、验收通过后应该回到那个
条目下面，而不是散落在工作区。

**走本地 API，不走 zotero.org。** Zotero 7+ 的本地 API 读不需要认证；Zotero 10+
还支持写入与文件上传，只需要用户在弹窗里授权一次（选 Always Allow 可长期复用）。
因此本脚本不依赖 ``pyzotero``、不需要 zotero.org API key，也不碰 ``zotero.sqlite``。

流程分五步，顺序不能颠倒：

1. **线索解析**——front matter 的 ``source_pdf`` / ``doi`` / ``arxiv`` / ``title``，
   原文文件名，译文文件名。``citekey`` 只作关键词，**不当 DOI**（旧版把译文
   citekey 塞进 DOI 参数，搜出来必然是噪声）。
2. **锚定**——本地 API 只读查父条目。``source_pdf`` 能精确命中 Zotero 里那条附件
   的文件名，是最硬的证据；其次是 DOI／arXiv 等值；最后才是标题相似度。
   歧义时输出候选，**不写库**。
3. **判重**——按 ``filename`` + ``md5`` 判定 new / unchanged / update。
   旧版只看文件名，同名就跳过，导致改稿重出的 PDF 永远挂不上新版。
4. **授权与上传**——``POST /api/local/authorize`` 拿 key，三步上传（建条目 →
   传文件 → 注册），失败回滚删掉空壳附件。
5. **复验与记账**——读回子项核 md5，写单篇 ``zotero_attach.json`` 与总账 CSV。

用法::

    python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md
    python scripts/zotero_attach.py <stem>_zh.pdf --parent-key ABCD1234
    python scripts/zotero_attach.py --batch ../交付目录 --strict
    python scripts/zotero_attach.py <stem>_zh.pdf --prepare-only   # 只锚定，不写库
    python scripts/zotero_attach.py <stem>_zh.pdf --dry-run        # 只读，不产文件

退出码：0 全挂上；1 硬错误；2 有待挂（需人工）；3 锚定歧义（需人选）。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

LOCAL_BASE = "http://127.0.0.1:23119/api"
LOCAL_ORIGIN = "http://127.0.0.1:23119"
CONFIG_DEFAULT = pathlib.Path(os.environ.get("ZOTERO_CONFIG")
                              or (pathlib.Path.home() / ".workbuddy" / "zotero.json"))
APP_NAME = "translation-skills (zotero_attach)"
SKIP_DIRS = {"_work", "_dist", "_zotero", "node_modules", ".git", "__pycache__"}

EXIT_OK, EXIT_ERR, EXIT_PENDING, EXIT_AMBIG = 0, 1, 2, 3
TITLE_MIN = 0.85
TITLE_GAP = 0.08


class LocalUnavailable(RuntimeError):
    """Zotero 本地 API 连不上（没启动、没开开关、版本太低）。"""


# ---------------------------------------------------------------- 小工具

def _opener():
    """绕开系统代理：Windows 上 http_proxy 会把 localhost 请求也劫走。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


_OPEN = _opener()


def http(method, url, body=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with _OPEN.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise LocalUnavailable(
            "连不上 Zotero 本地 API（%s）。确认 Zotero 已启动，且「设置 → 高级」里"
            "勾了「允许此计算机上的其他应用程序与 Zotero 通信」。"
            % getattr(e, "reason", e))


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_text(s):
    """归一化：NFKC、小写、去冠词、去标点、压空白。中英文都适用。"""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"^(a|an|the)\s+", "", s.strip())
    s = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_ratio(a, b):
    """标题相似度。副标题差异不该把命中拉低，所以主标题单独比一次取大。"""
    na, nb = norm_text(a), norm_text(b)
    if not na or not nb:
        return 0.0
    best = difflib.SequenceMatcher(None, na, nb).ratio()
    main_a, main_b = na.split(":")[0].strip(), nb.split(":")[0].strip()
    if len(main_a) >= 12 and len(main_b) >= 12:
        best = max(best, difflib.SequenceMatcher(None, main_a, main_b).ratio())
    return best


def norm_doi(s):
    s = (s or "").strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", s).strip()


def read_frontmatter(md):
    """取 front matter 里能当锚的字段。BOM／CRLF 都要兼容。"""
    out = {}
    if not md or not pathlib.Path(md).is_file():
        return out
    text = pathlib.Path(md).read_text(encoding="utf-8-sig", errors="ignore")
    m = re.match(r"---\s*\r?\n(.*?)\r?\n---\s*\r?\n", text, re.S)
    if not m:
        return out
    keep = ("title", "title_en", "title_zh", "doi", "arxiv", "citekey",
            "year", "journal", "venue", "source_pdf", "source_file")
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t", "-")):
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        k, v = k.strip().lower(), v.strip().strip('"').strip("'")
        if k in keep and v and v.lower() not in ("null", "~"):
            out[k] = v
    return out


def stem_of(pdf):
    """``Hollmann2022_zh.pdf`` → ``Hollmann2022``。"""
    s = pathlib.Path(pdf).stem
    return s[:-3] if s.endswith("_zh") else s


NAME_PREFIX = "zh - "


def attach_name(pdf, fm, prefix=NAME_PREFIX, kids=None):
    """Zotero 里那个附件的文件名：沿用原文附件那套命名，最前面标 zh。

    原文附件多半是 Zotero 自己按「作者 et al. - 年 - 题名」命名的，直接拿它的
    文件名加前缀，附件列表里原文和译文就挨着排、一眼对得上。没有 ``source_pdf``
    时退回 ``<stem>_zh.pdf`` 的 stem。
    """
    base = ""
    pfx_low = (prefix or "").strip().lower()
    # 自己挂过的中译要排除：新命名以 zh 开头，旧命名是 <stem>_zh.pdf。
    self_names = {pathlib.Path(pdf).name.lower(), (stem_of(pdf) + "_zh.pdf").lower()}
    for c in (kids or []):
        d = c.get("data", {})
        fn = d.get("filename") or ""
        low = fn.lower()
        if not low.endswith(".pdf") or d.get("contentType") != "application/pdf":
            continue
        if (pfx_low and low.startswith(pfx_low)) or low in self_names:
            continue
        base = pathlib.Path(fn).stem
        break
    src = (fm or {}).get("source_pdf") or ""
    if not base:
        base = pathlib.Path(src).stem if src else stem_of(pdf)
    pfx = prefix or ""
    if pfx and base.lower().startswith(pfx.strip().lower()):
        base = base[len(pfx.strip()):].lstrip(" -")
    name = "%s%s.pdf" % (pfx, base)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    if len(name) > 180:                       # Zotero storage 路径 + Windows 260 字符上限
        name = name[:176].rstrip(" .") + ".pdf"
    return name


def guess_md(pdf):
    p = pathlib.Path(pdf)
    for name in (stem_of(p) + "_zh.md", stem_of(p) + ".md"):
        cand = p.with_name(name)
        if cand.is_file():
            return cand
    return None


def source_md(pdf):
    p = pathlib.Path(pdf)
    for name in (stem_of(p) + "_原文.md", stem_of(p) + "_src.md"):
        cand = p.with_name(name)
        if cand.is_file():
            return cand
    return None


def extract_ident(text):
    """从原文 Markdown 里捞 DOI / arXiv 号。"""
    out = []
    for m in re.finditer(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text or ""):
        out.append(m.group(1).rstrip(".,;)"))
    for m in re.finditer(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", text or "", re.I):
        out.append("10.48550/arXiv." + m.group(1))
    return list(dict.fromkeys(out))


def drag_title(path):
    """Zotero 拖出的文件名通常是「作者 - 年份 - 题名.pdf」。"""
    stem = pathlib.Path(path).stem
    m = re.match(r"^.+?\s+-\s+(\d{4})\s+-\s+(.+)$", stem)
    return (m.group(2).strip(), m.group(1)) if m else ("", "")


# ---------------------------------------------------------------- 本地 API

class Local:
    def __init__(self, user_id="0"):
        self.base = LOCAL_BASE
        self.user = str(user_id or "0")
        self.server_id = ""
        self.key = ""
        self.remember = None

    def _url(self, path):
        return self.base + path

    def _u(self, path):
        return "/users/%s%s" % (self.user, path)

    def call(self, method, path, body=None, headers=None, auth=False, timeout=60):
        h = {"Zotero-API-Version": "3"}
        if self.server_id:
            h["Zotero-Server-ID"] = self.server_id
        if auth:
            if not self.key:
                raise RuntimeError("没拿到本地 API key")
            h["Zotero-API-Key"] = self.key
        payload = None
        if isinstance(body, (dict, list)):
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            h["Content-Type"] = "application/json"
        elif body is not None:
            payload = body
        h.update(headers or {})
        st, hd, raw = http(method, self._url(path), payload, h, timeout=timeout)
        sid = hd.get("Zotero-Server-ID")
        if sid and not self.server_id:
            self.server_id = sid
        return st, hd, raw

    def probe(self):
        """探活并取 server id。返回 False 表示本地 API 不可用。"""
        try:
            st, hd, _ = self.call("GET", "/", timeout=8)
        except (SystemExit, LocalUnavailable):
            return False
        if st != 200:
            return False
        self.server_id = hd.get("Zotero-Server-ID") or self.server_id
        return bool(self.server_id)

    def search(self, q, limit=25, everywhere=False):
        params = {"q": q, "limit": str(limit), "format": "json"}
        if everywhere:
            params["qmode"] = "everything"
        st, _, raw = self.call("GET", self._u("/items?" + urllib.parse.urlencode(params)))
        if st != 200:
            return []
        try:
            return json.loads(raw)
        except ValueError:
            return []

    def item(self, key):
        st, _, raw = self.call("GET", self._u("/items/" + key))
        if st != 200:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def children(self, key):
        st, _, raw = self.call("GET", self._u("/items/%s/children" % key))
        if st != 200:
            return []
        try:
            return json.loads(raw)
        except ValueError:
            return []

    def authorize(self, app_name=APP_NAME, timeout=180):
        """申请本地写权限。用户点 Always Allow 时 key 可长期复用。"""
        st, _, raw = self.call("POST", "/local/authorize", {"appName": app_name},
                               timeout=timeout)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        if st == 200 and data.get("key"):
            self.key = data["key"]
            self.remember = bool(data.get("remember"))
            return True, ""
        if st == 403:
            return False, "用户在 Zotero 弹窗里拒绝了授权"
        if st == 429:
            return False, "授权弹窗请求过频（每分钟最多 5 次），稍等再试"
        if st == 428:
            return False, "缺 Zotero-Server-ID（旧版 Zotero 不支持本地写入）"
        return False, "授权失败：HTTP %s %s" % (st, raw[:200].decode("utf-8", "replace"))


# ---------------------------------------------------------------- 锚定

class Anchor:
    def __init__(self, key, title, via, score=1.0, candidates=None):
        self.key = key
        self.title = title
        self.via = via
        self.score = score
        self.candidates = candidates or []

    @property
    def uri(self):
        return "zotero://select/library/items/" + self.key


def _match_source_pdf(api, source_pdf):
    """source_pdf 是 Zotero 里那条附件的真实文件名，命中就等于 100% 确认父条目。"""
    name = unicodedata.normalize("NFKC", pathlib.Path(source_pdf).name).lower()
    probe = pathlib.Path(source_pdf).stem
    m = re.match(r"^.+?\s+-\s+\d{4}\s+-\s+(.+)$", probe)
    if m:
        probe = m.group(1)
    for q in dict.fromkeys([probe, pathlib.Path(source_pdf).stem]):
        if not q:
            continue
        for it in api.search(q, limit=40, everywhere=True):
            d = it.get("data", {})
            if d.get("itemType") != "attachment":
                continue
            if unicodedata.normalize("NFKC", d.get("filename") or "").lower() != name:
                continue
            parent = d.get("parentItem")
            if not parent:
                continue
            p = api.item(parent)
            return parent, (p or {}).get("data", {}).get("title", ""), d.get("key", "")
    return None


def resolve(api, args, fm, pdf):
    """按可靠性从高到低试线索。返回 (Anchor|None, candidates)。"""
    if args.parent_key:
        d = api.item(args.parent_key)
        if d and d.get("data"):
            return Anchor(args.parent_key, d["data"].get("title", ""), "parent-key"), []
        raise SystemExit("父条目 %s 在库里取不到（key 错或不在当前库）" % args.parent_key)

    dois = []
    if args.doi:
        dois.append(norm_doi(args.doi))
    if fm.get("doi"):
        dois.append(norm_doi(fm["doi"]))
    if fm.get("arxiv"):
        dois.append(norm_doi("10.48550/arXiv." + fm["arxiv"]))
    src = source_md(pdf)
    if src:
        dois.extend(extract_ident(src.read_text(encoding="utf-8", errors="ignore")))
    for doi in dict.fromkeys(d for d in dois if d):
        for it in api.search(doi, limit=25, everywhere=True):
            d = it.get("data", {})
            if d.get("itemType") in ("attachment", "note"):
                continue
            if norm_doi(d.get("DOI") or "") == doi:
                return Anchor(d["key"], d.get("title", ""), "DOI:%s" % doi), []

    if fm.get("source_pdf"):
        hit = _match_source_pdf(api, fm["source_pdf"])
        if hit:
            return Anchor(hit[0], hit[1], "source_pdf 精确匹配附件"), []

    titles = []
    if args.title:
        titles.append(args.title)
    if fm.get("title_en"):
        titles.append(fm["title_en"])
    if fm.get("title") and re.search(r"[A-Za-z]", fm["title"]):
        titles.append(fm["title"])
    dtitle, _ = drag_title(pdf.name)
    if dtitle:
        titles.append(dtitle)

    pool, seen = [], set()
    for t in dict.fromkeys(x for x in titles if x):
        for everywhere in (False, True):
            got = api.search(t, limit=25, everywhere=everywhere)
            for it in got:
                d = it.get("data", {})
                if d.get("itemType") in ("attachment", "note") or not d.get("title"):
                    continue
                if d.get("key") in seen:
                    continue
                seen.add(d.get("key"))
                pool.append((title_ratio(d["title"], t), d, t))
            if pool:
                break
    pool.sort(key=lambda x: -x[0])
    if pool:
        best = pool[0]
        second = pool[1][0] if len(pool) > 1 else 0.0
        cands = [(d["key"], d.get("title", ""), round(r, 3)) for r, d, _ in pool[:3] if r >= 0.5]
        if best[0] >= TITLE_MIN and (len(pool) == 1 or best[0] - second >= TITLE_GAP):
            return Anchor(best[1]["key"], best[1].get("title", ""), "标题:%s" % best[2], best[0]), cands
        return None, cands
    return None, []


# ---------------------------------------------------------------- 判重 / 上传

def attachment_children(api, parent_key):
    return [c for c in api.children(parent_key)
            if c.get("data", {}).get("itemType") == "attachment"]


def plan(kids, pdf, want_name):
    """返回 (mode, existing_attachment, md5, legacy)。mode ∈ new / unchanged / update。"""
    md5 = md5_of(pdf)
    same = [c for c in kids if (c["data"].get("filename") or "") == want_name]
    # 旧版把附件存成「<stem>_zh.pdf」。库里出现这种名字就说明是本脚本以前挂的，
    # 换成新命名时要一并清掉，否则同一个条目下会挂着两份中译。
    legacy = [c for c in kids
              if (c["data"].get("filename") or "") == pathlib.Path(pdf).name
              and (c["data"].get("filename") or "") != want_name]
    if not same:
        return "new", None, md5, legacy
    old = same[0]
    if (old["data"].get("md5") or "").lower() == md5:
        return "unchanged", old, md5, legacy
    return "update", old, md5, legacy


def create_attachment(api, parent_key, filename, title=""):
    payload = [{
        "itemType": "attachment",
        "linkMode": "imported_file",
        "parentItem": parent_key,
        "title": title or pathlib.Path(filename).stem,
        "contentType": "application/pdf",
        "filename": filename,
    }]
    st, _, raw = api.call("POST", api._u("/items"), payload,
                          headers={"Zotero-Write-Token": os.urandom(16).hex()}, auth=True)
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    if st not in (200, 201):
        raise RuntimeError("建附件条目失败：HTTP %s %s" % (st, raw[:200].decode("utf-8", "replace")))
    for bucket in ("success", "successful"):
        got = data.get(bucket) or {}
        if isinstance(got, dict) and got.get("0"):
            v = got["0"]
            return v.get("key") if isinstance(v, dict) else str(v)
    raise RuntimeError("建附件条目被拒：%s" % (data.get("failed") or data.get("failure"),))


def upload_file(api, att_key, pdf, md5, old_md5=None, fname=None):
    """三步上传。old_md5 有值时覆盖（If-Match），否则新建（If-None-Match: *）。

    三个坑都在这一步，全是实测踩出来的：
    * 参数必须放在 **form body** 里。按官方文档写成 query string，Zotero 10.0.8
      的本地实现直接 500（Web API 那边认 query，本地不认）。
    * 必须带 ``Content-Type: application/x-www-form-urlencoded``，否则 400。
    * 覆盖时 ``If-Match`` 要填**旧文件的 md5**（文件 ETag），填条目 version 会
      400 ``Invalid If-Match header``。
    """
    p = pathlib.Path(pdf)
    fname = fname or p.name
    stat = p.stat()
    fields = urllib.parse.urlencode({
        "md5": md5,
        "filename": fname,
        "filesize": stat.st_size,
        "mtime": int(stat.st_mtime * 1000),
    }).encode("utf-8")
    cond = {"If-Match": old_md5} if old_md5 else {"If-None-Match": "*"}
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    st, _, raw = api.call("POST", api._u("/items/%s/file" % att_key),
                          body=fields, headers={**form, **cond}, auth=True)
    if st == 401:
        raise PermissionError("写请求被拒（401），本地 key 失效")
    if st not in (200, 201):
        raise RuntimeError("申请上传位失败：HTTP %s %s" % (st, raw[:200].decode("utf-8", "replace")))
    try:
        info = json.loads(raw) if raw else {}
    except ValueError:
        info = {}
    if info.get("exists"):
        return "exists"
    url = info.get("url") or ""
    upload_key = info.get("uploadKey") or ""
    if not url or not upload_key:
        raise RuntimeError("上传位响应缺 url/uploadKey：%s" % (info,))
    # Zotero 回的 url 可能写 localhost；Windows 上 localhost 会先试 ::1 再回退，慢 2 秒。
    if url.startswith("http"):
        target = re.sub(r"^http://localhost(?=[:/])", "http://127.0.0.1", url)
    else:
        target = LOCAL_ORIGIN + url
    with open(p, "rb") as fh:
        st2, _, raw2 = http("POST", target, fh.read(),
                            {"Content-Type": info.get("contentType") or "application/pdf"})
    if st2 not in (200, 201, 204):
        raise RuntimeError("上传文件失败：HTTP %s %s" % (st2, raw2[:200].decode("utf-8", "replace")))
    st3, _, raw3 = api.call("POST", api._u("/items/%s/file" % att_key),
                            body=urllib.parse.urlencode({"upload": upload_key}).encode("utf-8"),
                            headers={**form, **cond}, auth=True)
    if st3 not in (200, 204):
        raise RuntimeError("注册附件失败：HTTP %s %s" % (st3, raw3[:200].decode("utf-8", "replace")))
    return "uploaded"


def delete_item(api, key):
    d = api.item(key)
    ver = (d or {}).get("version") or (d or {}).get("data", {}).get("version")
    hd = {"If-Unmodified-Since-Version": str(ver)} if ver else {}
    st, _, _ = api.call("DELETE", api._u("/items/" + key), headers=hd, auth=True)
    return st in (200, 204)


def verify(api, parent_key, fname, md5):
    for c in api.children(parent_key):
        d = c.get("data", {})
        if d.get("itemType") == "attachment" and (d.get("filename") or "") == fname:
            return d.get("key", ""), (d.get("md5") or "").lower() == md5
    return "", False


# ---------------------------------------------------------------- 记账 / 降级

def write_manifest(pdf, r):
    mf = pathlib.Path(pdf).parent / "_work" / "zotero_attach.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "pdf": str(pdf), "md5": r.get("md5", ""), "status": r["status"],
        "mode": r.get("mode", ""), "via": r.get("via", ""), "score": r.get("score", 0),
        "parent_key": r.get("parent_key", ""), "parent_title": r.get("parent_title", ""),
        "attachment_key": r.get("attachment_key", ""),
        "zotero_filename": r.get("zotero_filename", ""),
        "zotero_uri": ("zotero://select/library/items/" + r["parent_key"]) if r.get("parent_key") else "",
        "note": r.get("note", ""),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return mf


LEDGER_HEAD = ["time", "stem", "pdf", "md5", "parent_key", "parent_title",
               "attachment_key", "zotero_filename", "status", "skill"]


def ledger_upsert(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.is_file():
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    rows = [r for r in rows if (r.get("stem") or "") != row["stem"]]
    rows.append(row)
    rows.sort(key=lambda r: r.get("time") or "")
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_HEAD)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in LEDGER_HEAD})


def emit_pending(entries, zdir):
    """降级产物：一份汇总表 + 一段可粘进 Zotero 的 JS。一次交付只一份。"""
    zdir.mkdir(parents=True, exist_ok=True)
    md = ["# Zotero 待挂清单", "",
          "生成时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
          "已锚定的直接用同目录 `attach.js`：Zotero → 工具 → 开发者 → 运行 JavaScript，"
          "整段粘贴后 Run，一次挂完。未锚定的需先在 Zotero 里选定条目（给 `--parent-key` 重跑）。", "",
          "| 稿子 | PDF | 父条目 | 标题 | 状态 |", "|---|---|---|---|---|"]
    for e in entries:
        md.append("| %s | %s | %s | %s | %s |" % (
            e.get("stem", ""), e.get("pdf", ""), e.get("parent_key", "") or "—",
            (e.get("parent_title") or "")[:48], e.get("status", "")))
    md.append("")
    rows = ["  { pdf: %s, parent: %s }," % (json.dumps(e["pdf"], ensure_ascii=False),
                                            json.dumps(e["parent_key"]))
            for e in entries if e.get("parent_key")]
    hint = ("// 由 zotero_attach.py 生成：把译文 PDF 挂到已锚定的父条目下"
            if rows else
            "// 本批次没有已锚定的条目（多半是 Zotero 没启动）。启动 Zotero 后重跑本脚本再粘这段。")
    js = "\n".join([
        hint,
        "const jobs = [", *rows, "];",
        "let ok = 0; const fail = [];",
        "for (const j of jobs) {",
        "  try {",
        "    const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, j.parent);",
        "    if (!item) { fail.push(j.pdf + '：库里没有父条目 ' + j.parent); continue; }",
        "    const att = await Zotero.Attachments.importFromFile({ file: j.pdf, parentItemID: item.id });",
        "    ok++; Zotero.debug('attached ' + att.key);",
        "  } catch (e) { fail.push(j.pdf + '：' + e); }",
        "}",
        "return '已挂 ' + ok + ' 个；失败 ' + fail.length + (fail.length ? '\\n' + fail.join('\\n') : '');",
        "",
    ])
    (zdir / "pending.md").write_text("\n".join(md), encoding="utf-8")
    js_path = zdir / "attach.js"
    js_path.write_text(js, encoding="utf-8")
    return zdir / "pending.md", js_path


# ---------------------------------------------------------------- 单篇

def ensure_auth(api, cfg, args):
    """有缓存 key 直接用；server 变了或没有就授权一次。"""
    if cfg.get("local_key") and cfg.get("server_id") == api.server_id:
        api.key = cfg["local_key"]
        return True, ""
    if cfg.get("local_key") and cfg.get("server_id"):
        print("  配置里的 server_id 与当前库不一致（换过库），重新授权。")
    print("  → Zotero 会弹窗问是否允许写入，请点「Always Allow」（以后不再问）。")
    ok, why = api.authorize()
    if not ok:
        return False, why
    if api.remember:
        cfg["local_key"] = api.key
        cfg["server_id"] = api.server_id
        cfg["user_id"] = api.user
        save_config(args.config, cfg)
        print("  授权 → 已记住，写入 %s" % (pathlib.Path(args.config) if args.config else CONFIG_DEFAULT))
    else:
        print("  授权 → 只给了单次 key（下次还得点）")
        cfg["local_key"] = ""
    return True, ""


def source_report(pdf, md, fm, anchor, cands, api):
    """回答一个问题：这篇是不是从 Zotero 库里拖出来的。只读，不写库、不弹窗。

    交付时先问这个，比先挂后翻账省事：不在库里就不必折腾授权，
    在库里就顺手把父条目 key 记下来，下次改稿直接 --parent-key。
    """
    print("  ── 来源判定 ──")
    if not anchor:
        if cands:
            print("  状态：库里有多条候选，需要人选（%d 条）" % len(cands))
            for k, t, r in cands:
                print("    %s  %.3f  %s" % (k, r, t[:70]))
        else:
            print("  状态：不在库里")
            tried = []
            if fm.get("doi"):
                tried.append("DOI %s" % fm["doi"])
            if fm.get("source_pdf"):
                tried.append("原文文件名 %s" % pathlib.Path(fm["source_pdf"]).name)
            if fm.get("title"):
                tried.append("英文标题")
            print("  查过：%s" % ("、".join(tried) or "（front matter 里没有可用的锚）"))
            print("  结论：PDF 照常交付，不挂 Zotero。")
        return
    print("  状态：在库里")
    print("  条目：%s" % anchor.key)
    print("  标题：%s" % anchor.title)
    print("  依据：%s（%.2f）" % (anchor.via, anchor.score))
    print("  打开：%s" % anchor.uri)
    kids = attachment_children(api, anchor.key)
    pfx = (NAME_PREFIX or "").strip().lower()
    src = None
    for c in kids:
        d = c.get("data", {})
        fn = (d.get("filename") or "")
        if not fn.lower().endswith(".pdf"):
            continue
        if pfx and fn.lower().startswith(pfx):
            continue
        src = d
        break
    if src:
        print("  原文附件：%s（%s）" % (src.get("filename"), src.get("key")))
    elif fm.get("source_pdf"):
        print("  原文附件：库里没有；front matter 记的是 %s"
              % pathlib.Path(fm["source_pdf"]).name)
    else:
        print("  原文附件：库里只有条目，没有原文 PDF")


def run_one(pdf, args, api, cfg):
    pdf = pathlib.Path(pdf).resolve()
    md = pathlib.Path(args.md) if args.md else guess_md(pdf)
    fm = read_frontmatter(md)
    md5 = md5_of(pdf)
    base = {"stem": stem_of(pdf), "pdf": str(pdf), "md5": md5}

    print("译文 PDF：%s（%s 字节）" % (pdf, format(pdf.stat().st_size, ",")))
    if md:
        print("  元信息 → %s" % pathlib.Path(md).name)
    try:
        anchor, cands = resolve(api, args, fm, pdf)
    except LocalUnavailable as e:
        print("  锚定 → 本地 API 不可用：%s" % e)
        if args.detect:
            print("  ── 来源判定 ──")
            print("  状态：查不了。先启动 Zotero，并在「设置 → 高级」勾上"
                  "「允许此计算机上的其他应用程序与 Zotero 通信」，再重跑 --detect。")
        return {**base, "status": "pending", "rc": EXIT_PENDING, "note": str(e)}

    if not anchor:
        if cands:
            print("  锚定 → 歧义，候选 %d 条：" % len(cands))
            for k, t, r in cands:
                print("    %s  %.3f  %s" % (k, r, t[:70]))
            print("  用 --parent-key <KEY> 指定后重跑。")
            if args.detect:
                source_report(pdf, md, fm, None, cands, api)
            return {**base, "status": "ambiguous", "rc": EXIT_AMBIG, "candidates": cands}
        print("  锚定 → 没找到父条目（给 --parent-key，或补 --title / --doi）")
        if args.detect:
            source_report(pdf, md, fm, None, [], api)
        return {**base, "status": "pending", "rc": EXIT_PENDING}

    print("  锚定 → %s  %s  （%s，%.2f）" % (anchor.key, anchor.title[:64], anchor.via, anchor.score))
    if args.detect:
        source_report(pdf, md, fm, anchor, [], api)
        return {**base, "status": "detected", "rc": EXIT_OK,
                "parent_key": anchor.key, "parent_title": anchor.title,
                "via": anchor.via, "score": round(anchor.score, 3)}
    kids = attachment_children(api, anchor.key)
    want_name = attach_name(pdf, fm, args.name_prefix, kids)
    mode, existing, md5, legacy = plan(kids, pdf, want_name)
    print("  附件名 → %s" % want_name)
    print("  判重 → %s（%s）" % (mode, {"new": "新建", "unchanged": "已是最新", "update": "覆盖旧版"}[mode]))
    got = {**base, "md5": md5, "parent_key": anchor.key, "parent_title": anchor.title,
           "via": anchor.via, "score": round(anchor.score, 3), "mode": mode,
           "zotero_filename": want_name}

    if mode == "unchanged" and not legacy:
        print("  跳过上传：库里这份就是当前版本。")
        return {**got, "status": "unchanged", "rc": EXIT_OK,
                "attachment_key": existing["data"]["key"]}

    if args.dry_run:
        print("  --dry-run：不写库、不产文件。")
        return {**got, "status": "dry-run", "rc": EXIT_OK,
                "attachment_key": (existing or {}).get("data", {}).get("key", "")}

    if args.prepare_only:
        print("  --prepare-only：只锚定，不写库。")
        return {**got, "status": "prepared", "rc": EXIT_PENDING,
                "attachment_key": (existing or {}).get("data", {}).get("key", "")}

    ok, why = ensure_auth(api, cfg, args)
    if not ok:
        print("  授权 → 失败：%s" % why)
        return {**got, "status": "error", "rc": EXIT_ERR, "note": why}

    for c in legacy:
        old = c["data"]
        if delete_item(api, old["key"]):
            print("  清理旧命名附件 %s（%s）" % (old.get("filename"), old["key"]))
        else:
            print("  [!] 旧命名附件 %s 删不掉，库里会同时留两份" % old.get("filename"))

    if mode == "unchanged":
        print("  跳过上传：库里这份就是当前版本。")
        return {**got, "status": "unchanged", "rc": EXIT_OK,
                "attachment_key": existing["data"]["key"]}

    title = args.attach_title or pathlib.Path(want_name).stem
    created = False
    old_md5 = ""
    if mode == "update":
        att_key = existing["data"]["key"]
        old_md5 = (existing["data"].get("md5") or "").lower()
        if not old_md5:
            # 旧附件没记 md5（早期版本挂的），拿不到 ETag 就无法覆盖，删掉重建。
            print("  上传 → 旧附件无 md5，删除后重建 %s" % att_key)
            if delete_item(api, att_key):
                att_key = create_attachment(api, anchor.key, want_name, title)
                created, mode = True, "new"
            else:
                raise SystemExit("旧附件 %s 删不掉，也无法覆盖；请手工处理后重跑" % att_key)
        else:
            print("  上传 → 覆盖 %s" % att_key)
    else:
        att_key = create_attachment(api, anchor.key, want_name, title)
        created = True
        print("  上传 → 新建 %s" % att_key)

    try:
        how = upload_file(api, att_key, pdf, md5, old_md5, fname=want_name)
        print("  上传 → %s" % how)
        got_key, match = verify(api, anchor.key, want_name, md5)
        if not match:
            raise RuntimeError("上传返回成功，但复验对不上（附件 %s），检查 Zotero 同步状态" % (got_key or "缺失"))
        status = "attached" if mode == "new" else "updated"
        print("  复验 → ok（%s）" % status)
        return {**got, "status": status, "rc": EXIT_OK, "attachment_key": got_key}
    except (RuntimeError, PermissionError) as e:
        if created:
            rolled = delete_item(api, att_key)
            print("  失败：%s；回滚空壳附件 %s" % (e, "成功" if rolled else "失败，请手工删 " + att_key))
        else:
            print("  失败：%s" % e)
        return {**got, "status": "error", "rc": EXIT_ERR, "attachment_key": att_key, "note": str(e)}


# ---------------------------------------------------------------- 配置 / 批量 / main

def load_config(path):
    cfg = {"server_id": "", "local_key": "", "user_id": "0", "remember": False,
           "inbox": "", "web_api_key": "", "web_user_id": ""}
    p = pathlib.Path(path) if path else CONFIG_DEFAULT
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for k in cfg:
                if data.get(k) not in ("", None, False):
                    cfg[k] = data[k]
            if data.get("api_key") and not cfg["web_api_key"]:
                cfg["web_api_key"] = data["api_key"]
        except (OSError, ValueError) as e:
            print("  [!] 配置文件读不了（%s），按无配置处理：%s" % (p, e))
    cfg["user_id"] = os.environ.get("ZOTERO_USER_ID") or cfg["user_id"] or "0"
    return cfg


def save_config(path, cfg):
    p = pathlib.Path(path) if path else CONFIG_DEFAULT
    data = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    data.update({k: v for k, v in cfg.items() if v not in ("", None)})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def collect(batch, pattern):
    out = []
    for p in sorted(pathlib.Path(batch).rglob(pattern)):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def zotero_dir(args):
    return pathlib.Path(args.zotero_dir) if args.zotero_dir else pathlib.Path.cwd() / "_zotero"


def main(argv=None):
    ap = argparse.ArgumentParser(description="把译文 PDF 挂回 Zotero 父条目（本地 API 优先）")
    ap.add_argument("pdf", nargs="?", help="译文 PDF；批量时省略")
    ap.add_argument("--md", default=None, help="对应译文 Markdown（默认自动找 <stem>_zh.md）")
    ap.add_argument("--parent-key", default=None, help="Zotero 父条目 key（最可靠）")
    ap.add_argument("--title", default=None, help="父条目标题（搜索用）")
    ap.add_argument("--doi", default=None, help="父条目 DOI / arXiv（搜索用）")
    ap.add_argument("--batch", default=None, metavar="DIR", help="扫描目录下全部译文 PDF")
    ap.add_argument("--pattern", default="*_zh.pdf", help="批量匹配模式，默认 *_zh.pdf")
    ap.add_argument("--strict", action="store_true", help="有待挂即返回非 0（交付门禁）")
    ap.add_argument("--auto", action="store_true", help="必须挂上，做不到就返回 1")
    ap.add_argument("--prepare-only", action="store_true", help="只锚定，不写库")
    ap.add_argument("--detect", action="store_true",
                    help="只报告来源：这篇在不在库里、挂给哪条、原文附件叫什么。不写库、不产物")
    ap.add_argument("--dry-run", action="store_true", help="只读：查条目，不写库、不产文件")
    ap.add_argument("--stage", action="store_true", help="把待挂 PDF 复制到 _zotero/inbox/ 一处")
    ap.add_argument("--attach-title", default=None, help="附件标题，默认与附件文件名一致")
    ap.add_argument("--name-prefix", default=NAME_PREFIX, help='附件名前缀，默认 "zh - "')
    ap.add_argument("--config", default=None, help="配置文件，默认 ~/.workbuddy/zotero.json")
    ap.add_argument("--zotero-dir", default=None, help="总账与降级产物目录，默认 ./_zotero")
    args = ap.parse_args(argv)

    if not args.pdf and not args.batch:
        ap.error("给一个 PDF，或用 --batch <目录>")

    cfg = load_config(args.config)
    api = Local(cfg.get("user_id") or "0")
    if api.probe():
        print("Zotero 本地 API 就绪（server %s，user %s）" % (api.server_id, api.user))
    else:
        print("[!] 本地 API 不可用：Zotero 没启动，或「设置 → 高级」里没勾"
              "「允许此计算机上的其他应用程序与 Zotero 通信」。锚定会不准。")

    targets = [pathlib.Path(args.pdf)] if args.pdf else collect(args.batch, args.pattern)
    if not targets:
        raise SystemExit("没找到要挂的 PDF（模式 %s）" % args.pattern)
    if len(targets) > 1:
        args.md = None

    results = []
    for i, pdf in enumerate(targets, 1):
        print("\n[%d/%d] %s" % (i, len(targets), pdf.name))
        if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
            print("  跳过：不是存在的 .pdf")
            continue
        results.append(run_one(pdf, args, api, cfg))

    if not args.dry_run and not args.detect:
        zdir = zotero_dir(args)
        for r in results:
            if r["status"] in ("attached", "updated", "unchanged"):
                ledger_upsert(zdir / "attached.csv", {
                    "time": datetime.datetime.now().isoformat(timespec="seconds"),
                    "stem": r["stem"], "pdf": r["pdf"], "md5": r.get("md5", ""),
                    "parent_key": r.get("parent_key", ""), "parent_title": r.get("parent_title", ""),
                    "attachment_key": r.get("attachment_key", ""),
                    "zotero_filename": r.get("zotero_filename", ""), "status": r["status"],
                    "skill": pathlib.Path(__file__).resolve().parent.parent.name,
                })
            write_manifest(r["pdf"], r)

        todo = [r for r in results
                if r["status"] not in ("attached", "updated", "unchanged", "dry-run")]
        if todo:
            if args.stage:
                inbox = zdir / "inbox"
                inbox.mkdir(parents=True, exist_ok=True)
                for r in todo:
                    dst = inbox / pathlib.Path(r["pdf"]).name
                    if not dst.is_file() or md5_of(dst) != md5_of(r["pdf"]):
                        shutil.copy(r["pdf"], dst)
                print("\n待挂副本已集中到：%s" % inbox)
            p1, p2 = emit_pending(todo, zdir)
            print("待挂清单：%s" % p1)
            if p2:
                print("一键脚本：%s" % p2)

    print("\n" + "=" * 62)
    for r in results:
        print("%-12s %-16s %s" % (r["status"], r["stem"], r.get("parent_key", "") or ""))
    rc = max((r["rc"] for r in results), default=0)
    if args.auto and any(r["status"] not in ("attached", "updated", "unchanged") for r in results):
        rc = EXIT_ERR
    if args.strict and any(r["status"] in ("pending", "ambiguous", "prepared") for r in results):
        rc = EXIT_ERR
    summary = ", ".join("%s %d" % (k, sum(1 for r in results if r["status"] == k))
                        for k in dict.fromkeys(r["status"] for r in results))
    print("=" * 62)
    print("共 %d 篇：%s" % (len(results), summary))
    return rc


if __name__ == "__main__":
    sys.exit(main())
