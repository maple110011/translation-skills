#!/usr/bin/env python3
"""Build the list of decisions a translator must not make silently.

Translation fails quietly in a few specific places, and they are not the same
kind of failure:

* A formula came out one character different from the source. Mechanical — a
  script finds it, but only a human can say whether `\\le` should have stayed
  `\\le`.
* A term the project glossary already fixed gets rendered differently three
  pages later. Mechanical — a script finds it.
* The source admits two readings and the Chinese has to pick one. Semantic —
  no script finds it, but the reader is entitled to know a choice was made.
* A symbol used all over the paper is missing from the 符号一览. Mechanical
  for the inventory, judgment for the meaning.

So this script handles the mechanical half and reserves an explicit section for
the half that has to be written by hand. It does not pretend to review style —
this workflow does not polish.

Usage:
    python review_queue.py 原文.md 译文.md --glossary _work/x_术语.csv -o _work/x_待校对.md
    python review_queue.py 原文.md 译文.md --glossary *.csv --math _work/公式差异.csv \\
        --notation _work/符号缺漏.csv --manual _work/x_人工待校.csv
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter

try:                                    # console may be cp936
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

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
                "kind": (r.get("kind") or "").strip(),
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
        # kind=keep / dst=@keep 是「保留英文原文」的裁定，不是漏译。
        # 反向检查（英文串必须在、alt 里的中文写法必须不在）由
        # fidelity_check.py 负责，这里只负责别把它误报成「约定译法未出现」。
        if g.get("kind") == "keep" or g["dst"].strip().lower() in ("@keep", "keep"):
            continue
        english = g["src"]
        hits = len(re.findall(r"\b" + re.escape(english) + r"\b", src_text, re.I))
        if not hits:
            continue
        prose_hits = len(re.findall(r"\b" + re.escape(english) + r"\b", prose, re.I))
        if prose_hits == 0:
            cite_only.append(g)
            continue
        # 中文形态：定下的译法是「局部化」时，「局部化的」「局部化地」都算用了它。
        # 不这样处理，一张表会天天报「约定译法未出现」。
        core = re.sub(r"[的地得]$", "", g["dst"])
        used = len(re.findall(re.escape(core) + r"[的地得]?", tgt_text))
        alts = [a.strip() for a in re.split(r"[|/／]", g["alt"]) if a.strip()]
        # 备选写法若只是主译法的形态变化（`事后` / `事后的`），不算「同时用了别的写法」。
        alts = [a for a in alts if a not in g["dst"] and g["dst"] not in a]
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
        # `müller et`、`smith et al` 这类是引用里的人名碎片，不是术语
        if re.search(r"\bet\s+al\b|\bet$|\bal$", phrase):
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
    ap.add_argument("--math", default="",
                    help="math_fidelity.py 产出的公式差异 CSV；有它就在清单里加一节")
    ap.add_argument("--notation", default="",
                    help="notation.py check 产出的符号缺漏 CSV；有它就在清单里加一节")
    ap.add_argument("--figures", default="",
                    help="figures.py audit 产出的图目录 CSV；有它就在清单里加一节")
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

    math_rows, notation_rows = [], []
    if args.math and os.path.exists(args.math):
        with open(args.math, "r", encoding="utf-8-sig", newline="") as fh:
            math_rows = [r for r in csv.DictReader(fh) if (r.get("类型") or "") not in ("", "一致")]
        math_rows = [r for r in math_rows
                     if ("math:" + (r.get("序号") or "")) not in resolved]
    fig_rows = []
    if args.figures and os.path.exists(args.figures):
        with open(args.figures, "r", encoding="utf-8-sig", newline="") as fh:
            fig_rows = [r for r in csv.DictReader(fh) if (r.get("说明") or "").strip()]
    if args.notation and os.path.exists(args.notation):
        with open(args.notation, "r", encoding="utf-8-sig", newline="") as fh:
            notation_rows = [r for r in csv.DictReader(fh) if (r.get("符号") or "").strip()]
        notation_rows = [r for r in notation_rows
                         if ("notation:" + (r.get("符号") or "")) not in resolved]

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
        "**怎么看**：第一、二、三、四、六节要你说话。在「你的意见：」后面写一句就行，"
        "写「按建议」「用 A」「照原文保留」「改回原式」都可以，不必写完整句子；"
        "不想定的留空，我按建议处理。你写完，我负责改译文、回填术语表与符号表、重跑校验。"
        "第五节的术语不一致不用回复，除非你不同意。",
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
        f"## 二、公式差异（{len(math_rows)} 处）",
        "",
        "脚本把原文和译文的每一处公式逐字对过，下面是所有不一致的地方。"
        "多一个下标、少一个绝对值、「大于等于」写成「大于」，都会让命题变成另一个命题，"
        "所以这一节请逐条看。",
        "",
    ]
    if math_rows:
        for i, r in enumerate(math_rows, 1):
            typ = (r.get("类型") or "").strip()
            L.append(f"### F{i}. {typ} · 源第 {(r.get('源行') or '').strip()} 行"
                     f" · 相似度 {(r.get('相似度') or '').strip()}"
                     f" · 键 `math:{(r.get('序号') or '').strip()}`")
            if (r.get("原文式") or "").strip():
                L.append(f"- 源：`{(r.get('原文式') or '').strip()[:200]}`")
            if (r.get("译文式") or "").strip():
                L.append(f"- 译：`{(r.get('译文式') or '').strip()[:200]}`")
            if (r.get("源上下文") or "").strip():
                L.append(f"- 位置：{_clip(r.get('源上下文'), 90)}")
            if (r.get("说明") or "").strip():
                L.append(f"- 为什么要看：{r.get('说明')}")
            L += ["", "> 你的意见：", ""]
    else:
        L += ["没有差异。脚本只比符号，公式的意思对不对还得你自己看。", ""]

    L += [
        "---",
        "",
        f"## 三、符号一览（{len(notation_rows)} 条）",
        "",
        "正文用了、表里没有的符号，读者只能回正文里找定义；"
        "表里有、正文没有的，多半是抄表时抄错了。都不影响理解，但影响能不能查。",
        "",
    ]
    if notation_rows:
        miss = [r for r in notation_rows if (r.get("类型") or "") == "缺失"]
        other = [r for r in notation_rows if (r.get("类型") or "") != "缺失"]
        if miss:
            L.append("**正文有、表里没有**（按出现次数排，只出现一次的多半可以不进表）：")
            L.append("")
            for r in miss:
                L.append(f"- `{(r.get('符号') or '').strip()}` ×{(r.get('出现次数') or '0').strip()}"
                         f"　首见第 {(r.get('首次行') or '').strip()} 行"
                         f"　{_clip(r.get('上下文'), 40)}")
            L.append("")
        for r in other:
            L.append(f"- [{(r.get('类型') or '').strip()}] `{(r.get('符号') or '').strip()}`")
        L += ["", "> 你的意见：", ""]
    else:
        L += ["符号表与正文一致。", ""]

    L += [
        "---",
        "",
        f"## 四、图与表（{len(fig_rows)} 条）",
        "",
        "图的版式只许恢复、不许重排：原文并排的面板要并排，原文分开的两张图不许合并。"
        "下面这些是脚本能判的部分；宽图会不会被压小，只能你自己看一眼。",
        "",
    ]
    if fig_rows:
        for r in fig_rows:
            typ = (r.get("类型") or "").strip()
            where = (r.get("位置") or "").strip()
            L.append(f"- [{typ}] {where + '　' if where else ''}{(r.get('说明') or '').strip()}")
        L += ["", "> 你的意见：", ""]
    else:
        L += ["图的编号、图注、路径都对得上。", ""]

    L += [
        "---",
        "",
        f"## 五、术语不一致（{len(drift)} 条，可直接改）",
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
        L += [f"{names}{more}。按引用规则，括号引用逐字保留，这些词本来就不该在译文里变成中文，"
              "列出来只是噪声，已从上面的清单剔除。", ""]
    else:
        L += ["无。", ""]

    L += [
        "---",
        "",
        f"### 附：原文疑点（{sum(1 for m in manual if (m.get('类型') or '') == '原文疑误')} 条，已并入第一节）",
        "",
        "原文本身有问题的地方（符号前后不一致、假设与证明对不上、编号跳号）都列在第一节点名了。"
        "不替作者圆场，也不擅自改。",
        "",
        "---",
        "",
        f"## 六、候选术语（{len(fresh)} 条）",
        "",
        "原文反复出现、术语表里没有的词。每条附一次出现的上下文，以及我的建议译法。"
        "只挑「译错会让读者理解成另一个概念、或让公式的含义变形」的收进表——"
        "如 consistency（相合性／一致性）、sharp bound（最优界／尖锐界）、identifiability（可识别性）。"
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
        "把这份文件留着，说一声「按清单改」。我会：读你的意见 → 更新术语表、符号表与译文 → "
        "重跑公式归一、公式比对与结构对账 → 已决条目记进 `已决定.csv`，下版清单不再出现。",
    ]

    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print(f"要你定 {len(manual)} 条 | 公式差异 {len(math_rows)} 处 | 符号表 {len(notation_rows)} 条 | "
          f"图与表 {len(fig_rows)} 条 | 术语不一致 {len(drift)} 条 | 候选术语 {len(fresh)} 条")
    print(f"已写出 {out}")


if __name__ == "__main__":
    main()
