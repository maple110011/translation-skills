#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""英中**段落级**对齐。补上句级对齐留下的那个洞。

为什么需要
----------
现有 `vol*_sent.jsonl` 是句级配对，`zh_i` 指针会偏一两段，导致：
  · 某句英文被挂到隔壁中文段上（按英文排序时隔壁分更高）；
  · 中文 `zh` 常常只是半句（英文一整句只对到中文后半）。
两种毛病都不报警。段落级对齐先把「哪段对哪段」定死，句级退化成段内的事。

做法
----
同一篇（章）内，英中两侧都是同一段德文的连续译本，顺序严格单调、篇幅成比例。
用单调 DP 在「英文段 × 中文段」上求最小代价路径：

    代价 = |中文字数 − R × 英文字符数| / (R × 英文字符数)       （R 由全卷标定）
    允许 1:1、2:1、1:2，以及单向跳过（代价 0.8，让多出来的段能被丢掉）

跳过代价给得比错配小一点：宁可承认「这一段没配上」，也不要强行拉郎配——
这是本项目一贯的原则（宁可说不知道，也不指一段错的中文）。

产物：corpus/align_para/vol{N}_para.jsonl
      {zh_doc, zh_i, en_doc, en_i, en_text, rel}

用法：
    python align_para.py 1 2 3 4 5 6 7 10
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WS = re.compile(r"\s+")
SKIP_EN = 0.5      # 多出来的英文（页码行、图注）可以便宜地丢掉
SKIP_ZH = 6.0      # 中文段尽量都要有英文，否则该段永远检索不到


def clean(s):
    return WS.sub(" ", s or "").strip()


def load_jsonl(fp):
    if not os.path.exists(fp):
        return []
    return [json.loads(l) for l in open(fp, encoding="utf-8")]


def doc_map(vol):
    """从现有句表反推「中文篇 → 英文篇」。只取占比最高的组合，避免噪声。"""
    pairs = {}
    for r in load_jsonl(os.path.join(ROOT, f"corpus/vol{vol}_sent.jsonl")):
        zd, ed = r.get("zh_doc"), r.get("en_doc")
        if zd and ed:
            pairs.setdefault(zd, {}).setdefault(ed, 0)
            pairs[zd][ed] += 1
    out = {}
    for zd, d in pairs.items():
        out[zd] = [k for k, _ in sorted(d.items(), key=lambda x: -x[1])]
    return out


K = 8          # 一个块最多合并几段（英文侧或中文侧）


def align(en, zh, R):
    """单调分段 DP：允许 **任意 n:1 与 1:n 的块**，不再限于 2:1/1:2。

    为什么改：中英分段粒度常常是 3:1、5:1（英文分得细、中文分得粗）。
    旧版只允许最多并两段，多出来的靠「跳过」处理，于是出现
    「英文挂半截」「引导句占位」「同一英文挂两处」这类错位——
    盲测里 5 条分歧全是这个原因。

    转移：
        (di, 1)  di∈1..K   一段中文吃掉 di 段英文
        (1, dj)  dj∈1..K   一段英文覆盖 dj 段中文
        (1, 0) / (0, 1)   真正的跳过（引文、页码行等）
    块代价 = |中文字数 − R × 英文字符数| / (R × 英文字符数) + 0.12 × (块内段数 − 2)

    返回 [(i0, j0, i1, j1)]，语义是「英文 [i0,i1) ↔ 中文 [j0,j1)」。
    """
    m, n = len(en), len(zh)
    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(m + 1)]
    bk = [[None] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    le = [len(x) for x in en]
    lz = [len(x) for x in zh]
    pe = [0]
    for x in le:
        pe.append(pe[-1] + x)
    pz = [0]
    for x in lz:
        pz.append(pz[-1] + x)

    def cost(ez, ze, blocks):
        want = R * ez
        base = abs(ze - want) / max(1.0, want)
        return base + 0.12 * max(0, blocks - 2)

    for i in range(m + 1):
        for j in range(n + 1):
            cur = dp[i][j]
            if cur == INF:
                continue
            for di in range(1, K + 1):                    # n:1
                i2 = i + di
                if i2 > m or j >= n:
                    break
                c = cur + cost(pe[i2] - pe[i], lz[j], di + 1)
                if c < dp[i2][j + 1]:
                    dp[i2][j + 1], bk[i2][j + 1] = c, (i, j)
            for dj in range(1, K + 1):                    # 1:n
                j2 = j + dj
                if j2 > n or i >= m:
                    break
                c = cur + cost(le[i], pz[j2] - pz[j], dj + 1)
                if c < dp[i][j2]:
                    dp[i][j2], bk[i][j2] = c, (i, j)
            if i < m:                                     # 跳过一段英文
                c = cur + SKIP_EN
                if c < dp[i + 1][j]:
                    dp[i + 1][j], bk[i + 1][j] = c, (i, j)
            if j < n:                                     # 跳过一段中文
                c = cur + SKIP_ZH
                if c < dp[i][j + 1]:
                    dp[i][j + 1], bk[i][j + 1] = c, (i, j)

    path, i, j = [], m, n
    while i > 0 or j > 0:
        step = bk[i][j]
        if step is None:
            break
        pi, pj = step
        path.append((pi, pj, i, j))
        i, j = pi, pj
    path.reverse()
    return path


def run(vol):
    zh_blocks = load_jsonl(os.path.join(ROOT, f"corpus/mea{vol}.jsonl"))
    if not zh_blocks:
        print(f"卷 {vol}: 缺中文字语料，跳过")
        return
    dmap = doc_map(vol)
    # 英文篇号形如 MECW36-004——卷号与文集卷号**不是**一回事
    # （文集第 6 卷的英文底本是 MECW 第 36 卷），必须按 en_doc 反查语料文件
    need = set()
    for eds in dmap.values():
        for ed in eds:
            mm = re.match(r"MECW(\d+)-", ed)
            if mm:
                need.add(int(mm.group(1)))
    en_paras = {}
    for ev in sorted(need):
        for b in load_jsonl(os.path.join(ROOT, f"corpus/mecw{ev}.jsonl")):
            if b.get("kind") != "para" or not b.get("text"):
                continue
            en_paras.setdefault(b["doc"], []).append((b["i"], clean(b["text"])))
    zh_paras = {}
    for b in zh_blocks:
        if b.get("kind") != "para" or not b.get("text"):
            continue
        zh_paras.setdefault(b["doc"], []).append((b["i"], clean(b["text"])))
    for d in en_paras:
        en_paras[d].sort()
    for d in zh_paras:
        zh_paras[d].sort()

    dmap = doc_map(vol)
    # 先把能映射上的篇凑成「作业」：R 必须只用这些篇标定。
    # 早期版本用整卷英文字数做分母，而英文侧是按篇号载入的整卷 MECW，
    # 与中文卷不同量，R 会被算成 0.06 这种离谱值，整卷对齐全废。
    jobs, miss = [], 0
    for zd, zlist in zh_paras.items():
        en = []
        for ed in dmap.get(zd, []):
            for i, t in en_paras.get(ed, []):
                en.append((ed, i, t))
        if not en:
            miss += 1
            continue
        jobs.append((zd, zlist, en))

    tot_en = sum(len(t) for _, _, en in jobs for _, _, t in en)
    tot_zh = sum(len(t) for _, zl, _ in jobs for _, t in zl)
    R = tot_zh / max(1, tot_en)

    os.makedirs(os.path.join(ROOT, "corpus/align_para"), exist_ok=True)
    out_fp = os.path.join(ROOT, f"corpus/align_para/vol{vol}_para.jsonl")
    stats = collections.Counter()
    with open(out_fp, "w", encoding="utf-8") as fh:
        for zd, zlist, en in jobs:
            if not en:
                continue
            path = align([t for _, _, t in en], [t for _, t in zlist], R)

            # 先把块摊平：每个中文段 → (英文块, 是否顺延)
            slot = [None] * len(zlist)
            for i0, j0, i1, j1 in path:
                di, dj = i1 - i0, j1 - j0
                if dj <= 0:
                    stats["skip_en"] += di
                    continue
                if di <= 0:
                    stats["skip_zh"] += dj
                    continue
                stats[f"{di}:{dj}"] += 1
                block = en[i0:i1]
                slot[j0] = ("".join(t for _, _, t in block), block[0][0],
                            block[0][1], block[-1][1], di, dj, False)
                for j in range(j0 + 1, j1):
                    slot[j] = (slot[j0][0], slot[j0][1], slot[j0][2],
                               slot[j0][3], di, dj, False)

            # 顺延：没配上英文的中文段（表头、表格行、编者注）挂上相邻块的英文，
            # 并标 carry=True。不这样做它们就永远检索不到；标出来是为了让
            # 排序与判级知道「这段英文不是它自己的」。
            last = None
            for j in range(len(zlist)):
                if slot[j]:
                    last = slot[j]
                elif last:
                    slot[j] = last[:5] + (last[5], True)
                    stats["carry_back"] += 1
            nxt = None
            for j in range(len(zlist) - 1, -1, -1):
                if slot[j] and not slot[j][6]:
                    nxt = slot[j]
                elif slot[j] is None and nxt:
                    slot[j] = nxt[:5] + (nxt[5], True)
                    stats["carry_fwd"] += 1

            for j, s in enumerate(slot):
                if not s:
                    continue
                et, edoc, ei0, ei1, di, dj, carry = s
                zt = zlist[j][1]
                rel = abs(len(zt) - R * len(et)) / max(1.0, R * len(et))
                fh.write(json.dumps({
                    "zh_doc": zd, "zh_i": zlist[j][0],
                    "en_doc": edoc, "en_i": ei0, "en_span": [ei0, ei1],
                    "en_text": et, "rel": round(min(rel, 1.0), 3),
                    "block": f"{di}:{dj}", "carry": carry,
                }, ensure_ascii=False) + "\n")

    big = sum(v for k, v in stats.items() if ":" in k)
    print(f"卷 {vol:>2}: 篇 {len(zh_paras)}（未映射 {miss}）  R={R:.3f}  "
          f"对齐块 {big}  "
          + "  ".join(f"{k}={v}" for k, v in sorted(
              ((k, v) for k, v in stats.items() if ":" in k and v > 20),
              key=lambda x: -x[1])[:5])
          + f"  跳过 en{stats['skip_en']}  顺延 {stats['carry_back']}+{stats['carry_fwd']}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("vols", nargs="*", type=int)
    a = ap.parse_args(argv)
    for v in (a.vols or [1, 2, 3, 4, 5, 6, 7, 10]):
        run(v)


if __name__ == "__main__":
    main()
