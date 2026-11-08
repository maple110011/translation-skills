"""把 works.csv 里的人工篇名，解析成具体的 MECW 文件。

支持三种写法
------------
T:某段标题       在"该卷允许的 MECW 卷"里按标题子串查找（大小写不敏感）
T:a > b          先找标题含 a 的，再在其中挑含 b 的（用于 Introduction 这类重名）
R:卷:起-止       直接指定文件号区间，如 R:4:02-12
L:文件,文件     直接列出文件名，如 L:MECW23-002.html,MECW23-055.html
P:卷-文件:起-止  指定单个文件的段落区间，如 P:27-036:73-113
                 （语料仓库把多篇序跋塞进同一个 HTML 时只能这样切）

解析结果写入 index/works_resolved.json，并打印需要人工确认的条目。
"""
import os, re, json, csv, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

ALLOW = {
    1: {3, 4, 5, 6, 7, 9},
    2: {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16},
    3: {18, 19, 20, 21, 22, 23, 24},
    4: {25, 26, 27},
    8: {28, 29, 30, 31, 32, 33, 34},
    10: set(range(38, 51)),
}


def load_index():
    return [json.loads(l) for l in open(os.path.join(ROOT, "index/mecw_titles.jsonl"),
                                        encoding="utf-8")]


def num(fn):
    return int(re.search(r"-(\d+)\.html$", fn).group(1))


STOPW = set("the of and a an in on to for by with from as is are be at it its".split())


def toks(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return [w for w in s.split() if w and w not in STOPW]


def fuzzy(spec, pool):
    """按查询词在标题里的覆盖率打分；返回 [(score, rec)]，取前几名。"""
    q = toks(spec)
    if not q:
        return []
    out = []
    for r in pool:
        t = set(toks(r["title"])) | set(toks(r["h1"]))
        if not t:
            continue
        hit = sum(1 for w in q if w in t)
        # 长词权重高一点，「china」这种太泛的词不要喧宾夺主
        wsum = sum(1.0 for w in q)
        score = sum(1.0 for w in q if w in t) / max(wsum, 1e-9)
        if hit:
            out.append((score, r))
    out.sort(key=lambda x: (-x[0], x[1]["vol"], x[1]["file"]))
    return out


def resolve(spec, vol, idx):
    allow = ALLOW.get(vol, set())
    pool = [r for r in idx if r["vol"] in allow]
    spec = spec.strip()
    zs = re.search(r"@z=(\d+)\s*$", spec)
    if zs:
        spec = spec[:zs.start()].strip()

    m = re.fullmatch(r"R:(\d+):(\d+)-(\d+)", spec)
    if m:
        v, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return [r["file"] for r in idx if r["vol"] == v and a <= num(r["file"]) <= b], "range"

    if spec.upper().startswith("X:"):
        return [], f"底本缺失：{spec[2:].strip()}"

    if spec.upper().startswith("L:"):
        fs = [x.strip() for x in spec[2:].split(",") if x.strip()]
        return fs, "list" if fs else "未命中: 空列表"

    # 直接写文件名（可能是多个），也认
    if re.fullmatch(r"MECW\d+-\d+\.html(\s*,\s*MECW\d+-\d+\.html)*", spec):
        fs = [x.strip() for x in spec.split(",")]
        return fs, "list" if len(fs) > 1 else "ok"

    m = re.fullmatch(r"P:(\d+)-(\d+):(\d+)-(\d+)", spec)
    if m:
        v, f, a, b = (int(m.group(i)) for i in range(1, 5))
        return [f"MECW{v:02d}-{f:03d}.html"], f"range {a}-{b}"

    parts = [p.strip() for p in spec.split(">")]
    cand = pool
    for p in parts:
        if p.lower().startswith("t:"):
            p = p[2:].strip()
        hit = [r for r in cand if p.lower() in (r["title"] or "").lower()
               or p.lower() in (r["h1"] or "").lower()]
        if not hit:                       # 子串找不到就退回模糊匹配
            fz = fuzzy(p, cand)
            if not fz or fz[0][0] < 0.7:
                return [], f"未命中: {p}"
            top = fz[0][0]
            cand = [r for sc, r in fz if sc >= top - 1e-9]
            if len(cand) > 1:
                return [r["file"] for r in cand], f"模糊多义({len(cand)})"
            return [cand[0]["file"]], f"模糊({top:.2f})"
        cand = hit
    # 同名多篇：Economic & Philosophic Manuscripts 会分两个文件，全都要
    titles = {r["title"].lower() for r in cand}
    if len(titles) == 1 and len(cand) > 1:
        pass
    elif len(cand) > 1:
        # 按卷号+文件号排序，返回全部，但标记需确认
        cand = sorted(cand, key=lambda r: (r["vol"], num(r["file"])))
        return [r["file"] for r in cand], f"多义({len(cand)})"
    return [r["file"] for r in cand], "ok"


def main():
    idx = load_index()
    rows = list(csv.DictReader(open(os.path.join(ROOT, "works.csv"), encoding="utf-8-sig")))
    mea = {json.loads(l)["file"]: json.loads(l)
           for l in open(os.path.join(ROOT, "index/mea_titles.jsonl"), encoding="utf-8")}

    resolved, problems = {}, []
    for r in rows:
        vol = int(r["vol"])
        files, how = resolve(r["en"], vol, idx)
        item = {"vol": vol, "zh": r["zh"], "en": files,
                "how": how, "note": r.get("note", "")}
        m = re.fullmatch(r"P:(\d+)-(\d+):(\d+)-(\d+)", r["en"].strip())
        if m:
            item["range"] = [int(m.group(3)), int(m.group(4))]
        zm = re.search(r"@z=(\d+)\s*$", r["en"].strip())
        if zm:
            item["zh_from"] = int(zm.group(1))
            item["en"] = files
        resolved[f"{vol}:{r['zh']}"] = item
        if not files or how.startswith("未命中") or how.startswith("多义") or how.startswith("模糊多义"):
            problems.append((vol, r["zh"], r["en"], files, how))

    with open(os.path.join(ROOT, "index/works_resolved.json"), "w", encoding="utf-8") as f:
        json.dump(resolved, f, ensure_ascii=False, indent=1)

    ok = sum(1 for v in resolved.values() if v["en"] and v["how"] == "ok")
    print(f"共 {len(rows)} 条：唯一命中 {ok}，需确认 {len(problems)}\n")
    for vol, zh, spec, files, how in problems:
        t = mea.get(zh, {})
        print(f"  [卷{vol}] {zh}  ({t.get('title','')[:40]})")
        print(f"       规则 {spec}  → {files[:4]}  {how}")
        if how.startswith("未命中"):
            pool = [r for r in idx if r["vol"] in ALLOW.get(vol, set())]
            fz = fuzzy(spec[2:] if spec.lower().startswith("t:") else spec, pool)[:3]
            for sc, r in fz:
                print(f"        候选 {sc:.2f} {r['file']} {r['title'][:58]}")
    # 中文侧有哪些篇目没进映射（说明/索引除外）
    covered = {r["zh"] for r in rows}
    miss = [v for k, v in mea.items()
            if v["vol"] in ALLOW and v["vol"] != 10 and k not in covered
            and not re.search(r"说明|索引|目录|附录|凡例|注释", v["title"])]
    print(f"\n未纳入映射的中文篇目 {len(miss)} 篇：")
    for m in miss:
        print(f"  [卷{m['vol']}] {m['file']} 段{m['paras']:4d} 字{m['chars']:6d} {m['title'][:46]}")


if __name__ == "__main__":
    main()
