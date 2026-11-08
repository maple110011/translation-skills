#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把译文里的马恩引文对到《马克思恩格斯文集》的中文译文。

引擎在另一套程序里（`_marx_ref/`，73k 句、8 卷），本脚本只管三件事：

1. 从**英文原文**里找马恩引文。两种形态都要抓：带引号的串，以及
   无引号但段落末尾缀着 `(1978: 357)` 的整段——马克思的长引文在
   提取稿里往往就是这种裸段落，只抓引号会漏掉最要紧的几条。
2. 逐条匹配，拿到卷次、章名、页码、文集译文，以及引擎给的
   score / coverage / numeric。
3. 判可信度。**分数低不一定是错配**：作者引的是 Penguin 版，
   文集底本是 MECW，措辞有出入，正确匹配的 score 也常在 0.2—0.5。
   所以不用分数划线，改用四条与措辞无关的证据：卷次是否与引用年份相符、
   同篇几条引文是否落在同一章、前两名分不分得开、引文里的数字对不对得上。

**先按卷收窄再匹配**（`--anchor vol`，默认）。Penguin 与 MECW 是两个独立英译本，
篇章结构却同据 Engels 德文第四版，章号一一对应。《资本论》的引用年份就足以定卷，
把搜索限制在这一卷里，比事后按分数猜可靠得多：全库搜时 `(1978: 351)` 会被配到
第 5 卷第 24 章（score 0.247），限定第 6 卷后才落到本卷第八章。

**只产出 CSV，不写双语对照 md。** 对照是要给人看的，但它属于待校对清单的一部分，
由 `review_queue.py` 渲染；最终交付的稿子里只有中文，未定的引文在清单里问。

用法：
    python scripts/marx_quotes.py --source paper_原文.md --target paper_zh.md \\
        --marxref /path/to/_marx_ref -o _work/x_马恩引文.csv
"""
import argparse
import csv
import json
import os
import re
import sys

# 作者—年份引用与卷次的对应关系。《资本论》在《文集》里是 5、6、7 卷，
# 年份按通行英文版：1976=I、1978=II、1981=III。换成别的引用体例时用 --map 覆盖。
DEFAULT_MAP = {"1976": "5", "1978": "6", "1981": "7"}

# 段末引用串。著者写法有两种：`(1976: 163)`，以及方括号式的
# `(Marx [1867] 1990: 448, emphasis added)`——后者很常见，只认前一种会把整段
# 引文整条漏掉（第 2 节那段「As the number of the co-operating workers…」就是这样丢的）。
CITE_TAIL = re.compile(
    r"\((?:[^()]*?\[\d{4}\][^()]*?)?(\d{4})\s*:\s*([^()]{1,60})\)\s*[.。]?\s*$")
CITE_SPAN = re.compile(r"\(([^()]{3,60}?)\s*(\d{4})\s*:\s*([^()]{1,40})\)")
YEAR_ONLY = re.compile(r"^(\d{4})\s*:\s*(.+)$")


def load_marxref(path):
    """把 _marx_ref 目录挂进 sys.path，返回 (Engine 类, quotes 模块)。"""
    path = os.path.abspath(path)
    if not os.path.exists(os.path.join(path, "engine.py")):
        sys.exit(f"找不到 {path}/engine.py。用 --marxref 指向 _marx_ref 目录。")
    sys.path.insert(0, path)
    from engine import Engine          # noqa: E402
    import quotes                      # noqa: E402
    return Engine, quotes


# ---------------------------------------------------------------------------
# 段落定位
#
# vol*_sent.jsonl 的 zh 字段会骗人，有两种情形：
#   1. 段内切成多句时，英文一整句可能只对到中文的后半句，前半句静默丢失
#      （p.216 那条「The worker works under the control of the capitalist…」
#       只剩「资本家进行监视…」，「工人在资本家的监督下劳动」整句没了）；
#   2. zh_i 指针会偏一两段（中文段号与英文段号不是一回事）。
# 但 zh 的文本本身是真的，所以拿它回 meaN.jsonl 的段落里反查，比信指针稳。
# 段落级文件是 mea{vol}.jsonl，与卷号同名，可以只搜该卷。
# ---------------------------------------------------------------------------

def load_paragraphs(marxref, vols):
    """读 mea{vol}.jsonl，返回 {(doc, i): text}。标题段不要：它不是正文。"""
    out = {}
    for v in vols:
        fp = os.path.join(os.path.abspath(marxref), "corpus", f"mea{v}.jsonl")
        if not os.path.exists(fp):
            continue
        for line in open(fp, encoding="utf-8"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("kind") == "heading" or not d.get("text"):
                continue
            out[(d["doc"], d["i"])] = d["text"]
    return out


def locate_paragraph(paras, hit, vol):
    """用命中的中文片段反查它真正出自哪一段，返回 {doc, i, text, how}。"""
    zh = re.sub(r"\s+", "", (hit.get("zh") or ""))
    if not zh:
        return None
    # 优先按 zh_doc 收窄范围（同卷内），不命中再放全卷
    prefer = (hit.get("zh_doc") or "")
    keys = [k for k in paras if k[0].startswith(f"MEA{vol}-")]
    if prefer:
        keys.sort(key=lambda k: k[0] != prefer)
    for n in (16, 12, 10, 8, 6):
        key = zh[:n]
        if len(key) < 6:
            continue
        for k in keys:
            if key in re.sub(r"\s+", "", paras[k]):
                return {"doc": k[0], "i": k[1], "text": paras[k], "how": f"{n}字前缀"}
    return None


def suspect(hit, para, quote):
    """把「不能直接拿去用」的情形说清楚。返回空串表示没看出问题。

    判据只有长度和位置两路，语义对不对它看不出来——所以这里给的是
    「值得人看一眼」的线索，不是结论。
    """
    zh = re.sub(r"\s+", "", hit.get("zh") or "")
    if not zh:
        return "中文为空"
    if not para:
        return "段落未定位，须人工在文集里搜"
    nw = len(re.findall(r"[A-Za-z][A-Za-z'\-]+", quote or hit.get("en") or ""))
    expect = max(8, nw * 1.6)
    ratio = len(zh) / expect
    notes = []
    if ratio < 0.85:
        notes.append(f"短于引文：{len(zh)} 字／期望约 {expect:.0f} 字，可能只对到后半句")
    elif ratio > 2.3:
        notes.append(f"长于引文：{len(zh)} 字／期望约 {expect:.0f} 字，含引文之外的上下文")
    full = re.sub(r"\s+", "", para["text"])
    pos = full.find(zh[:40])
    if pos > 0:
        head = full[:pos]
        if len(head) >= 8:
            notes.append(f"段落开头 {len(head)} 字未被覆盖（「{head[:20]}…」）")
        before = full[max(0, pos - 80):pos]
        if before.count("\u201c") > before.count("\u201d"):
            notes.append("落在段落引号内，疑为转引而非原文出处")
    return "；".join(notes)


def mark_paragraph(para, hit):
    """段落全文，把引擎命中的那截用【】圈出来，人一眼能看出缺了哪半句。"""
    if not para:
        return ""
    full, zh = para["text"], re.sub(r"\s+", "", hit.get("zh") or "")
    if not zh:
        return full
    # 在原文里找 zh 的位置（zh 是压缩过空白的，只能按前缀在压缩文本里定位）
    flat, idx, pos = [], 0, 0
    for ch in full:
        if not ch.isspace():
            flat.append(ch)
            if ch == zh[:1] and pos == 0:
                pos = idx
        idx += 1
    fz = "".join(flat)
    i = fz.find(zh[:40])
    if i < 0:
        return full
    # 压缩下标 → 原文下标
    cnt, start = 0, 0
    for j, ch in enumerate(full):
        if not ch.isspace():
            if cnt == i:
                start = j
                break
            cnt += 1
    end, cnt = len(full), 0
    for j, ch in enumerate(full):
        if not ch.isspace():
            cnt += 1
            if cnt == i + len(zh):
                end = j + 1
                break
    return full[:start] + "【" + full[start:end] + "】" + full[end:]


def strip_front(md):
    """YAML front matter 自成一"块"，不剥掉会让译文段落整体错位一格。"""
    if md.startswith("---"):
        m = re.match(r"---\n.*?\n---\n", md, re.S)
        if m:
            return md[m.end():]
    return md


def blocks_of(md):
    return [b.strip() for b in re.split(r"\n\s*\n", strip_front(md))]


def find_quotes(md, quotes_mod, years):
    """返回 [{kind, block, text, citation, year}]，block 是段落下标。"""
    body = strip_front(md)
    shift = len(md) - len(body)
    spans, pos = [], 0
    for piece in re.split(r"\n\s*\n", body):
        spans.append((pos, pos + len(piece)))
        pos += len(piece) + 2

    def block_at(offset):
        for i, (a, b) in enumerate(spans):
            if a <= offset <= b:
                return i
        return None

    out = []
    for c in quotes_mod.extract(md):
        cite = (c.get("citation") or "").strip()
        m = YEAR_ONLY.match(cite) or re.search(r"(\d{4})\s*:", cite)
        year = m.group(1) if m else ""
        if year in years:
            out.append({"kind": "quoted", "line": c["line"], "text": c["text"],
                        "citation": cite, "year": year,
                        "block": block_at(c.get("start", 0) - shift)})
    blocks = blocks_of(md)
    for i, b in enumerate(blocks):
        m = CITE_TAIL.search(b)
        if not m or m.group(1) not in years:
            continue
        body = b[:m.start()].strip()
        if len(body) < 50:
            continue
        # 整段规则的前提是「这一整段都是引文」。段内自带成对引号的，是
        # 「作者叙述 + 段中引文」的混合段（如 "Interestingly, ... is to “secure the
        # harmonious cooperation ...” (Marx 1990: 448)"）：那些引文由行内规则管，
        # 整段拿去匹配只会把作者的话也算进马克思头上，得分低还没意义。
        if '“' in body:
            continue
        out.append({"kind": "block", "line": 0, "text": body,
                    "citation": f"({m.group(1)}: {m.group(2).strip()})",
                    "year": m.group(1), "block": i})
    # 去重：同一段被两条规则抓到，留 block 那条（更完整）
    seen, uniq = set(), []
    for q in out:
        key = re.sub(r"\W+", "", q["text"].lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(q)
    return uniq, blocks


def tail_sentences(para, n=2):
    """整段引文在提取稿里是一个段落，对应译文也就是那个段落。
    引用串缀在段末，引文自然也在段末，取末尾两句比截开头有用。"""
    sents = [s.strip() for s in re.split(r"(?<=[。！？])", para or "") if s.strip()]
    return "".join(sents[-n:]) if sents else ""


def quoted_in(para):
    """段落里加了引号的那几截，取最长的一段。引文在译文里通常加了引号，
    比截段首准得多——段首往往还是作者自己的话。"""
    hits = re.findall(r"[“\"「]([^”\"」]{10,})[”\"」]", para or "")
    return max(hits, key=len) if hits else ""


def closest_sentence(para, reference):
    """在译文段落里挑与文集译文最贴的一句：中文 2-gram 重合度最高者。
    引文常嵌在长段中间，整段贴出来要人自己找，不如直接对齐到句。
    若译文里给引文加了引号，只取引号内那截——那才是"我们怎么译这句引文"，
    整句还带着作者自己的话，对照起来看不出差别。"""
    if not para or not reference:
        return ""
    ref = {reference[i:i + 2] for i in range(len(reference) - 1)}
    best, score = "", 0.0
    for s_ in re.split(r"(?<=[。！？])", para):
        s_ = s_.strip()
        if len(s_) < 8:
            continue
        m = re.search(r"[“\"「]([^”\"」]{8,})[”\"」]", s_)
        cand = m.group(1) if m else s_
        g = {cand[i:i + 2] for i in range(len(cand) - 1)}
        if not g:
            continue
        sc = len(g & ref) / len(g)
        if sc > score:
            best, score = cand, sc
    return best if score >= 0.12 else ""


def trim_hint(quote_en, zh):
    """引擎的"文集译文"是跨句合并的结果，常常比引文本身长得多。

    引文往往只是一个从句或半句，返回的却是整段两三句。哪几句才算引文覆盖的范围，
    脚本判不了——这要读语义，交给 agent。这里只把长度比摆出来：正常英译中的字数比
    在 1.6—2.0 之间，超过 2.6 倍基本可以断定译文包含了引文之外的上下文。
    反过来，比例低到 1 倍以下，多半是文集这一句的中文本身残缺（库里有这种段）。
    """
    if not zh:
        return ""
    nw = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", quote_en or ""))
    nz = len(re.findall(r"[\u4e00-\u9fff]", zh))
    if not nw or not nz:
        return ""
    ratio = nz / nw
    if ratio > 2.6:
        return f"译文 {nz} 字 / 引文 {nw} 词（{ratio:.1f} 倍），含引文之外的上下文，需裁"
    if ratio < 0.9:
        return f"译文 {nz} 字 / 引文 {nw} 词（{ratio:.1f} 倍），译文疑不完整"
    return ""


def grade(top, margin, expect_vol, numeric, majority=None, relaxed=False,
          para_note=""):
    """可信度：分数只作参考，卷次、章群、候选间距、数字才是硬证据。

    majority = (同篇引文最集中的章名, 占比)，只在 ≥4 条引文时给出。
    一篇文献里的马恩引文通常集中在同一章（本文 8 条里 7 条在第十五章），
    落单的那条不是不可能对，但值得人看一眼。
    """
    if top is None:
        return "无匹配", "引擎没有返回任何候选"
    if numeric == "mismatch":
        return "低", "引文里的数字在文集译文里对不上，多半配错了段"
    if expect_vol and str(top["vol"]) != str(expect_vol):
        how = "放宽到全库后" if relaxed else ""
        return "低", f"{how}引用年份对应第 {expect_vol} 卷，却配到第 {top['vol']} 卷"
    if majority and majority[0] and majority[1] >= 0.6 and top["chapter"] != majority[0]:
        if top["score"] >= 0.55:
            # 分数高、章不同，多半是作者真的引了别处（如第十四章讲流通时间），不算疑点
            return "高", f"落在「{top['chapter']}」，与其余引文不同章，但分数高"
        return "低", f"其余引文都在「{majority[0]}」，这条落在「{top['chapter']}」"
    if margin < 0.08:
        return "低", "前两名分数咬得太近，无法区分"
    # 句对齐的 zh 常常只是段落的一部分（英文整句对到中文后半句），
    # 这种情况分数再高也不能直接拿去用，降一级并说明占了多少。
    # 只把「短于引文」当降级理由：那是英文整句只对到中文后半句，内容真丢了。
    # 「段落开头未被覆盖」不降级——引文常常只引段落后半，这属正常；它留在
    # 「疑点」列里，供人对照「段落正文」看【】圈外的句子是否该算进来。
    if para_note and "短于引文" in para_note:
        return "中", f"分数够，但译文不完整（{para_note}），须取整段再裁"
    if top["score"] >= 0.55:
        return "高", ""
    if top["score"] >= 0.32:
        return "中", ""
    return "低", "分数偏低，且无其它证据支持"


def main(argv=None):
    ap = argparse.ArgumentParser(description="马恩引文 → 文集译文匹配")
    ap.add_argument("--source", required=True, help="英文原文 Markdown")
    ap.add_argument("--target", default="", help="中文译文 Markdown（用来并排看我们怎么译的）")
    ap.add_argument("--marxref", default=os.environ.get("MARX_REF", ""),
                    help="_marx_ref 目录；也可用环境变量 MARX_REF")
    ap.add_argument("--years", default="1973,1976,1978,1981",
                    help="视为马恩著作的引用年份，逗号分隔")
    ap.add_argument("--map", default="", help="年份=卷次,逗号分隔，覆盖默认对应")
    ap.add_argument("--anchor", choices=["vol", "none"], default="vol",
                    help="vol：按引用年份把搜索限制在对应卷（默认）；none：全库搜")
    ap.add_argument("-o", "--out", default="", help="输出 CSV")
    ap.add_argument("--md", default="", help="额外输出双语对照 Markdown（排查用，正常流程不要）")
    ap.add_argument("--topk", type=int, default=3)
    args = ap.parse_args(argv)

    if not args.marxref:
        sys.exit("需要 --marxref 指向 _marx_ref 目录（或设环境变量 MARX_REF）。")

    Engine, quotes_mod = load_marxref(args.marxref)
    years = {y.strip() for y in args.years.split(",") if y.strip()}
    vmap = dict(DEFAULT_MAP)
    for kv in [x for x in args.map.split(",") if "=" in x]:
        k, v = kv.split("=", 1)
        vmap[k.strip()] = v.strip()

    src = open(args.source, encoding="utf-8").read()
    quotes, src_blocks = find_quotes(src, quotes_mod, years)
    if not quotes:
        sys.exit("原文里没找到带年份引用的英文引文。检查 --years 是否对得上引用体例。")

    tgt_blocks = blocks_of(open(args.target, encoding="utf-8").read()) if args.target else []

    eng = Engine()
    paras = load_paragraphs(args.marxref, eng.volumes)
    if not paras:
        print("⚠ 没读到 meaN.jsonl 段落文件，段落定位关闭（仍可用，但会缺「段落正文」）",
              file=sys.stderr)
    matched = []
    for q in quotes:
        expect = vmap.get(q["year"], "")
        vols = [int(expect)] if (args.anchor == "vol" and expect) else None
        # 多要几个候选：跨句合并会把窗口重新打分，返回序不等于最终分数序
        hits = eng.match(q["text"], topk=max(args.topk, 6), volumes=vols)
        relaxed = False
        if not hits and vols:
            # 卷约束下一无所获，放宽到全库重搜；但记下放宽过，别当成正常结果
            hits = eng.match(q["text"], topk=max(args.topk, 6))
            relaxed = True
        hits.sort(key=lambda h: -h["score"])
        matched.append((q, expect, hits, relaxed))

    # 章群：同一篇里的引文多半集中在同一章，落单的那条值得人看一眼
    from collections import Counter
    chapters = Counter(h[0]["chapter"] for _, _, h, _ in matched if h and h[0].get("chapter"))
    majority = None
    if len(matched) >= 4 and chapters:
        name, n = chapters.most_common(1)[0]
        majority = (name, n / len(matched))

    rows = []
    for q, expect, hits, relaxed in matched:
        top = hits[0] if hits else None
        margin = (top["score"] - hits[1]["score"]) if len(hits) > 1 else 1.0
        para_hit = locate_paragraph(paras, top, top["vol"]) if (top and paras) else None
        para_note = suspect(top, para_hit, q["text"]) if top else ""
        level, why = grade(top, margin, expect, top["numeric"] if top else "",
                           majority, relaxed, para_note)
        ours = ""
        if q["block"] is not None and q["block"] < len(tgt_blocks):
            para = re.sub(r"\s+", " ", tgt_blocks[q["block"]])
            zh = (top["zh"] if top else "") or ""
            ours = closest_sentence(para, zh) or quoted_in(para)
            if not ours and q["kind"] == "block":
                ours = tail_sentences(para)
        # 同章同页的候选等于同一个位置，列出来只是噪声
        alts = [h for h in hits[1:]
                if top and (h["page"], h["chapter"]) != (top["page"], top["chapter"])][:2]
        rows.append({
            "序号": len(rows) + 1,
            "形态": "整段" if q["kind"] == "block" else "引号内",
            "原文": q["text"],
            "引用串": q["citation"],
            "引用年份": q["year"],
            "锚定": "放宽" if relaxed else ("按卷" if (args.anchor == "vol" and expect) else "全库"),
            "应属卷": expect,
            "匹配卷": top["vol"] if top else "",
            "章": top["chapter"] if top else "",
            "页": top["page"] if top else "",
            "可信度": level,
            "score": top["score"] if top else "",
            "coverage": top["coverage"] if top else "",
            "候选间距": round(margin, 3),
            "数字核对": top["numeric"] if top else "",
            "引擎提示": (top["warn"] if top else "") or "",
            "判定理由": why,
            "备选": "；".join(f"第 {h['vol']} 卷 {h['chapter']} p.{h['page']}（{h['score']}）"
                             for h in alts),
            "文集译文": (top["zh"] if top else "") or "",
            "段落定位": (f'{para_hit["doc"]} 第{para_hit["i"]}段' if para_hit else "未定位"),
            "疑点": para_note,
            "段落正文": mark_paragraph(para_hit, top) if top else "",
            "裁句提示": trim_hint(q["text"], (top["zh"] if top else "") or ""),
            "本译文段": ours,
        })

    out = args.out or os.path.splitext(args.source)[0] + "_马恩引文.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    if args.md:
        L = ["# 马恩引文对照", "",
             f"原文：`{os.path.abspath(args.source)}`  ",
             f"共 {len(rows)} 条；"
             f"高 {sum(r['可信度'] == '高' for r in rows)}、"
             f"中 {sum(r['可信度'] == '中' for r in rows)}、"
             f"低 {sum(r['可信度'] == '低' for r in rows)}、"
             f"无匹配 {sum(r['可信度'] == '无匹配' for r in rows)}。", "",
             "**分数低不等于配错。** 作者引的是 Penguin 版，文集底本是 MECW，措辞有出入，"
             "正确匹配的 score 也常在 0.2—0.5；真正管用的是卷次对不对、候选之间分不分得开、"
             "以及引文里的数字在中文里找不找得到。", ""]
        for r in rows:
            L.append(f"## {r['序号']}. {r['引用串']} · {r['可信度']}"
                     + (f"（{r['判定理由']}）" if r["判定理由"] else ""))
            L.append("")
            L.append(f"- 原文：{r['原文'][:160]}")
            if r["匹配卷"]:
                L.append(f"- 匹配：第 {r['匹配卷']} 卷 · {r['章']} · p.{r['页']}"
                         f"（score {r['score']}，间距 {r['候选间距']}，数字 {r['数字核对']}）")
            else:
                L.append("- 匹配：无")
            if r["文集译文"]:
                L.append(f"- 文集译文：{r['文集译文']}")
            if r["本译文段"]:
                L.append(f"- 本译文：{r['本译文段']}")
            L.append("")
        open(args.md, "w", encoding="utf-8").write("\n".join(L) + "\n")

    hi = sum(r["可信度"] == "高" for r in rows)
    mid = sum(r["可信度"] == "中" for r in rows)
    lo = sum(r["可信度"] in ("低", "无匹配") for r in rows)
    print(f"马恩引文 {len(rows)} 条：高 {hi} / 中 {mid} / 需人工 {lo}")
    print(f"已写出 {out}")
    if lo:
        print("\n需人工核对：")
        for r in rows:
            if r["可信度"] in ("低", "无匹配"):
                print(f"  {r['序号']}. {r['引用串']} {r['判定理由']}：{r['原文'][:50]}…")


if __name__ == "__main__":
    main()
