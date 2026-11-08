"""第 10 卷（书信选编）映射：按「日期 + 发信人」归并。

中文书信标题形如「N.马克思致阿尔诺德·卢格」，日期在正文首行的日期行里；
英文侧 MECW 38—50 的标题是「Letter to <收信人>, <Month D, YYYY>」，
`author` 字段就是发信人。两边都是按时间编排的，所以日期是最好的锚。

产出追加进 index/works_resolved.json（vol=10），之后 build_works.py 10 直接可用。
"""
import os, re, json, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MON = {m: i + 1 for i, m in enumerate(
    "January February March April May June July August September October November December".split())}
CN_MON = {m: i + 1 for i, m in enumerate("一二三四五六七八九十".split())}


def parse_en_date(written):
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})", written or "")
    if m and m.group(2) in MON:
        return int(m.group(3)), MON[m.group(2)], int(m.group(1))
    m = re.search(r"([A-Z][a-z]+)\s+(\d{4})", written or "")      # 只有年月
    if m and m.group(1) in MON:
        return int(m.group(2)), MON[m.group(1)], None
    return None


def main():
    mea10 = json.load(open(os.path.join(ROOT, "index/mea10_dates.json"), encoding="utf-8"))
    en = [json.loads(l) for l in
          open(os.path.join(ROOT, "index/mecw_titles.jsonl"), encoding="utf-8")
          if json.loads(l)["vol"] >= 38]

    # 英文按日期建索引
    by_date, by_ym = {}, {}
    for r in en:
        if not (r["title"] or "").lower().startswith("letter"):
            continue
        d = parse_en_date(r["written"])
        if not d:
            continue
        y, m, dd = d
        if dd:
            by_date.setdefault((y, m, dd), []).append(r)
        by_ym.setdefault((y, m), []).append(r)

    zh_c = {}
    for line in open(os.path.join(ROOT, "corpus/mea10.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        if r["kind"] == "para":
            zh_c.setdefault(r["doc"], []).append(r["text"])

    resolved = json.load(open(os.path.join(ROOT, "index/works_resolved.json"), encoding="utf-8"))
    # 清掉上一轮的书信条目，避免叠加
    resolved = {k: v for k, v in resolved.items() if not k.startswith("10:")}

    hit = miss = 0
    for r in mea10:
        if not r.get("y"):
            continue
        key = (r["y"], r["m"], r["d"])
        cands = by_date.get(key) or by_ym.get((r["y"], r["m"])) or []
        if not cands:
            miss += 1
            continue
        ztxt = "".join(zh_c.get(r["file"], []))
        # 同日多封：用发信人 + 长度比挑
        sender_cn = "恩格斯" if "恩格斯致" in r["title"] else "马克思"
        want_en = "Friedrich Engels" if sender_cn == "恩格斯" else "Karl Marx"
        scored = []
        for c in cands:
            s = 0.0
            if want_en.lower() in (c["author"] or "").lower():
                s += 1.0
            ratio = len(ztxt) / max(1, len(c["title"]) * 30)
            s += 1.0 if 0.1 <= ratio <= 3 else 0.0
            scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        best = scored[0][1]
        resolved[f"10:{r['file']}"] = {
            "vol": 10, "zh": r["file"], "en": [best["file"]],
            "how": f"日期{key}", "note": f"{sender_cn}致；{r['y']}-{r['m']}-{r['d']}",
        }
        hit += 1

    with open(os.path.join(ROOT, "index/works_resolved.json"), "w", encoding="utf-8") as f:
        json.dump(resolved, f, ensure_ascii=False, indent=1)
    print(f"书信映射：命中 {hit}，未命中 {miss}（共 {len(mea10)} 封）")


if __name__ == "__main__":
    main()
