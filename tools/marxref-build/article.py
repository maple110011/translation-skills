"""文章级处理：一篇 Markdown 稿子里的英文马恩引文，逐条匹配中文译文并回填。

这是这套工具最主要的用法——译一篇论文时，稿子里十几处马恩引文要一并换成
《马克思恩格斯文集》的译文，并在原处补上出处。

    python article.py paper.md                      # 输出 paper.zh.md + 核对清单
    python article.py paper.md -o out.md --mode replace
    python article.py paper.md --report out/        # 报告与清单写到指定目录

两种模式
--------
annotate（默认）  保留英文原句，在后面追加中文与出处。适合「先看一遍再决定」。
replace           直接把英文引文换成中文译文 + 出处。适合定稿。

状态
----
ok        可以直接用
review    命中了但有可疑信号（未对齐 / 数字对不上 / 匹配度偏低），标【中译待核】
unmatched 没命中：多半是未收录于文集第 5—7 卷，或不是马恩引文。原文不动，只记进清单。

设计原则：**绝不静默替换**。所有拿不准的都留下可见标记与原因，人一眼能扫出来。
"""
import os, re, sys, csv, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quotes as Q

ART = "《马克思恩格斯文集》"


def cite_text(vol, page):
    if not vol:
        return ""
    return f"{ART}第{vol}卷" + (f"，第{page}页" if page else "（页码待核）")


def classify(m, min_ok=0.80, min_hit=0.55):
    """把一条匹配结果归成 ok / review / unmatched，并给出人话原因。"""
    if not m:
        return "unmatched", "未命中"
    if m["score"] < min_hit:
        return "unmatched", "未收录于文集第 5—7 卷，或非马恩引文"
    reasons = []
    if not m.get("zh"):
        reasons.append("未对齐到中文")
    if m.get("unaligned"):
        reasons.append("该句未对齐到中文")
    if m.get("numeric") == "mismatch":
        reasons.append("数字与中文句对不上")
    if m.get("nq", 99) < 4:
        reasons.append("引文过短")
    if m["score"] < min_ok:
        reasons.append(f"匹配度 {m['score']:.2f} 偏低")
    if reasons:
        return "review", "；".join(dict.fromkeys(reasons))
    return "ok", ""


def embed(m, status, reason, mode):
    """生成要插入（或替换）的文本片段。"""
    zh = (m.get("zh") or "").strip()
    cite = cite_text(m.get("vol"), m.get("page"))
    if mode == "replace":
        if status == "ok":
            return f"“{zh}”（{cite}）"
        return f"“{zh}”〔中译待核：{reason}；{cite}〕"
    if status == "ok":
        return f"【中译】“{zh}”（{cite}）"
    return f"【中译待核】“{zh}”（{reason}；{cite}）"


def process(md, engine, mode="annotate", min_ok=0.80, min_hit=0.55):
    """返回 (annotated_md, items, stats)。"""
    cands = Q.extract(md)
    cache = {}
    items = []

    for k, c in enumerate(cands):
        # 幂等：已经标过「中译」的位置跳过，避免跑两次插两遍
        tail = re.sub(r"^[\s>]+", "", md[c["end"]:c["end"] + 24])
        if tail.startswith(("【中译】", "【中译待核】")):
            continue

        if c["text"] in cache:
            m = cache[c["text"]]
        else:
            res = engine.match(c["text"], topk=1, min_score=0.10)
            m = res[0] if res else None
            cache[c["text"]] = m

        status, reason = classify(m, min_ok, min_hit)
        item = {
            "index": k + 1, "line": c["line"], "kind": c["kind"], "ci": k,
            "quote": c["text"], "citation_in_doc": c.get("citation"),
            "status": status, "reason": reason,
            "vol": m.get("vol") if m else None,
            "chapter": m.get("chapter") if m else None,
            "page": m.get("page") if m else None,
            "score": m.get("score") if m else None,
            "zh": (m.get("zh") or "") if m else "",
            "unaligned": bool(m.get("unaligned")) if m else None,
            "numeric": m.get("numeric") if m else None,
        }

        if status == "unmatched":
            # 分数低于门槛时那个"最佳候选"其实是噪声，留着会让人以为找到了
            item.update(zh="", vol=None, chapter=None, page=None)

        # 只有 ok / review 且确实拿到了中文才回填
        if status in ("ok", "review") and item["zh"]:
            item["insert"] = embed(m, status, reason, mode)
            if c["kind"] == "block":
                item["edit"] = (c["end"], c["end"], "\n> " + item["insert"])
            elif mode == "replace":
                item["edit"] = (c["start"], c["end"], item["insert"])
            else:
                item["edit"] = (c["end"], c["end"], " " + item["insert"])
        items.append(item)

    out = md
    edits = sorted([x["edit"] for x in items if x.get("edit")], key=lambda e: (-e[0], -e[1]))
    # 偏移互不重叠，从后往前拼即可
    for s, e, t in edits:
        out = out[:s] + t + out[e:]

    stats = {
        "quotes": len(cands),
        "ok": sum(1 for x in items if x["status"] == "ok"),
        "review": sum(1 for x in items if x["status"] == "review"),
        "unmatched": sum(1 for x in items if x["status"] == "unmatched"),
        "inserted": sum(1 for x in items if x.get("edit")),
    }
    return out, items, stats


def write_report(items, stats, outdir, stem="report"):
    os.makedirs(outdir, exist_ok=True)
    jp = os.path.join(outdir, f"{stem}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"stats": stats,
                   "items": [{k: v for k, v in x.items() if k != "edit"} for x in items]},
                  f, ensure_ascii=False, indent=1)
    cp = os.path.join(outdir, f"{stem}.csv")
    with open(cp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "状态", "行号", "英文引文", "中文译文", "卷", "页", "匹配度", "说明"])
        for x in items:
            w.writerow([x["index"], x["status"], x["line"], x["quote"], x["zh"],
                        x["vol"] or "", x["page"] or "",
                        f"{x['score']:.2f}" if x["score"] is not None else "",
                        x["reason"]])
    return jp, cp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="输出的 Markdown，默认 <input>.zh.md")
    ap.add_argument("--mode", choices=["annotate", "replace"], default="annotate")
    ap.add_argument("--report", default=None, help="报告目录，默认 <input>.report/")
    ap.add_argument("--min-ok", type=float, default=0.80)
    ap.add_argument("--min-hit", type=float, default=0.55)
    args = ap.parse_args()

    from engine import Engine
    eng = Engine()

    md = open(args.input, encoding="utf-8").read()
    out, items, stats = process(md, eng, mode=args.mode,
                                min_ok=args.min_ok, min_hit=args.min_hit)

    stem = re.sub(r"\.md$", "", args.input)
    op = args.output or stem + ".zh.md"
    open(op, "w", encoding="utf-8").write(out)
    jp, cp = write_report(items, stats, args.report or stem + ".report")

    print(f"\n抽出引文 {stats['quotes']} 条：ok {stats['ok']} / 待核 {stats['review']} / "
          f"未命中 {stats['unmatched']}，已回填 {stats['inserted']} 处")
    if args.mode == "replace":
        print("注意：replace 模式会删掉英文原句。约四分之一的中文句存在错位风险，"
              "且无标记可查，务必对着清单逐条核一遍再定稿。")
    print(f"输出：{op}")
    print(f"报告：{jp}")
    print(f"清单：{cp}")


if __name__ == "__main__":
    main()
