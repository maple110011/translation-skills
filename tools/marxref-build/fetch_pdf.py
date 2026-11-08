#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分段下载《马克思恩格斯文集》各卷 PDF。

hf-mirror 对大文件直连会 `schannel: server closed abruptly`，
必须用 Range 分段（2 MB 一段）再拼接；`--http1.1 -k` 缺一不可。
"""
import os
import subprocess
import sys
import time

BASE = ("https://hf-mirror.com/datasets/VoiceOfML/Teachers/resolve/main/"
        "A1%20%E9%A9%AC%E5%85%8B%E6%80%9D%26%E6%81%A9%E6%A0%BC%E6%96%AF/"
        "03-01%20%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86/")

# 卷号 → (URL 编码后的文件名, 字节数)
JOBS = {
    1: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(1)%20"
        "1843-1848%E5%B9%B4%E8%91%97%E4%BD%9C.pdf", 40322061),
    2: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(2)%20"
        "1848-1859%E5%B9%B4%E8%91%97%E4%BD%9C.pdf", 40100999),
    3: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(3)%20"
        "1864-1883%E5%B9%B4%E8%91%97%E4%BD%9C.pdf", 36674652),
    4: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(4)%20"
        "%E6%81%A9%E6%A0%BC%E6%96%AF1884-1895%E5%B9%B4%E8%91%97%E4%BD%9C.pdf", 34026633),
    8: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(8)%20"
        "%E3%80%8A%E8%B5%84%E6%9C%AC%E8%AE%BA%E3%80%8B%E6%89%8B%E7%A8%BF%E9%80%89%E7%BC%96.pdf",
        31102878),
    10: ("%E9%A9%AC%E5%85%8B%E6%80%9D%E6%81%A9%E6%A0%BC%E6%96%AF%E6%96%87%E9%9B%86(10)%20"
         "%E4%B9%A6%E4%BF%A1%E9%80%89%E7%BC%96.pdf", 45617189),
}

CHUNK = 2 * 1024 * 1024


def fetch(vol, name, total, root):
    out = os.path.join(root, "pdf", f"mea{vol}.pdf")
    if os.path.exists(out) and os.path.getsize(out) == total:
        print(f"[卷{vol}] 已存在，跳过", flush=True)
        return True
    n = (total + CHUNK - 1) // CHUNK
    url = BASE + name
    for i in range(n):
        a, b = i * CHUNK, min((i + 1) * CHUNK - 1, total - 1)
        part = os.path.join(root, "pdf", f"_v{vol}_{i:03d}")
        if os.path.exists(part) and os.path.getsize(part) == b - a + 1:
            continue
        ok = False
        for _ in range(5):
            subprocess.run(["curl", "-sSL", "--http1.1", "-k", "--max-time", "90",
                            "-r", f"{a}-{b}", "-o", part, url], capture_output=True)
            if os.path.exists(part) and os.path.getsize(part) == b - a + 1:
                ok = True
                break
            time.sleep(1.2)
        if not ok:
            print(f"[卷{vol}] 分片 {i}/{n} 失败", flush=True)
            return False
        if i % 5 == 0:
            print(f"[卷{vol}] {i + 1}/{n}", flush=True)
    with open(out, "wb") as f:
        for i in range(n):
            with open(os.path.join(root, "pdf", f"_v{vol}_{i:03d}"), "rb") as g:
                f.write(g.read())
    got = os.path.getsize(out)
    print(f"[卷{vol}] 完成 {got} / {total}  头部 {open(out,'rb').read(5)}", flush=True)
    return got == total


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    vols = [int(x) for x in sys.argv[1:]] or sorted(JOBS)
    for v in vols:
        name, total = JOBS[v]
        if not fetch(v, name, total, root):
            print(f"[卷{v}] 未完成", flush=True)


if __name__ == "__main__":
    main()
