"""建英文 MECW 全量标题索引。

不发 API 请求（GitHub 未鉴权每小时只有 60 次），改成顺序探测 + Range 请求：
每个文件只取前 700 字节，够拿到 <title> 和 <h1> 元信息。

注意两个实测坑：
* MECW 各卷**编号会跳号**（如第 31 卷 002 不存在、010 存在），所以空号容忍要放宽，
  否则一卷会被提前截断成 1 篇。
* 书信卷（38—50）远超 80 篇，上限必须放大。

输出 index/mecw_titles.jsonl；重扫某些卷时按卷替换，不影响其余卷。
"""
import os, re, sys, json, html, time
import concurrent.futures as cf
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "https://raw.githubusercontent.com/MARX-ZH-CN/MARX-ZH-CN.github.io/main/en/MECW"
OUT = os.path.join(ROOT, "index", "mecw_titles.jsonl")


def head(url, nbytes=700):
    r = subprocess.run(["curl", "-sS", "--max-time", "25", "-r", f"0-{nbytes}", url],
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def parse(s):
    g = lambda pat, strip=True: (lambda m: re.sub(r"<[^>]+>", " ", m.group(1)).strip()
                                 if strip else m.group(1))(re.search(pat, s, re.S | re.I)) \
        if re.search(pat, s, re.S | re.I) else ""
    m = re.search(r"<title>(.*?)</title>", s, re.S | re.I)
    title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
    h = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S | re.I)
    h1 = html.unescape(re.sub(r"<[^>]+>", " ", h.group(1))).strip() if h else ""
    a = re.search(r"Author\(s\)\s*</th>\s*<td>(.*?)</td>", s, re.S | re.I)
    author = html.unescape(re.sub(r"<[^>]+>", " ", a.group(1))).strip() if a else ""
    w = re.search(r"Written\s*</th>\s*<td>(.*?)</td>", s, re.S | re.I)
    written = html.unescape(re.sub(r"<[^>]+>", " ", w.group(1))).strip() if w else ""
    return title, h1, re.sub(r"\s+", " ", author), re.sub(r"\s+", " ", written)


def scan_vol(vol, maxn=400, gap=6):
    recs, miss = [], 0
    for i in range(1, maxn + 1):
        fn = f"MECW{vol:02d}-{i:03d}.html"
        s = head(f"{BASE}/{vol}/{fn}")
        if len(s) < 200 or "<title>" not in s:
            miss += 1
            if miss >= gap:
                break
            continue
        miss = 0
        t, h1, au, wr = parse(s)
        recs.append({"vol": vol, "file": fn, "title": t, "h1": h1,
                     "author": au, "written": wr})
    return recs


def main():
    vols = [int(x) for x in sys.argv[1:]] or list(range(1, 51))
    os.makedirs(os.path.join(ROOT, "index"), exist_ok=True)

    old = []
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            r = json.loads(line)
            if r["vol"] not in vols:
                old.append(r)

    all_recs = list(old)
    t0 = time.time()
    with cf.ThreadPoolExecutor(6) as ex:
        for vol, recs in zip(vols, ex.map(scan_vol, vols)):
            all_recs.extend(recs)
            print(f"  卷{vol:2d}: {len(recs):3d} 篇  累计 {len(all_recs)}  ({time.time()-t0:.0f}s)",
                  flush=True)

    all_recs.sort(key=lambda r: (r["vol"], r["file"]))
    with open(OUT, "w", encoding="utf-8") as f:
        for r in all_recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n共 {len(all_recs)} 篇 → {OUT}")


if __name__ == "__main__":
    main()
