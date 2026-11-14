#!/usr/bin/env python3
"""Extract a PDF into Markdown through the MinerU v4 API.

Why this exists instead of a one-liner
--------------------------------------
The awkward part of every MinerU call is not the request, it is the token:
before this script, each run meant either exporting an environment variable in
a shell that the agent does not share, or pasting a 40-character secret into a
chat log where it then lives forever. Both are bad. This script resolves the
token from a documented chain of places, tells you *which* place it came from,
never prints the secret itself, and can store it once with `--set-token`.

Token resolution order (first hit wins)
---------------------------------------
1. ``--token``            one-off override, never persisted
2. ``$MINERU_TOKEN``      environment variable
3. ``~/.workbuddy/secrets/mineru_token.json``   written by ``--set-token``
4. ``~/.dsh/mineru-token`` / ``~/.dsh/mineru-token.txt``   legacy file, read-only
5. interactive prompt     only if stdin is a TTY; offers to save to (3)

Usage
-----
    # one-time setup (prompts, stores, exits)
    python mineru_extract.py --set-token

    # check where the token is coming from, without running anything
    python mineru_extract.py --token-status

    # extract one or more PDFs
    python mineru_extract.py paper.pdf -o ./extracted

    # only pages 3-12, force OCR, English
    python mineru_extract.py scan.pdf --pages 3-12 --ocr --lang en

The extracted Markdown is a working draft. It never outranks the source PDF:
formulas, tables, and footnote markers produced here still have to be checked
against the page image before the text is treated as authoritative.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile

API_BASE = "https://mineru.net/api/v4"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".workbuddy", "secrets")
CONFIG_PATH = os.path.join(CONFIG_DIR, "mineru_token.json")
LEGACY_PATHS = [
    os.path.join(os.path.expanduser("~"), ".dsh", "mineru-token"),
    os.path.join(os.path.expanduser("~"), ".dsh", "mineru-token.txt"),
]

STATE_DONE = {"done"}
STATE_FAIL = {"failed"}

ERROR_HINTS = {
    "A0202": "token 错误。确认 Bearer 前缀与 token 一致，或用 --set-token 重新写入。",
    "A0211": "token 已过期。到 mineru.net 的 API 管理页重建，再 --set-token。",
    "-60005": "文件超过 200MB，先拆分。",
    "-60006": "文件超过 200 页，用 --pages 分段提取。",
    "-60008": "源文件读取超时，网络或文件本身有问题。",
    "-60018": "当日任务数达上限，次日再试。",
}


# --------------------------------------------------------------------------
# Token handling
# --------------------------------------------------------------------------
def mask(token: str) -> str:
    """Render a secret so a human can recognise it but not reuse it."""
    if not token:
        return "(空)"
    if len(token) <= 12:
        return token[:2] + "*" * (len(token) - 2)
    return f"{token[:6]}…{token[-4:]}  (len={len(token)})"


def resolve_token(cli_token=None, prompt=True):
    """Return (token, source_label). Never raises for a missing token if
    prompting is allowed and a TTY is available."""
    if cli_token:
        return cli_token.strip(), "--token (本次有效，未保存)"

    env = os.environ.get("MINERU_TOKEN", "").strip()
    if env:
        return env, "环境变量 MINERU_TOKEN"

    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                tok = (json.load(fh).get("token") or "").strip()
            if tok:
                return tok, CONFIG_PATH
        except (OSError, ValueError):
            pass

    for p in LEGACY_PATHS:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    tok = fh.read().strip()
                if tok:
                    return tok, f"{p}（旧文件，只读）"
            except OSError:
                continue

    if not prompt:
        return "", "未找到"
    if not sys.stdin.isatty():
        return "", "未找到，且当前不是交互终端"

    print("未找到 MinerU token。")
    print("获取方式：登录 https://mineru.net → API 管理 → 创建 Token。")
    tok = getpass.getpass("请粘贴 token（输入不回显）：").strip()
    if not tok:
        return "", "用户未输入"
    save = input(f"保存到 {CONFIG_PATH} 以便下次直接使用？[Y/n] ").strip().lower()
    if save in ("", "y", "yes"):
        write_token(tok)
        print(f"已保存：{CONFIG_PATH}")
    return tok, "本次输入"


def write_token(token: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    payload = {
        "token": token,
        "note": "MinerU v4 API token. 由 mineru_extract.py --set-token 写入。",
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    try:
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600 where supported
    except OSError:
        pass


def cmd_set_token():
    print("设置 MinerU API token。")
    print("获取方式：登录 https://mineru.net → API 管理 → 创建 Token。")
    tok = getpass.getpass("请粘贴 token（输入不回显）：").strip()
    if not tok:
        sys.exit("未输入，已取消。")
    if not tok.startswith("sk-"):
        print("提示：MinerU 的 token 通常以 'sk-' 开头，请确认没有粘错。")
    write_token(tok)
    print(f"已写入 {CONFIG_PATH}")
    print(f"指纹：{mask(tok)}")
    print("此后的调用会自动读取它，无需再输入。")


def cmd_token_status():
    tok, src = resolve_token(prompt=False)
    if not tok:
        print(f"未配置。来源：{src}")
        print("运行 python mineru_extract.py --set-token 写入，或临时 --token 传入。")
        return
    print(f"来源：{src}")
    print(f"指纹：{mask(tok)}")
    print("解析顺序：")
    chain = [
        ("命令行 --token", src.startswith("--token")),
        ("环境变量 MINERU_TOKEN", "环境变量" in src),
        (f"本脚本配置 {CONFIG_PATH}", src == CONFIG_PATH),
        ("旧文件 ~/.dsh/mineru-token（只读）", "旧文件" in src),
        ("交互输入", "本次输入" in src),
    ]
    for label, hit in chain:
        print(f"  {'✓' if hit else ' '} {label}")
    if "旧文件" in src:
        print("\n提示：正在使用旧的位置。运行 --set-token 可迁到本脚本的配置文件，"
              "旧文件保持不动。")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
def _request(method, url, token=None, payload=None, raw=None, timeout=120):
    data = raw if raw is not None else (
        json.dumps(payload).encode("utf-8") if payload is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        raise RuntimeError(f"HTTP {e.code}: {body[:400]!r}") from None
    if not body:
        return {}
    try:
        return json.loads(body)
    except ValueError:
        return {"_raw": body[:400].decode("utf-8", "replace")}


def _check(resp, token):
    if resp.get("code") not in (0, "0", None):
        code = str(resp.get("code"))
        msg = resp.get("msg") or resp.get("_raw") or ""
        hint = ERROR_HINTS.get(code, "")
        detail = f"[{code}] {msg}"
        if hint:
            detail += f"\n  处理建议：{hint}"
        detail += f"\n  当前 token：{mask(token)}"
        raise SystemExit(detail)
    return resp.get("data") or {}


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
def submit_batch(token, files, model, ocr, formula, table, lang, pages, extra=None):
    payload_files = []
    for f in files:
        item = {"name": os.path.basename(f), "is_ocr": bool(ocr)}
        if pages:
            item["page_ranges"] = pages
        payload_files.append(item)
    payload = {"files": payload_files, "model_version": model,
               "enable_formula": bool(formula), "enable_table": bool(table)}
    if lang:
        payload["language"] = lang
    if extra:
        # markdown/json 是默认输出；这里只放 docx / html / latex
        payload["extra_formats"] = list(extra)
    resp = _request("POST", f"{API_BASE}/file-urls/batch", token, payload)
    data = _check(resp, token)
    urls = data.get("file_urls") or []
    if len(urls) != len(files):
        raise SystemExit(f"申请到 {len(urls)} 个上传链接，但有 {len(files)} 个文件。")
    return data.get("batch_id"), urls


def upload(url, path):
    """PUT the file to the presigned OSS URL.

    Uses http.client rather than urllib on purpose: urllib's handler silently
    adds ``Content-Type: application/x-www-form-urlencoded`` to any request that
    carries a body, and OSS computes the signature over the headers it expects,
    so that extra header produces ``SignatureDoesNotMatch`` (403). The presigned
    URL must be honoured exactly as issued: method, host, path, query, and no
    stray headers beyond Content-Length.
    """
    import http.client
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if parts.scheme != "https":
        raise SystemExit(f"上传链接不是 https，拒绝发送：{parts.scheme}")
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    size = os.path.getsize(path)
    conn = http.client.HTTPSConnection(parts.netloc, timeout=600)
    try:
        with open(path, "rb") as fh:
            conn.putrequest("PUT", target, skip_accept_encoding=True)
            conn.putheader("Content-Length", str(size))
            conn.endheaders()
            remaining = size
            while remaining > 0:
                chunk = fh.read(min(1 << 20, remaining))
                if not chunk:
                    break
                conn.send(chunk)
                remaining -= len(chunk)
        resp = conn.getresponse()
        body = resp.read()[:400]
        if resp.status not in (200, 201):
            raise SystemExit(
                f"上传 {os.path.basename(path)} 失败 HTTP {resp.status}："
                f"{body.decode('utf-8', 'replace')}")
    finally:
        conn.close()
    print(f"  已上传 {os.path.basename(path)}（{size / 1048576:.1f} MB）")


def poll(token, batch_id, expected, interval=3, timeout=1800):
    deadline = time.time() + timeout
    last_seen = {}
    while time.time() < deadline:
        resp = _request("GET", f"{API_BASE}/extract-results/batch/{batch_id}", token)
        data = _check(resp, token)
        results = data.get("extract_result") or []
        done = 0
        for item in results:
            name = item.get("file_name") or "?"
            state = item.get("state") or "?"
            prog = item.get("extract_progress") or {}
            if state in STATE_DONE:
                done += 1
            elif state in STATE_FAIL:
                raise SystemExit(
                    f"{name} 解析失败：{item.get('err_msg') or '未知原因'}")
            if state != last_seen.get(name):
                last_seen[name] = state
                extra = ""
                if prog.get("extracted_pages"):
                    extra = f"  {prog['extracted_pages']}/{prog.get('total_pages', '?')} 页"
                print(f"  {name}: {state}{extra}")
        if results and done == len(results) and len(results) >= expected:
            return results
        if results and done == len(results) and expected == 1:
            return results
        time.sleep(interval)
    raise SystemExit(f"等待超时（{timeout}s）。batch_id={batch_id}，可稍后手动查看。")


def fetch_zip(url, dest_dir, stem):
    """Download the result archive, unpack it, and locate the markdown file.

    The archive is written to the system temp directory rather than beside the
    output, so a failed cleanup can never leave a stray dotfile in the project.
    """
    import tempfile

    os.makedirs(dest_dir, exist_ok=True)
    print("  下载结果包…")
    fd, tmp = tempfile.mkstemp(suffix=".zip", prefix="mineru_")
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, tmp)
        out = os.path.join(dest_dir, stem)
        if os.path.isdir(out):
            shutil.rmtree(out, ignore_errors=True)
        with zipfile.ZipFile(tmp) as zf:
            zf.extractall(out)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

    # MinerU puts full.md at the archive root; be tolerant of nesting.
    for pattern in ("full.md", ".md"):
        for root, _dirs, names in os.walk(out):
            for n in sorted(names):
                if n == pattern or (pattern == ".md" and n.endswith(".md")):
                    return os.path.join(root, n), out
    return None, out


def cmd_extract(args):
    token, src = resolve_token(args.token)
    if not token:
        raise SystemExit(
            f"没有可用的 MinerU token（{src}）。\n"
            "运行 python mineru_extract.py --set-token 一次性写入，"
            "或临时用 --token 传入。")
    print(f"token 来源：{src}   指纹：{mask(token)}")

    pdfs = []
    for p in args.inputs:
        if os.path.isdir(p):
            pdfs += [os.path.join(p, n) for n in sorted(os.listdir(p))
                     if n.lower().endswith((".pdf", ".docx", ".pptx", ".png", ".jpg"))]
        elif os.path.isfile(p):
            pdfs.append(p)
        else:
            raise SystemExit(f"找不到文件：{p}")
    if not pdfs:
        raise SystemExit("没有可处理的文件。")

    if len(pdfs) > 50:
        raise SystemExit("单次最多 50 个文件，请分批。")
    big = [p for p in pdfs if os.path.getsize(p) > 200 * 1048576]
    if big:
        raise SystemExit("以下文件超过 200MB，请先拆分：\n  " + "\n  ".join(big))

    todo = pdfs
    if not args.force:
        todo = [p for p in pdfs
                if not os.path.isfile(os.path.join(
                    args.outdir, os.path.splitext(os.path.basename(p))[0], "full.md"))]
        skipped = len(pdfs) - len(todo)
        if skipped:
            print(f"跳过 {skipped} 个已有结果的文件（--force 可重跑）。")
    if not todo:
        print("全部已存在，未提交任务。")
        return

    print(f"提交 {len(todo)} 个文件（model={args.model}"
          f"{'，OCR' if args.ocr else ''}{'，页码范围 ' + args.pages if args.pages else ''}）…")
    batch_id, urls = submit_batch(token, todo, args.model, args.ocr,
                                  not args.no_formula, not args.no_table,
                                  args.lang, args.pages, args.extra_formats)
    print(f"batch_id = {batch_id}")
    for url, path in zip(urls, todo):
        upload(url, path)

    print("等待解析…")
    results = poll(token, batch_id, len(todo), timeout=args.timeout)

    by_name = {}
    for item in results:
        if item.get("full_zip_url"):
            by_name[item.get("file_name")] = item["full_zip_url"]

    made = []
    for path in todo:
        stem = os.path.splitext(os.path.basename(path))[0]
        url = by_name.get(os.path.basename(path))
        if not url:
            print(f"  {stem}: 结果中缺少下载链接，跳过")
            continue
        md, outdir = fetch_zip(url, args.outdir, stem)
        if md:
            made.append(md)
            print(f"  → {md}")
        else:
            print(f"  {stem}: 压缩包里没有 markdown")
    if made:
        print("\n完成。这些是工作草案，公式/表格/脚注仍需对照原 PDF 校对，"
              "不要把提取结果当作最终事实来源。")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="用 MinerU v4 API 把 PDF 提取为 Markdown（token 只需设置一次）。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="PDF/图片/Office 文件或目录")
    ap.add_argument("-o", "--outdir", default="mineru_out", help="输出目录")
    ap.add_argument("--model", default="vlm", choices=["vlm", "pipeline", "MinerU-HTML"])
    ap.add_argument("--pages", default=None, help='页码范围，如 "3-12"、"2,4-6"')
    ap.add_argument("--ocr", action="store_true", help="强制 OCR（扫描件用）")
    ap.add_argument("--lang", default=None, help='文档语言，如 en / ch')
    ap.add_argument("--no-formula", action="store_true", help="关闭公式识别")
    ap.add_argument("--no-table", action="store_true", help="关闭表格识别")
    ap.add_argument("--token", default=None, help="一次性 token，不保存")
    ap.add_argument("--set-token", action="store_true", help="交互式写入 token 后退出")
    ap.add_argument("--token-status", action="store_true", help="只看 token 来源与指纹")
    ap.add_argument("--force", action="store_true", help="已有结果也重跑")
    ap.add_argument("--timeout", type=int, default=1800, help="轮询超时秒数")
    ap.add_argument("--extra-formats", default=None,
                    help="额外导出格式，逗号分隔：docx,html,latex（默认只出 md+json）")
    args = ap.parse_args(argv)

    if args.set_token:
        cmd_set_token()
        return
    if args.token_status:
        cmd_token_status()
        return
    if not args.inputs:
        ap.print_help()
        sys.exit(1)
    if isinstance(args.extra_formats, str):
        args.extra_formats = [x.strip() for x in args.extra_formats.split(",") if x.strip()]
    cmd_extract(args)


if __name__ == "__main__":
    main()
