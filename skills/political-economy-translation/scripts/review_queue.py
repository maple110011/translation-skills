#!/usr/bin/env python3
"""Build the list of decisions a translator must not make silently.

Translation fails quietly in a few specific places, and they are not the same
kind of failure:

* A term the project glossary already fixed gets rendered differently three
  pages later. Mechanical — a script finds it.
* The source admits two readings and the Chinese has to pick one. Semantic —
  no script finds it, but the reader is entitled to know a choice was made.
* A word that looks like everyday vocabulary carries a theoretical load in this
  literature (`tension` 张力 not 紧张). Judgment.
* A term the glossary has never seen. Needs a decision before it is used twice.

So this script handles the mechanical half and reserves an explicit section for
the half that has to be written by hand. It does not pretend to review style.

Usage:
    python review_queue.py 原文.md 译文.md --glossary _work/x_术语.csv -o _work/x_待校对.md
    python review_queue.py 原文.md 译文.md --glossary *_术语.csv --manual _work/x_人工待校.csv
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z][A-Za-z\u00C0-\u024F'\-]*")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

STOP = set("""
the a an of and or in on at to for from by with without as is are was were be
been being this that these those it its their there here which who whom whose
what when where why how not no nor but if then than so such very more most less
least much many few both each every all any some other another same own only
also just even still yet already often usually always never can could may might
must should shall will would do does did done have has had having we our you
your they them he she his her one two three first second new old good bad
""".split())

SUFFIX = re.compile(r"(ism|ization|isation|ation|tion|ment|ness|ity|ence|ance)$")


FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)


def read(path):
    """Read a Markdown file without its YAML front matter.

    Metadata is not prose: counting it as a paragraph would inflate the source
    and hide a real gap in the translation.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    m = FRONT.match(text)
    return text[m.end():] if m else text


def paragraphs(text):
    """Prose paragraphs with their index, skipping code and display math."""
    out, buf, in_fence, in_math = [], [], False, False
    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            buf = []
            continue
        if in_fence:
            continue
        if in_math:
            if line.strip().startswith("$$"):
                in_math = False
            continue
        if line.strip().startswith("$$"):
            if buf:
                out.append(" ".join(buf))
                buf = []
            if line.strip().count("$$") < 2:
                in_math = True
            continue
        if not line.strip() or HEADING.match(line):
            if buf:
                out.append(" ".join(buf))
                buf = []
            continue
        buf.append(line.strip())
    if buf:
        out.append(" ".join(buf))
    return out


def load_glossary(path):
    rows = []
    if not path or not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            src = (r.get("src") or "").strip()
            dst = (r.get("dst") or "").strip()
            if not src or not dst:
                continue
            rows.append({
                "src": src,
                "dst": dst,
                "alt": (r.get("alt") or "").strip(),
                "status": (r.get("status") or "").strip(),
                "tier": (r.get("tier") or "").strip(),
                "confidence": (r.get("confidence") or "").strip(),
                "count": (r.get("count") or "").strip(),
                "note": (r.get("note") or "").strip(),
            })
    return rows


CITE_SPAN = re.compile(r"\([^()]{0,90}?(?:19|20)\d{2}[a-z]?[^()]{0,40}?\)")


def strip_cites(text):
    """去掉括号引用与参考文献段：那里的原文按规则 4 保持英文，不能拿来判术语缺失。"""
    body = re.split(r"^#{1,6}\s*(?:References|参考文献)\s*$", text, flags=re.M)[0]
    return CITE_SPAN.sub(" ", body)


def term_drift(src_text, tgt_text, glossary):
    """Glossary terms that appear in the running text but not as agreed.

    只有出现在正文（括号引用、参考文献之外）的术语才需要汉译。一个只在
    `(Foley 1990)` 里出现的姓氏，本来就不该在译文里变成中文，把它列进
    「约定译法未出现」是纯噪声。
    """
    prose = strip_cites(src_text)
    drift, cite_only = [], []
    for g in glossary:
        english = g["src"]
        hits = len(re.findall(r"\b" + re.escape(english) + r"\b", src_text, re.I))
        if not hits:
            continue
        prose_hits = len(re.findall(r"\b" + re.escape(english) + r"\b", prose, re.I))
        if prose_hits == 0:
            cite_only.append(g)
            continue
        used = tgt_text.count(g["dst"])
        alts = [a.strip() for a in re.split(r"[|/／]", g["alt"]) if a.strip()]
        alt_hits = {a: tgt_text.count(a) for a in alts if tgt_text.count(a)}
        if used == 0:
            # 译文按规则 4 把原词留在括号引用里（学者姓名、书名），不算混用异译。
            # 只在引用之外也保留英文，才算真的没译。
            in_tgt = re.search(r"\b" + re.escape(english) + r"\b", tgt_text, re.I)
            in_prose = re.search(r"\b" + re.escape(english) + r"\b", strip_cites(tgt_text), re.I)
            if in_tgt and not in_prose:
                continue
            drift.append({**g, "hits": prose_hits, "used": 0, "alts": alt_hits,
                          "kind": "约定译法未出现"})
        elif alt_hits:
            drift.append({**g, "hits": prose_hits, "used": used, "alts": alt_hits,
                          "kind": "同时用了别的写法"})
    return drift, cite_only


MATH_JUNK = re.compile(r"\b(math(bf|cal|rm|it)|alpha|beta|omega|lambda|sigma|nu)\b")
SINGLE_LETTER = re.compile(r"\b[a-z]\b")


def singular(phrase):
    if phrase.endswith("ies") and len(phrase) > 5:
        return phrase[:-3] + "y"
    if phrase.endswith("s") and not phrase.endswith(("ss", "us", "is", "as", "os")):
        return phrase[:-1]
    return phrase


def _context(text, phrase, width=34):
    """候选词第一次出现时的上下文，供人判断这是不是个术语。"""
    m = re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I)
    if not m:
        return ""
    left = text[max(0, m.start() - width):m.start()]
    right = text[m.end():m.end() + width]
    left = re.sub(r"\s+", " ", left).strip()
    right = re.sub(r"\s+", " ", right).strip()
    return f"…{left} **{text[m.start():m.end()]}** {right}…"


def _clip(s, n=60):
    """清单里引用原文/译文都要截断，否则一条占满一屏，人就不看了。"""
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip("，、；：,;:") + "…"


def _overlap(a, b):
    """两段中文的字面重合度（2-gram Jaccard）。只作"改不改"的粗尺度参考：
    同义改写会低，照抄会高，不追求精确。"""
    a = re.sub(r"\s+", "", a or "")
    b = re.sub(r"\s+", "", b or "")
    if len(a) < 8 or len(b) < 8:
        return None
    ga = {a[i:i + 2] for i in range(len(a) - 1)}
    gb = {b[i:i + 2] for i in range(len(b) - 1)}
    # 按较短一方归一：文集常是整句、我们的摘录只是引文那截，用并集算会一律虚低
    return len(ga & gb) / min(len(ga), len(gb)) if (ga and gb) else None


def new_terms(src_text, glossary, min_count=4, top=40):
    """Recurring multi-word units the glossary has never seen.

    只给证据，不给判断：每条附一次出现的上下文，译法由译者（或 agent）补。
    """
    known = {g["src"].lower(): g["dst"] for g in glossary}
    # 公式、图片路径、HTML 表格先清掉：它们会被切成 begin/array/png 这类假术语
    text = re.sub(r"\$\$.+?\$\$", " ", src_text, flags=re.S)
    text = re.sub(r"(?<!\\)\$.+?(?<!\\)\$", " ", text, flags=re.S)
    text = re.sub(r"<table>.*?</table>", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"^\s*(?:Figure|图)\s*\d+\.?.*$", " ", text, flags=re.M)
    # 参考文献整段保留原文（规则 4），不参与术语挖掘
    text = re.split(r"^#{1,6}\s*(?:References|参考文献)\s*$", text, flags=re.M)[0]

    counts = Counter()
    # 只在句内取 n-gram：跨逗号/分号的窗口会拼出 `capital productive` 这种假术语
    for seg in re.split(r"[.;:,!?()\[\]\u2014\u2013\"\u201c\u201d]", text):
        toks = [w.lower() for w in LATIN.findall(seg)]
        for n in (2, 3):
            for i in range(len(toks) - n + 1):
                span = toks[i:i + n]
                if span[0] in STOP or span[-1] in STOP:
                    continue
                if any(t in STOP for t in span[1:-1]):
                    continue
                if all(len(t) < 4 for t in span):
                    continue
                counts[" ".join(span)] += 1
    out = []
    for phrase, n in counts.most_common():
        if n < min_count:
            break
        if phrase in known or singular(phrase) in known:
            continue
        # A longer form of a term already in the table (`transformation problem
        # debates`) is a variant, not a new term.
        if any(phrase.startswith(k + " ") or phrase.endswith(" " + k)
               or k.startswith(phrase + " ") for k in known):
            continue
        if MATH_JUNK.search(phrase) or SINGLE_LETTER.search(phrase):
            continue
        # Structural prepositions mark a sentence fragment rather than a term:
        # `relationship between` is grammar, `rate of profit` is a term.
        if re.search(r"\b(between|among|within|across|through|during)\b", phrase):
            continue
        if all(t in STOP for t in phrase.split()):
            continue
        out.append({"src": phrase, "count": n, "context": _context(text, phrase),
                    "suggest": known.get(phrase, "") or known.get(singular(phrase), ""),
                    "why": ""})
        if len(out) >= top:
            break
    return out



def low_confidence(glossary):
    """Entries the table itself flags as unsettled.

    Only the status column counts. Mining confidence (`中`/`低`) means the
    evidence for that rendering is thin, which is worth showing, but it is not
    the same thing as the table having left the question open.
    """
    return [g for g in glossary
            if any(k in g["status"] for k in ("待核", "待裁决", "待人工"))]


def thin_evidence(glossary):
    """Entries whose rendering rests on few observations."""
    return [g for g in glossary if g["confidence"] in ("中", "低")]


MANUAL_COLS = ["位置", "类型", "原文", "译法A", "译法B", "建议", "理由"]


def load_manual(path):
    """Read the hand-written queue, tolerating a sheet saved without a header.

    People paste these into Excel or append rows with a script; both produce
    files whose first line may not be the header. Falling back to positional
    columns is more useful than silently rendering a table of blanks.
    """
    if not path or not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        raw = [[(c or "").lstrip("\ufeff").strip() for c in row]
               for row in csv.reader(fh)]
    raw = [r for r in raw if any(r)]
    if not raw:
        return []
    header = raw[0]
    if any(h in header for h in ("位置", "类型", "原文")):
        body = raw[1:]
    else:
        header = MANUAL_COLS
        body = raw
    out = []
    for row in body:
        if not any(row):
            continue
        out.append({h: (row[i] if i < len(row) else "") for i, h in enumerate(header)})
    return out


MANUAL_TEMPLATE = """位置,类型,原文,译法A,译法B,建议,理由
"""
MANUAL_HEADER = "位置,类型,原文,译法A,译法B,建议,理由"


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成待人工校对的清单")
    ap.add_argument("source", nargs="?", help="原文 Markdown")
    ap.add_argument("target", nargs="?", help="译文 Markdown")
    ap.add_argument("--glossary", default="", help="项目术语表 CSV（可逗号分隔多个）")
    ap.add_argument("--manual", default="", help="人工待校 CSV（翻译时随手记的）")
    ap.add_argument("-o", "--out", default="", help="输出 Markdown 路径")
    ap.add_argument("--min-count", type=int, default=4, help="新术语候选的最低频次")
    ap.add_argument("--suggest", default="",
                    help="候选术语的译法建议 CSV（src,dst）：agent 跑完后补这一列")
    ap.add_argument("--marx", default="",
                    help="marx_quotes.py 产出的马恩引文 CSV；有它就在清单里加一节")
    ap.add_argument("--marx-note", default="",
                    help="CSV（引用串,备注）：对可疑引文的人工核查结论，附在该条后面")
    ap.add_argument("--marx-adopt", default="",
                    help="引文采用表（序号,引用串,采用,原文句,说明），用来标注哪些已改用文集译文")
    ap.add_argument("--resolved", default="",
                    help="已决定清单 CSV（键,动作,说明）：其中的条目不再出现在新清单里")
    ap.add_argument("--init-manual", nargs="?", const="", metavar="PATH",
                    help="生成空白的人工待校 CSV 模板后退出；可给路径，默认 人工待校.csv")
    args = ap.parse_args(argv)

    if args.init_manual is not None:
        path = args.init_manual or args.manual or "人工待校.csv"
        if os.path.exists(path):
            sys.exit(f"{path} 已存在，未覆盖。")
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(MANUAL_TEMPLATE)
        print(f"已创建 {path}\n翻译时逐行填写，交付前用 --manual {path} 传入。")
        return

    if not args.source or not args.target:
        ap.error("需要原文与译文两个路径（除非用 --init-manual 只建模板）。")

    src_text, tgt_text = read(args.source), read(args.target)
    glossary = []
    for p in [x for x in args.glossary.split(",") if x.strip()]:
        glossary.extend(load_glossary(p.strip()))

    drift, cite_only = term_drift(src_text, tgt_text, glossary)
    # `effort` and `labor effort` both resolving to the same rendering would be
    # two rows for one decision; keep the longer source form.
    by_dst = {}
    for d in drift:
        by_dst.setdefault(d["dst"], []).append(d)
    deduped = []
    for dst, group in by_dst.items():
        deduped.append(max(group, key=lambda x: len(x["src"])) if len(group) > 1 else group[0])
    drift = sorted(deduped, key=lambda x: -x["hits"])

    fresh = new_terms(src_text, glossary, args.min_count)
    if args.suggest and os.path.exists(args.suggest):
        tips = {}
        with open(args.suggest, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r.get("src") or "").strip().lower()
                if k:
                    tips[k] = ((r.get("dst") or "").strip(), (r.get("note") or "").strip())
        for f in fresh:
            hit = tips.get(f["src"].lower())
            if hit:
                f["suggest"], f["why"] = hit

    resolved = set()
    if args.resolved and os.path.exists(args.resolved):
        with open(args.resolved, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r.get("键") or "").strip().lower()
                if k:
                    resolved.add(k)

    marx_note = {}
    if args.marx_note and os.path.exists(args.marx_note):
        with open(args.marx_note, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r.get("引用串") or "").strip()
                if k:
                    marx_note[k] = (r.get("备注") or "").strip()

    adopted = {}
    if args.marx_adopt and os.path.exists(args.marx_adopt):
        with open(args.marx_adopt, "r", encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r.get("序号") or "").strip()
                if k:
                    adopted[k] = r

    marx = []
    if args.marx and os.path.exists(args.marx):
        with open(args.marx, "r", encoding="utf-8-sig", newline="") as fh:
            marx = list(csv.DictReader(fh))

    manual = [m for m in load_manual(args.manual)
              if ("manual:" + (m.get("原文") or "").strip().lower()) not in resolved]
    drift = [d for d in drift if ("term:" + d["src"].lower()) not in resolved]
    fresh = [f for f in fresh if ("candidate:" + f["src"].lower()) not in resolved]
    shaky = low_confidence(glossary)
    thin = thin_evidence(glossary)

    out = args.out or os.path.splitext(args.target)[0] + "_待校对.md"
    L = []
    L += [
        "# 待校对清单",
        "",
        f"原文：`{os.path.abspath(args.source)}`  ",
        f"译文：`{os.path.abspath(args.target)}`  ",
        f"术语表：{len(glossary)} 条",
        "",
        "**怎么看**：第一节、第四节、第五节要你说话。在「你的意见：」后面写一句就行，"
        "写「按建议」「用 A」「照原文保留」都可以，不必写完整句子；不想定的留空，我按建议处理。"
        "你写完，我负责改译文、回填术语表、重跑校验。",
        "",
        "---",
        "",
        f"## 一、要你定的（{len(manual)} 条）",
        "",
    ]
    if manual:
        for i, m in enumerate(manual, 1):
            pos = (m.get("位置") or "").strip()
            typ = (m.get("类型") or "").strip()
            en = (m.get("原文") or "").strip()
            a_ = (m.get("译法A") or "").strip()
            b_ = (m.get("译法B") or "").strip()
            rec = (m.get("建议") or "").strip()
            why = (m.get("理由") or "").strip()
            L.append(f"### R{i}. {en}  ·  {typ}")
            if pos:
                L.append(f"- 位置：{pos}")
            if a_ or b_:
                opts = " ／ ".join(x for x in (a_, b_) if x)
                L.append(f"- 备选：{opts}")
            if rec:
                L.append(f"- 我的建议：{rec}" + (f"（{why}）" if why else ""))
            elif why:
                L.append(f"- 说明：{why}")
            L += ["", "> 你的意见：", ""]
    else:
        L += ["没有需要你定的问题。", ""]

    L += [
        "---",
        "",
        f"## 二、我可以直接改的（{len(drift)} 条）",
        "",
        "术语表里定了译法，译文没用上。没意见就按行尾写法改，不用回复；"
        "觉得不该改，就在该条后面写一句。",
        "",
    ]
    if drift:
        for i, d in enumerate(drift, 1):
            actual = "、".join(f"{k}×{v}" for k, v in d["alts"].items()) or "未出现"
            L.append(f"{i}. **{d['src']}** → 应作「{d['dst']}」，译文现用：{actual}"
                     f"（原文 {d['hits']} 处）")
        L.append("")
    else:
        L += ["无。", ""]

    L += [
        f"### 只在括号引用里出现、不需要处理（{len(cite_only)} 条）",
        "",
    ]
    if cite_only:
        names = "、".join(g["src"] for g in cite_only[:14])
        more = f" 等 {len(cite_only)} 条" if len(cite_only) > 14 else ""
        L += [f"{names}{more}。按规则 4，括号引用逐字保留，这些词本来就不该在译文里变成中文，"
              "列出来只是噪声，已从上面的清单剔除。", ""]
    else:
        L += ["无。", ""]

    L += [
        "---",
        "",
        f"## 三、原文疑点（{sum(1 for m in manual if (m.get('类型') or '') == '原文疑误')} 条，已并入第一节）",
        "",
        "原文本身有问题的地方都列在第一节点名了。我不替作者圆场，也不擅自改。",
        "",
        "---",
        "",
        f"## 四、候选术语（{len(fresh)} 条）",
        "",
        "原文反复出现、术语表里没有的词。每条附一次出现的上下文，以及我的建议译法。"
        "只挑「译错会改变论证」的收进表——影响因果方向、影响数量关系、有学派标记功能的。"
        "其余留空即可，我会按上下文处理，不硬定译法。",
        "",
    ]
    if fresh:
        for i, f in enumerate(fresh, 1):
            L.append(f"### T{i}. {f['src']}（{f['count']} 次）")
            if f["context"]:
                L.append(f"- 上下文：{f['context']}")
            if f.get("suggest") and f["suggest"] not in ("不收", "-"):
                L.append(f"- 我的建议：{f['suggest']}" + (f"（{f['why']}）" if f.get("why") else ""))
            elif f.get("suggest"):
                L.append(f"- 我的建议：不必收" + (f"——{f['why']}" if f.get("why") else ""))
            else:
                L.append("- 我的建议：（待补）")
            L += ["", "> 你的意见：", ""]
    else:
        L += ["无。", ""]

    if marx:
        hi = sum(r.get("可信度") == "高" for r in marx)
        mid = sum(r.get("可信度") == "中" for r in marx)
        lo = [r for r in marx if r.get("可信度") in ("低", "无匹配")]
        good = [r for r in marx if r.get("可信度") in ("高", "中")]
        L += ["---", "", f"## 五、马恩引文（{len(marx)} 条，{len(lo)} 条需人工）", "",
              f"按引用年份锚定卷次后对到《马克思恩格斯文集》：高 {hi}、中 {mid}、需人工 {len(lo)}。",
              "",
              "作者引的是 Penguin 版，文集底本 MECW，两者是独立的英译本：句子措辞不同，"
              "但篇章结构同据恩格斯德文第四版，章号一一对应。所以这里不按分数划可信度，"
              "看四样与措辞无关的证据——卷次对不对、同篇引文是否集中在同一章、"
              "前两名候选分不分得开、引文里的数字对不对得上。", ""]
        if good:
            n_ad = sum(1 for r in good if (r.get("序号") or "") in adopted)
            L += ["### 5.1 引文译文：能对上的几条", "",
                  "引文默认直接用文集译文，不另译。"
                  + (f"其中 {n_ad} 条已按裁定的范围替换，其余未动。" if adopted else ""),
                  "引擎返回的文集译文常是跨句合并的结果，比引文本身长，所以每条都按引文实际覆盖的范围裁过——"
                  "引文是一个从句，就只取对应的那半句。", ""]
            for r in good:
                a = adopted.get(r.get("序号") or "")
                done = a is not None
                # 已采用的，原译要从采用表里取：引文 CSV 是在改完之后重跑的，
                # 它的「本译文段」已经是新句子，拿它对照等于自己跟自己比。
                orig = (a.get("原文句") if done else "") or r.get("本译文段") or ""
                ov = _overlap(r.get("文集译文"), orig)
                tag = "" if ov is None else f"，字面重合 {ov:.0%}"
                L.append(f"- **{r.get('引用串', '')}**（第 {r.get('匹配卷', '')} 卷 p.{r.get('页', '')}{tag}）"
                         + ("　已采用" if done else ""))
                L.append(f"  - 文集：{_clip(r.get('文集译文'), 80)}")
                L.append(f"  - 原译：{_clip(orig, 80) or '（引文表未抓到对应句）'}")
                if done and (a.get("说明") or "").strip():
                    L.append(f"  - 裁法：{_clip(a.get('说明'), 60)}")
            L += ["", "如某处不该改（文集译文在这个语境里读不通、或引文其实没覆盖那么宽），"
                  "报个序号，我换回原译。", "",
                  "> 你的意见：", ""]
        if lo:
            L += [f"### 5.2 需要人工核对的 {len(lo)} 条", "",
                  "引文是 Penguin 版、底本是 MECW，两套译本措辞不同，score 本来就不高，"
                  "所以它只作参考。判断办法很简单：看下面那行文集译文与我们的译法是不是讲的同一件事——"
                  "对得上就写「确认」，对不上就说按哪一处改。", ""]
            for i, r in enumerate(lo, 1):
                L += [f"#### M{i}. {r.get('引用串', '')}", ""]
                L.append(f"- 原文：{_clip(r.get('原文', ''), 150)}")
                L.append(f"- 现在的译文：{_clip(r.get('本译文段', ''), 120) or '（未定位到）'}")
                if r.get("匹配卷"):
                    L.append(f"- 引擎给的：第 {r['匹配卷']} 卷 · {r.get('章', '')} · p.{r.get('页', '')}"
                             f"（score {r.get('score', '')}，间距 {r.get('候选间距', '')}）")
                if r.get("备选"):
                    L.append(f"- 另有候选：{r['备选']}")
                if r.get("文集译文"):
                    L.append(f"- 它配的文集译文：{_clip(r.get('文集译文', ''), 120)}")
                L.append(f"- 为什么标出来：{r.get('判定理由', '')}")
                note = marx_note.get((r.get("引用串") or "").strip(), "")
                if note:
                    L.append(f"- 我的核查：{note}")
                L += ["", "> 你的意见：", ""]
        else:
            L += ["没有需要人工核对的引文。", ""]

    if shaky:
        L += ["---", "", f"### 附：术语表里本身待定的条目（{len(shaky)} 条）", ""]
        for g in shaky[:20]:
            L.append(f"- {g['src']} → {g['dst']}（{g['status']}）")
        if len(shaky) > 20:
            L.append(f"- 另有 {len(shaky) - 20} 条，见术语表 `status` 列。")
        L += [""]

    L += [
        "---",
        "",
        "## 你写完之后",
        "",
        "把这份文件留着，说一声「按清单改」。我会：读你的意见 → 更新术语表与译文 → "
        "重跑公式归一与结构对账 → 已决条目记进 `已决定.csv`，下版清单不再出现。",
    ]

    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print(f"要你定 {len(manual)} 条 | 可直接改 {len(drift)} 条 | "
          f"引用内免处理 {len(cite_only)} 条 | 候选术语 {len(fresh)} 条"
          + (f" | 马恩引文需人工 {sum(1 for r in marx if r.get('可信度') in ('低', '无匹配'))} 条" if marx else ""))
    print(f"已写出 {out}")


if __name__ == "__main__":
    main()
