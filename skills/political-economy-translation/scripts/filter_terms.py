#!/usr/bin/env python3
"""Split a mined candidate list into real terms and everyday vocabulary.

A glossary that contains `worker → 工人` and `price → 价格` is worse than a
short one: every extra row costs attention at review time and buys nothing,
because those words have one obvious rendering and no theoretical stake. What
earns a row is that a competent translator could reasonably choose differently.

So the test for keeping a single-word entry is one of three:

1. Competing scholarly renderings that change how the reader grasps the concept
   (`agent` 主体／代理人, `actor` 行动者／行为者, `representation` 表征／再现).
2. A core category with settled but non-obvious Chinese usage
   (`realization` 实现／兑现, `appropriation` 占有, `determination` 规定).
3. The everyday sense and the theoretical sense diverge, so the everyday
   rendering is actively wrong (`tension` 张力 not 紧张, `problematic` 问题式 not
   有问题, `substantive` 实质的 not 实质性的).

Everything else with one word is dropped. Multi-word candidates are kept by
default — a phrase got into the list because it recurs as a unit, which is
itself evidence — except for leftover LaTeX, citation fragments, and phrases
built on a generic modifier (`different type`, `new technology`).

Usage:
    python filter_terms.py 术语表_初稿.csv -o ./out
    python filter_terms.py 术语表_初稿.csv --keep-more "labour,class"
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

# --------------------------------------------------------------------------
# Single words worth keeping. See the module docstring for the criteria.
# --------------------------------------------------------------------------
CORE_SINGLE = set("""
value surplus exploitation accumulation realization appropriation reproduction
determination contradiction abstract abstraction agency agent actor apparatus
artifact bargaining bundle category circuit closure constructivism constructivist
contract deductive deductivism deterministic differential disequilibrium
distributive dominance dual effort emergent endowment ensemble envelope
equalization equilibrium ergodic essence exchange formation frontier gravitation
inequality informality intensification intensity invariance magnitude
motion multiplier normative ontological orthodoxy paradigm peasantry pluralism
preconception priori problematic processual profit profitability propertyless
proposition rationality realm regularity representation reswitching
stationary steady struggle substantive tacit tension trade-off trajectory
uncertainty uniform unity wage wealth welfare taxonomic calculative mediation
totality
""".split())

# The mining pass picks the rendering that co-occurs most often, which for a
# bare noun is usually the head of a compound: `reproduction` came back as
# `生产` because `reproduction of labour power` is everywhere. These are the
# renderings a translator should actually standardise on; the mined value is
# kept in `dst_mined` so the correction stays auditable.
CORE_RENDERING = {
    "inequality": "不平等",
    "reproduction": "再生产",
    "uncertainty": "不确定性",
    "realm": "领域",
    "frontier": "前沿",
    "dominance": "支配",
    "deterministic": "决定论的",
    "processual": "过程性的",
    "problematic": "问题式",
    "representation": "表征",
    "invariance": "不变性",
    "profitability": "盈利性",
    "taxonomic": "分类学的",
    "substantive": "实质的",
    "ontological": "本体论的",
    "normative": "规范的",
    "formation": "形态",
    "tacit": "默会的",
    "pluralism": "多元主义",
    "agency": "能动性",
    "ergodic": "遍历的",
    "emergent": "涌现的",
    "unity": "统一",
    "constructivist": "建构主义的",
    "deductive": "演绎的",
    "differential": "级差的",
    "distributive": "分配的",
    "regularity": "规律性",
    "uniform": "统一的",
    "mathematical deductivist": "数学演绎主义者",
}

# Hyphenated forms mined as single tokens.
CORE_HYPHEN = set("""
cross-dual self-employment self-exploitation post-keynesian wage-additive
wage-profit causal-processual
""".split())

# Phrases that are citation furniture, journal titles, or sentence fragments.
PHRASE_NOISE = [
    (re.compile(r"\bet al\b|\bet\b|\bsee\b|\bcf\b|\bibid\b"), "引用标记"),
    (re.compile(r"\b(section|chapter|figure|table|appendix|page|footnote)\b"), "文中指称"),
    (re.compile(r"\bcentury\b|\bth\b|\bpp\b"), "时间/页码"),
    (re.compile(r"\b(journal|press|review|physical|european|american economic)\b"), "刊名"),
    (re.compile(r"\b(math|mathbf|mathcal|alpha|beta|omega|lambda|sigma|nu)\b"), "数学符号"),
    (re.compile(r"\b[a-z]\b(?!\s*$)"), "含单字母词，多为公式残片"),
]

# Phrases that are not terms at all: prepositional descriptions of where
# something happens, participle-first descriptions of what something is.
# `across sector`, `produced goods`, `process oriented` all describe; none of
# them names a concept a translator has to standardise.
DESCRIPTIVE = re.compile(
    r"^(across|within|between|among|through|under|over|around|toward|towards|"
    r"throughout|beyond)\b", re.I)

# Leftover typesetting and citation junk.
NOISE_PATTERNS = [
    (re.compile(r"\bmath(bf|cal|rm|it|sf)\b"), "LaTeX 残留"),
    (re.compile(r"\bin math"), "LaTeX 残留"),
    (re.compile(r"^\w in "), "LaTeX 残留"),
    (re.compile(r"\b(doi|org|http|www|pp|vol|no|eds?)\b"), "文献标识残留"),
    (re.compile(r"\d"), "含数字"),
    (re.compile(r"\b(journal|press|review|university|publishing|verlag)\b"), "刊名/出版信息"),
]

# Phrases whose head is a generic modifier: they read as terms but carry no
# concept. `different type` and `another kind` are grammar, not vocabulary.
GENERIC_PHRASE = re.compile(
    r"^(different|same|other|another|new|old|various|several|many|few|each|every|"
    r"some|any|all|both|such|own|whole|entire|first|second|third|last|next|"
    r"previous|following|above|below|present|current|recent|modern|early|late)\b",
    re.I)

# Dropped single words, bucketed only for the report, so the reasoning is
# auditable rather than a black box.
GENERIC_BUCKETS = {
    "通用名词": """worker price data management technology model content activity
        type outcome standard literature market firm industry sector growth
        money competition choice decision information knowledge output condition
        category unit equation complex skill equation product service services
        company country culture family health city town space event theme test
        goal risk wealth population resource environment infrastructure
        performance pressure trend path version expression element reason
        conclusion suggestion overview research interview meeting workshop team
        member membership participant client consumer owner plant factory shop
        floor unit cost contract asset bank loan investment sale trade transfer
        transaction flow stock cycle curve coefficient parameter variable
        formula function matrix equation proposition theorem axiom subset sequence
        series image element obstacle opportunity initiative intervention
        involvement operation activity action""",
    "通用动词": """accept achieve adopt align analyse answer appeal assume avoid
        build calculate capture combine compare compete construct convert cover
        create defend define derive describe design distinguish eliminate
        emphasise encourage ensure estimate expand extend fail gather
        illustrate implement improve incorporate introduce justify learn
        maintain manifest miss negotiate observe pose predict preserve propose
        prove purchase reject rely resist satisfy shape share stress support
        understand""",
    "通用形容词副词": """absolute additional adequate adjusted agricultural
        algorithmic asymmetric average behavioural causal careful classic
        commercial comparative complete conceptual conditional conservative
        consistent constrained correct democratic dependent descriptive direct
        ecological econometric efficient empirical endogenous entirely
        equivalent evolutionary existing external fair financial fixed
        flexible general generalised generalized german historical homogeneous
        ideal identical immediate implicit independent indian industrial
        infinite informational initial institutional internal isolated joint
        legal linear local loose macroscopic managerial marginal material
        mathematical meaningful metaphysical microscopic mixed monetary
        neoclassical nonnegative normal normative novel numerical observable
        ongoing organisational oriented purely realistic reasonable relative
        robust scientific simple single socialist stable statistical steady
        stochastic strategic strict sufficient technical technological
        theoretical thermal typical ultimate uniform unpaid unrealistic useful
        urban weighted world""",
}

GENERIC_SINGLE = set()
for _words in GENERIC_BUCKETS.values():
    GENERIC_SINGLE.update(_words.split())


# A phrase built only from these is grammar, not vocabulary: `economic outcome`,
# `open question`, `growth rate`. Deliberately excludes `social`, `production`,
# `relation`, `value` — `social relation` and `relation of production` are terms
# and would be lost by a broader list.
GENERIC_WORD = set("""
economic outcome open question interaction complex system growth rate market
price analysis collection decision making condition working long run data
activity level across phenomena choice cost type kind form part fact process
result case point degree aspect feature factor area role
""".split())

# Multi-word renderings that came out wrong because the mining pass grabbed a
# neighbouring compound's head. `maximum entropy → 大熵` is the clearest case:
# the correct term is 最大熵 and the mined string is a fragment of 最大熵分布.
PHRASE_RENDERING = {
    "commodity production": "商品生产",          # 不是小商品生产
    "value production": "价值生产",              # 不是剩余价值生产
    "circuit of capital": "资本循环",
    "maximum entropy": "最大熵",
    "worker-member": "合作社成员",
    "type of labour": "劳动类型",
    "local management": "基层管理",
    "evolutionary science": "演化科学",
    "work process": "工作过程",                  # 与 labour process 区分
    "labor effort": "劳动努力",
    "wage-profit curve": "工资—利润曲线",
    "management system": "管理系统",
    "pool of surplus": "剩余价值池",
    "causal-processual": "因果—过程的",
    "informal economy": "非正规经济",
    "total surplus value": "总剩余价值",
    "total profit": "总利润",
    "technological change": "技术变化",
    "source of value": "价值源泉",
    "value added": "增加值",
    "value produced": "生产的价值",
    "equilibrium model": "均衡模型",
    "equilibrium method": "均衡方法",
    "gig economy": "零工经济",
    "marx' identity": "马克思恒等式",
    "marxian value theory": "马克思主义价值理论",
    "performance target": "绩效目标",
    "petty production": "小生产",
    "propertyless worker": "无产工人",
    "theoretical foundation": "理论基础",
    "weighted sum": "加权和",
    "measure of labour": "劳动量度",
    "measurement of labour": "劳动量度",
    "classical-marxian theory": "古典马克思主义理论",
    "inverse transformation": "逆变换",
    "substantive theory": "实质理论",
    "labour productivity": "劳动生产率",
    "labor productivity": "劳动生产率",
    "dynamic of capitalist": "资本主义动态",
    "social constructivist": "社会建构论者",
    "internally related": "内在相关的",
    # Fixing the longer form keeps the truncation rule from eating the head
    # term: while both rendered as `转形问题`, `transformation problem` looked
    # like a cut-off of `transformation problem debate`.
    "transformation problem debate": "转形问题之争",
    "living labor engaged": "投入的活劳动",
    "reverse capital deepening": "资本倒流深化",
    "mathematical deductivist": "数学演绎主义者",
    "heterodox tradition": "异端传统",
    "food delivery": "外卖配送",
}

# Kept out of the table for reasons a rule cannot express.
PHRASE_DROP = {
    "process engineer",      # 职业名，不是概念
    "dos santos",            # 人名，归 verified_names
    "marx' theory",          # 截断，Marx's theory of value 已单独收录
    "necessary to produce",  # 句子片段
    "process theory",        # labour process theory 的截断
    "adam smith",            # 人名
    "yoshihara n",           # 人名
    "veneziani r",
    "cogliano veneziani",
    "bernstein h",
    "amount of time",        # 通用短语
    "capitalist enterpris",  # 拼写截断
    "deductivist method",    # 截断
    "mathematical deductive",  # 截断
    "form of mathematical",  # 截断
    "method of mathematical",
    "london sage",           # 出版地 + 出版社
    "development study",     # 刊名
    "peasant study",         # 刊名
    "food distribution",     # 职业描述，非概念
    "category neoclassical",  # 词序错乱
    "politics of algorithmic",  # 截断
    "allocation of social",  # 截断
    "adverse focus",         # 截断
    "profile c",             # 公式残片
    "bundle c",
    "yakovenko v",
    "qrse model",
    "overly taxonomic",      # 含程度副词
    "heterodox opposition",  # 句子片段
    "global pool",
    "main approach",
    "advanced capitalist",   # 译法错
    "labor mobility",
    "wage-additive",
    "total surplus",         # total surplus value 的截断，且译法错
    "living labor",          # living labor engaged 的截断
    "digital worker",        # digital worker inquiry 的截断
    "marxian value",         # marxian value theory 的截断，且挖到的译法缺字
    "harriss-white",         # 人名，归 verified_names
    "dynamic of capitalist",  # capitalist dynamics 的截断
    "wage-profit",           # wage-profit curve 的截断
    "produced goods",        # 描述性短语，不是概念
    "productive activity",   # 同上
    "type of labour",        # 同上
    "social interaction",    # 通用组合；social relation 才是术语
    "social system",
    "social realm",
    "problem debate",        # 截断，且本身不是固定术语
}


def prune_truncated(kept):
    """Drop a phrase that is a word-prefix of a longer one with the same rendering.

    `classical political → 古典政治经济学` is a cut-off `classical political
    economy`; keeping both means the short one wins lookups by matching first.
    A prefix with a *different* rendering is left alone — `profit rate` is not a
    truncation of `profit rate equalization`.
    """
    by_src = {r["src"].strip().lower(): r for r in kept}
    drop = {}
    for s, r in by_src.items():
        dst = (r.get("dst") or "").strip()
        for t, rt in by_src.items():
            if dst and t != s and t.startswith(s + " ") and (rt.get("dst") or "").strip() == dst:
                drop[s] = r
                break
    return [r for r in kept if r["src"].strip().lower() not in drop], list(drop.values())


def read_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_names(path):
    """Source spellings already covered by the person/place name table."""
    if not path or not os.path.isfile(path):
        return set()
    out = set()
    for r in read_rows(path):
        src = (r.get("src") or "").strip().lower()
        if not src:
            continue
        out.add(src)
        out.update(w.strip() for w in (r.get("alias") or "").split("|") if w.strip())
    return out


def looks_like_person(src, dst):
    """`barbara → 小商品生产` is a co-occurrence accident, not a translation.

    A single word rendering to a phrase containing 和 usually means two names
    were welded together by the alignment pass.
    """
    if " " in src:
        return False
    if "和" in dst and len(dst) > 3:
        return True
    return False


def classify(row, dst_share, dst_top, keep_more, names):
    src = row["src"].strip()
    dst = (row.get("dst") or "").strip()
    low = src.lower()

    for rx, why in NOISE_PATTERNS:
        if rx.search(low):
            return "drop", "noise", why

    if looks_like_person(src, dst):
        return "drop", "noise", "疑似两个人名被拼接"

    # A rendering shared by many unrelated source words is a co-occurrence
    # artefact for *most* of them — but not for the one that actually owns the
    # rendering. `剩余价值` is shared by five source phrases; `surplus value` is
    # the real one and must survive. So the highest-frequency claimant is
    # exempt and the rest are dropped.
    nd = len(re.sub(r"[^\u4e00-\u9fff]", "", dst)) if dst else 0
    share = dst_share.get(dst, 0) if dst else 0
    # A rendering far longer than the source phrase means the mining pass
    # grabbed a clause rather than a term: `agrarian change → 模资本的入侵所摧`.
    nw = len([t for t in re.split(r"[\s\-]+", src) if t])
    if dst and nd > max(4, nw * 4):
        return "drop", "noise", "译文过长，疑似整句残留"
    claimant = (not dst) or dst_top.get(dst) == low
    if dst and not claimant and ((share >= 5 and nd <= 4) or (share >= 4 and nd <= 3)):
        return "drop", "noise", f"译法被 {share} 个源词共用，共现污染"

    multi = " " in src or "-" in src
    if not multi:
        if low in keep_more or low in CORE_SINGLE or low in CORE_HYPHEN:
            return "keep", "core", ""
        if low in names:
            return "drop", "name", "人名，由 verified_names.csv 管"
        for bucket, words in GENERIC_BUCKETS.items():
            if low in words.split():
                return "drop", "generic", bucket
        # A single word outside the core list has no rendering dispute worth a
        # glossary row: `worker`, `data`, `management` read the same in any
        # competent translation. Dropped by default, and the high-frequency
        # ones are reported so the decision can be checked.
        return "drop", "generic", "日常词汇，无译法分歧"

    if GENERIC_PHRASE.match(src):
        return "drop", "generic", "通用修饰语开头的短语"
    if DESCRIPTIVE.match(src):
        return "drop", "generic", "介词/描述性短语，不构成术语"
    toks = [t for t in re.split(r"[\s\-]+", low) if t]
    if toks and all(t in GENERIC_WORD for t in toks):
        return "drop", "generic", "全部由日常词组成"
    for rx, why in PHRASE_NOISE:
        if rx.search(low):
            return "drop", "noise", why
    return "keep", "term", ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="过滤候选术语表中的通用词与噪声")
    ap.add_argument("input", help="候选术语表 CSV（curate.py 的产物）")
    ap.add_argument("-o", "--outdir", default=".", help="输出目录")
    ap.add_argument("--keep-more", default="",
                    help="额外保留的单词，逗号分隔")
    ap.add_argument("--names", default="",
                    help="verified_names.csv 路径，用于把单个人名交给人名表")
    ap.add_argument("--min-count", type=int, default=0,
                    help="保留条目的最低出现次数（默认不过滤）")
    ap.add_argument("--min-docs", type=int, default=3,
                    help="进入主表所需的最少文献篇数（默认 3）")
    ap.add_argument("--strong-count", type=int, default=15,
                    help="篇数不足但出现次数达到此值，仍进主表（默认 15）")
    args = ap.parse_args(argv)

    keep_more = {w.strip().lower() for w in args.keep_more.split(",") if w.strip()}
    rows = read_rows(args.input)
    if not rows:
        sys.exit("输入为空。")

    names = load_names(args.names)

    by_dst = defaultdict(set)
    for r in rows:
        d = (r.get("dst") or "").strip()
        if d:
            by_dst[d].add(r["src"].strip().lower())
    dst_share = {d: len(s) for d, s in by_dst.items()}
    # Who owns each rendering: the most frequent source phrase claiming it.
    dst_top = {}
    for r in rows:
        d, s = (r.get("dst") or "").strip(), r["src"].strip().lower()
        if not d:
            continue
        n = int(r.get("count") or 0)
        if d not in dst_top or n > dst_top[d][1]:
            dst_top[d] = (s, n)
    dst_top = {d: v[0] for d, v in dst_top.items()}

    kept, dropped = [], []
    for r in rows:
        verdict, tier, why = classify(r, dst_share, dst_top, keep_more, names)
        if verdict == "keep":
            if int(r.get("count") or 0) < args.min_count:
                dropped.append((r, "generic", f"频次低于 {args.min_count}"))
                continue
            row = dict(r)
            row["tier"] = tier
            # Record the mined rendering before substituting the standard one,
            # so every correction stays visible in the delivered table.
            if tier == "core" and row["src"].strip().lower() in CORE_RENDERING:
                fixed = CORE_RENDERING[row["src"].strip().lower()]
                if fixed != row["dst"].strip():
                    row["dst_mined"] = row["dst"].strip()
                    row["dst"] = fixed
            notes = []
            if why:
                notes.append(why)
            if tier == "core" and dst_share.get(row["dst"].strip(), 0) >= 3:
                notes.append("译法被多个源词共用，需核对")
            row["note"] = "；".join(notes)
            kept.append(row)
        else:
            dropped.append((r, tier, why))

    # Hand-listed removals, then rendering corrections, then truncations.
    # Order matters: a truncation is judged by whether two phrases carry the
    # same rendering, so the corrections must land first. `transformation
    # problem` looked like a cut-off of `transformation problem debate` only
    # because the mining pass gave both the same Chinese string.
    manual = [r for r in kept if r["src"].strip().lower() in PHRASE_DROP]
    for r in manual:
        dropped.append((r, "noise", "人工判定应删"))
    kept = [r for r in kept if r["src"].strip().lower() not in PHRASE_DROP]

    fixed = 0
    for r in kept:
        low = r["src"].strip().lower()
        cur = (r.get("dst") or "").strip()
        if low in PHRASE_RENDERING and cur != PHRASE_RENDERING[low]:
            r["dst_mined"] = cur
            r["dst"] = PHRASE_RENDERING[low]
            r["note"] = "；".join(x for x in (r.get("note", ""), "译法已人工修正") if x)
            fixed += 1

    kept, truncated = prune_truncated(kept)
    for r in truncated:
        dropped.append((r, "noise", "是更长条目的截断，且译法相同"))

    os.makedirs(args.outdir, exist_ok=True)
    fields = ["src", "dst", "dst_mined", "tier", "confidence", "count", "score",
              "docs", "alt", "status", "note", "evidence"]

    # Two out of these three conditions is what makes a term trustworthy: it
    # turns up in several documents, or it turns up so often in one that the
    # rendering is unambiguous. Everything else is a candidate, kept in a
    # separate file so it cannot be mistaken for a settled decision.
    def settled(r):
        return int(r.get("docs") or 0) >= args.min_docs \
            or int(r.get("count") or 0) >= args.strong_count

    main_rows = [r for r in kept if settled(r)]
    cand_rows = [r for r in kept if not settled(r)]

    out = os.path.join(args.outdir, "术语表.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(main_rows, key=lambda x: (-int(x.get("count") or 0), x["src"])):
            w.writerow(r)

    cand = os.path.join(args.outdir, "待核候选.csv")
    with open(cand, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(cand_rows, key=lambda x: (-int(x.get("count") or 0), x["src"])):
            w.writerow(r)

    # A readable version. The CSV is for scripts; this is for deciding whether
    # to trust the table at all, which happens by reading it, not querying it.
    md = os.path.join(args.outdir, "术语表.md")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("# 实证术语表\n\n")
        fh.write("从平行语料中反推的译法。每条的 `次数` 是该词在句对齐语料中出现的次数，"
                 "`篇数` 是覆盖的文献数。"
                 "只收有译法分歧风险的词，通用词汇（工人、价格、数据、技术等）不在表内。\n\n")
        for tier, title, note in (
                ("core", "一、核心范畴", "单词形式，但存在多种学界译法或理论义与日常义不同。"),
                ("term", "二、专有术语", "多词组合，翻译时必须统一。"),
        ):
            group = [r for r in main_rows if r["tier"] == tier]
            group.sort(key=lambda x: -int(x.get("count") or 0))
            fh.write(f"## {title}（{len(group)} 条）\n\n{note}\n\n")
            fh.write("| 原文 | 译法 | 次数 | 篇数 | 修正前 |\n|---|---|---|---|---|\n")
            for r in group:
                mined = r.get("dst_mined") or ""
                fh.write(f"| {r['src']} | {r.get('dst', '')} | {r.get('count', '')} | "
                         f"{r.get('docs', '')} | {mined} |\n")
            fh.write("\n")
        if cand_rows:
            fh.write("## 三、其余候选（未列入本表）\n\n")
            fh.write(f"另有 {len(cand_rows)} 条证据不足——只在一篇文献里出现，或次数太少——"
                     "放在 `待核候选.csv`。**它们不是标准译法**，翻译时遇到按上下文自行处理，"
                     "不必迁就表里的写法。\n")

    rej = os.path.join(args.outdir, "剔除清单.csv")
    with open(rej, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["src", "dst", "类别", "原因", "次数", "篇数"])
        for r, tier, why in sorted(dropped, key=lambda x: -int(x[0].get("count") or 0)):
            w.writerow([r["src"], r.get("dst", ""), tier, why, r.get("count", ""), r.get("docs", "")])

    counts = Counter(r["tier"] for r in kept)
    reasons = Counter(t for _, t, _ in dropped)
    report = [
        "术语表精简报告",
        "=" * 40,
        f"输入              {len(rows)}",
        f"保留              {len(kept)}",
        f"  核心术语(core)   {counts.get('core', 0)}",
        f"  多词术语(term)   {counts.get('term', 0)}",
        f"  → 主表           {len(main_rows)}",
        f"  → 待核候选       {len(cand_rows)}",
        f"剔除              {len(dropped)}",
        f"  日常词汇         {reasons.get('generic', 0)}",
        f"  人名             {reasons.get('name', 0)}",
        f"  噪声             {reasons.get('noise', 0)}",
        "",
        "保留率 {:.0%}".format(len(kept) / max(1, len(rows))),
    ]
    txt = os.path.join(args.outdir, "filter_report.txt")
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + "\n")
    print("\n".join(report))
    print(f"\n已写出：\n  {out}\n  {cand}\n  {rej}\n  {txt}")

    # The dropped words most likely to be argued about: frequent across many
    # documents but judged everyday vocabulary.
    risky = [r for r, tier, _ in dropped
             if tier == "generic" and int(r.get("count") or 0) >= 15]
    risky.sort(key=lambda r: -int(r["count"]))
    if risky:
        print(f"\n被删的高频词（≥15 次，如认为该留请用 --keep-more 加回）：")
        for r in risky[:20]:
            print(f"  {r['count']:>4} {r['src'][:22]:24} → {r['dst']}")


if __name__ == "__main__":
    main()
