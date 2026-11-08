"""第 8 卷专用的段级单调对齐。

为什么不用 align.py 的通用 DP：那个 DP 的 skip 代价对两个方向是同一个数，
适合「两边段落大致同构」的场景（资本论正文）。第 8 卷不是——
中文是摘选，英文段落数是中文的 4—12 倍，用对称代价时 DP 会把中文摊到
大片无关英文上：实测数字一致率掉到 0.1%，等于随机。

所以这里用**非对称代价**：
* 跳过英文段 0.06 —— 摘选本来就是隔一段取一段，横向跳过必须极便宜；
* 跳过中文段 1.50 —— 中文几乎每段都该落在英文某处，跳过要重罚；
* 数字对不上重罚 3.0 —— 手稿里数字（金额、百分比、页码）密度不低，
  是唯一跨语言字面可比的锚，它说不一致就是不一致。
"""
import json
import math
import re

NUM = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)*(?![\d])")
EN_S = re.compile(r'[.!?](?=[\s"\u201c\u2018]*[A-Z])')
ZH_S = re.compile(r"[。！？]")
C0 = 0.24          # 中文汉字 / 英文字符


def nums(t):
    return {re.sub(r"[, ]", "", x).strip(".") for x in NUM.findall(t or "") if x.strip(".")}


def feat(t, lang):
    s = len(EN_S.findall(t)) + 1 if lang == "en" else len(ZH_S.findall(t))
    return len(t), max(s, 1), nums(t)


def cost(e, z, prior=0.0):
    el, es, en = e
    zl, zs, zn = z
    c = 0.30 + prior
    c += 1.2 * abs(math.log((zl + 1.0) / (el * C0 + 1.0)))
    c += 0.8 * abs(zs - es) / max(es, zs, 1)
    if en and zn:
        inter = len(en & zn)
        if inter == 0:
            c += 1.2                     # 都有数字却一个都对不上，几乎肯定错配
        else:
            c += 3.0 * (1.0 - inter / len(en | zn))
    return c


def align_monotone(E, Z, skip_e=0.06, skip_z=1.50, prior_w=0.8):
    """返回 [(i, j)] 匹配对，i 英文段号，j 中文段号。"""
    n, m = len(E), len(Z)
    EF = [feat(t, "en") for t in E]
    ZF = [feat(t, "zh") for t in Z]
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        row, brow = dp[i], bk[i]
        for j in range(m + 1):
            cur = row[j]
            if cur == INF:
                continue
            if i < n:
                c = cur + skip_e
                if c < dp[i + 1][j]:
                    dp[i + 1][j] = c
                    bk[i + 1][j] = (1, 0)
            if j < m:
                c = cur + skip_z
                if c < row[j + 1]:
                    row[j + 1] = c
                    brow[j + 1] = (0, 1)
            if i < n and j < m:
                # 对角先验：摘选整体按手稿顺序推进，位置比偏离越多越可疑。
                # 没有这个先验时，数字锚又几乎没有（567 段里只有 40 段带数字），
                # DP 会自由漂移。
                c = cur + cost(EF[i], ZF[j], prior_w * abs(i / max(n, 1) - j / max(m, 1)))
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c
                    bk[i + 1][j + 1] = (1, 1)
            if i + 1 < n and j < m:
                # 英文两段并成中文一段（手稿分段比中文译本更碎）
                e2 = (EF[i][0] + EF[i + 1][0], EF[i][1] + EF[i + 1][1],
                      EF[i][2] | EF[i + 1][2])
                c = cur + cost(e2, ZF[j], prior_w * abs(i / max(n, 1) - j / max(m, 1))) + 0.10
                if c < dp[i + 2][j + 1]:
                    dp[i + 2][j + 1] = c
                    bk[i + 2][j + 1] = (2, 1)
    # 回溯
    i, j = n, m
    pairs = []
    while i > 0 or j > 0:
        step = bk[i][j]
        if step is None:
            break
        di, dj = step
        if di and dj:
            for k in range(di):
                pairs.append((i - 1 - k, j - 1))
        i, j = i - di, j - dj
    pairs.reverse()
    return pairs, dp[n][m]
