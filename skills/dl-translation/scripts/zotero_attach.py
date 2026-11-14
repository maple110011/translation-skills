#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""把译文 PDF 挂回 Zotero 父条目，作为子附件。

多数文献是从 Zotero 文献库里拖出来的：Windows 的 ``Zotero\drag`` 临时目录
会被清空，原文 PDF 常常已经不在，但文献条目仍在库里。译文 PDF 出完之后
应该回到那个条目下面，而不是散落在工作区。

两条路径（能自动就自动，不能就给可执行的待挂清单）：

* **自动**：配置了 Zotero Web API key（且装了 ``pyzotero``）时，按标题/DOI
  找到父条目，创建 attachment 子项并上传 PDF，最后复验子项确实存在。
* **待挂**：零配置时把 PDF 复制到 ``<PDF同级>/_work/zotero_inbox/``，写一份
  ``zotero_attach.json`` 清单，并打印在 Zotero 里选中条目后要做的两步操作。

**绝不直接读写 ``zotero.sqlite``**：Zotero 运行时数据库被锁，手工插 item 会
破坏同步。一切写入只走官方 Web API（或 Zotero 自己的界面）。

用法::

    python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md
    python scripts/zotero_attach.py <stem>_zh.pdf --parent-key ABCD1234 --auto
    python scripts/zotero_attach.py <stem>_zh.pdf --prepare-only --dry-run

配置（任选其一）::

    ZOTERO_API_KEY / ZOTERO_USER_ID / ZOTERO_LIBRARY_TYPE 环境变量
    ~/.workbuddy/zotero.json  {"api_key":"...","user_id":"...","inbox":"..."}

只用 Python 标准库；自动上传是**可选依赖** ``pyzotero``。
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

CONFIG_DEFAULT = pathlib.Path.home() / ".workbuddy" / "zotero.json"


def front_matter(md):
    """从译文 YAML front matter 取 title / DOI / citekey，供搜索父条目。"""
    out = {}
    if not md or not pathlib.Path(md).is_file():
        return out
    text = pathlib.Path(md).read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return out
    for line in m.group(1).split("\n"):
        k, _, v = line.partition(":")
        v = v.strip().strip('"').strip("'")
        if k.strip() in ("title", "title_en", "doi", "DOI", "citekey") and v:
            out[k.strip().lower()] = v
    return out


def drag_title(path):
    """Zotero 拖出的临时文件名通常是「作者 - 年份 - 题名.pdf」。"""
    stem = pathlib.Path(path).stem
    m = re.match(r"^.+?\s+-\s+(\d{4})\s+-\s+(.+)$", stem)
    return (m.group(2).strip(), m.group(1)) if m else (stem, "")


def load_config(path):
    cfg = {"api_key": os.environ.get("ZOTERO_API_KEY", ""),
           "user_id": os.environ.get("ZOTERO_USER_ID", ""),
           "library_type": os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
           "inbox": ""}
    p = pathlib.Path(path) if path else CONFIG_DEFAULT
    if p.is_file():
        try:
            cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                        if k in cfg and v})
        except (OSError, ValueError) as e:
            print("  [!] 配置文件读不了（%s），用环境变量：%s" % (p, e))
    return cfg


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def title_score(a, b):
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def find_parent(zot, key, title, doi):
    if key:
        try:
            return key, zot.item(key)["data"].get("title", "")
        except Exception as e:
            raise SystemExit("父条目 key %s 取不到：%s" % (key, e))
    for q in (doi, title):
        if not q:
            continue
        try:
            items = zot.items(q=q, limit=25)
        except Exception as e:
            raise SystemExit("按 %r 搜索 Zotero 失败：%s" % (q, e))
        tops = [it for it in items
                if it.get("data", {}).get("itemType") not in ("attachment", "note")
                and it.get("data", {}).get("title")]
        if not tops:
            continue
        best = max(tops, key=lambda it: title_score(it["data"]["title"], title or q))
        if title and title_score(best["data"]["title"], title) < 0.45:
            continue
        return best["data"]["key"], best["data"]["title"]
    raise SystemExit("没找到父条目：给 --parent-key（Zotero 里右键条目可复制 URI/Key），"
                     "或补 --title / --doi 再试")


def auto_attach(pdf, cfg, key, title, doi, dry_run):
    """返回 (状态, 附件 key, 提示)；None 表示不能自动、应降级到待挂。"""
    if not (cfg.get("api_key") and cfg.get("user_id")):
        return None, "", "未配置 ZOTERO_API_KEY / ZOTERO_USER_ID", ""
    try:
        from pyzotero import zotero  # type: ignore
    except ImportError:
        return None, "", "没装 pyzotero（自动上传需要：pip install pyzotero）", ""
    try:
        zot = zotero.Zotero(cfg["user_id"], cfg.get("library_type", "user"), cfg["api_key"])
        parent_key, parent_title = find_parent(zot, key, title, doi)
        print("  父条目：%s（%s）" % (parent_key, parent_title))
        if dry_run:
            return "dry-run", "", "只做了查找，未上传", parent_key
        try:
            children = zot.children(parent_key)
        except Exception as e:
            raise SystemExit("取子附件失败：%s" % e)
        for c in children:
            if (c.get("data", {}).get("itemType") == "attachment"
                    and c.get("data", {}).get("filename") == pdf.name):
                print("  已存在同名附件 %s，跳过（幂等）" % pdf.name)
                return "already-attached", c["data"]["key"], "附件已存在", parent_key
        # Windows 上长路径/带空格会让 attachment_simple 静默失败；先复制到短的临时名。
        with tempfile.TemporaryDirectory() as td:
            short = pathlib.Path(td) / "zot_upload.pdf"
            shutil.copy(pdf, short)
            res = zot.attachment_both([(pdf.name, str(short))], parentid=parent_key)
        if res.get("failure"):
            raise SystemExit("上传失败：%s" % res["failure"])
        ok = res.get("success") or []
        if not ok:
            raise SystemExit("上传没有返回成功项：%s" % res)
        att_key = ok[0].get("key", "") if isinstance(ok[0], dict) else ""
        for c in zot.children(parent_key):
            if c.get("data", {}).get("filename") == pdf.name:
                return "attached", c["data"]["key"], "已上传并复验", parent_key
        return "attached-unverified", att_key, "上传返回成功，但复验没找到子项，检查同步状态", parent_key
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit("自动上传出错：%s" % e)


def prepare(pdf, inbox, key, title, doi, dry_run, reason):
    d = pathlib.Path(inbox) if inbox else pdf.parent / "_work" / "zotero_inbox"
    if not dry_run:
        d.mkdir(parents=True, exist_ok=True)
    copy = d / pdf.name
    digest = sha256(pdf)
    if copy.is_file() and sha256(copy) == digest:
        status = "复用已有副本"
    elif dry_run:
        status = "dry-run，未复制"
    else:
        shutil.copy(pdf, copy)
        status = "已复制待挂副本"
    manifest = {
        "pdf": str(pdf), "copy": str(copy), "sha256": digest,
        "title": title, "doi": doi, "parent_key": key,
        "zotero_uri": ("zotero://select/library/items/%s" % key) if key else "",
        "status": "prepared", "reason": reason,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    mf = pdf.parent / "_work" / "zotero_attach.json"
    if not dry_run:
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n待挂副本：%s（%s）" % (copy, status))
    print("清单：%s" % mf)
    if key:
        print("打开父条目：zotero://select/library/items/%s" % key)
    print("在 Zotero 里选中对应文献条目，然后二选一：")
    print("  · 右键 → 添加附件 → 添加文件副本（Attach Stored Copy of File）→ 选上面这个 PDF；")
    print("  · 或把该 PDF 直接拖到条目上（Zotero 会自动建成子附件）。")
    if reason:
        print("（未自动上传的原因：%s）" % reason)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="把译文 PDF 挂回 Zotero 父条目作为子附件")
    ap.add_argument("pdf", help="译文 PDF")
    ap.add_argument("--md", default=None, help="对应译文 Markdown，从 YAML 取 title/DOI")
    ap.add_argument("--parent-key", default=None, help="Zotero 父条目 key（8 位）")
    ap.add_argument("--title", default=None, help="父条目标题（用于搜索）")
    ap.add_argument("--doi", default=None, help="父条目 DOI（用于搜索，优先）")
    ap.add_argument("--config", default=None, help="配置文件路径，默认 ~/.workbuddy/zotero.json")
    ap.add_argument("--inbox", default=None, help="待挂副本目录，默认 <PDF>/_work/zotero_inbox")
    ap.add_argument("--auto", action="store_true", help="强制自动上传；做不到就返回 1")
    ap.add_argument("--prepare-only", action="store_true", help="只生成待挂副本与操作指引")
    ap.add_argument("--dry-run", action="store_true", help="只解析与查找，不复制、不上传")
    args = ap.parse_args(argv)

    pdf = pathlib.Path(args.pdf)
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise SystemExit("译文 PDF 不存在或不是 .pdf：%s" % pdf)
    fm = front_matter(args.md)
    drag, _ = drag_title(str(pdf))
    title = args.title or fm.get("title_en") or fm.get("title") or drag
    doi = args.doi or fm.get("doi") or fm.get("citekey") or ""
    cfg = load_config(args.config)

    print("译文 PDF：%s（%s 字节）" % (pdf, format(pdf.stat().st_size, ",")))
    print("父条目线索：标题=%r DOI=%r key=%r" % (title, doi, args.parent_key or ""))

    if args.prepare_only:
        return prepare(pdf, args.inbox, args.parent_key, title, doi, args.dry_run,
                       "显式 --prepare-only")

    status, att_key, note, parent_key = auto_attach(
        pdf, cfg, args.parent_key, title, doi, args.dry_run)
    if status is None:
        if args.auto:
            print("[FAIL] 强制自动模式，但%s" % note)
            return 1
        return prepare(pdf, args.inbox, args.parent_key, title, doi, args.dry_run, note)

    print("\n[PASS] %s：%s" % (status, note))
    if att_key:
        print("附件 key：%s" % att_key)
    if parent_key:
        print("打开父条目：zotero://select/library/items/%s" % parent_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
