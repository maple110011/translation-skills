r"""把译文 Markdown 转成可编译的 XeLaTeX 源（可选直接出 PDF）。

用法：
    python md2tex.py 译文.md 输出.tex [--source-pdf 原文.pdf] [--pdf]
    python md2tex.py 译文.md 输出.tex --title-en "..." --authors "..." --venue "ICLR 2023" --doi 10.xxxx --citekey foo2024-zh

设计约定（这些约定是踩坑踩出来的，改之前先读 references/pdf-latex.md）：
* 编号写成 \tag{n}（右对齐）；同组多行公式合并成 align*/gather*，不逐行成 display；
* 公式不另起段落（否则 TeX 会多垫一个 baselineskip，段前空白明显大于段后）；
* 数学里不用裸 |（某些渲染器会当表格分隔符），一律 \vert/\Vert；
* 书签只用 \pdfbookmark，配 \addcontentsline 会让每个标题出现两条书签；
* 引文、符号表都走 hyperref 的 \hyperlink/\hypertarget，锚点不能落在 caption 里。
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import argparse

ap = argparse.ArgumentParser(description="译文 Markdown → XeLaTeX（可选出 PDF）")
ap.add_argument("md", help="译文 Markdown")
ap.add_argument("tex", help="输出 .tex")
ap.add_argument("--source-pdf", default=None, help="原文 PDF（用于 sha256 与首页元信息）")
ap.add_argument("--pdf", action="store_true", help="顺带用 xelatex 编译两遍出 PDF")
ap.add_argument("--title-en", default=None)
ap.add_argument("--authors", default=None)
ap.add_argument("--venue", default=None)
ap.add_argument("--doi", default=None)
ap.add_argument("--arxiv", default=None)
ap.add_argument("--citekey", default=None)
ap.add_argument("--footnotes", choices=["footnote", "endnote"], default="footnote",
                help="footnote=正文 [^n] 渲染成 LaTeX 页底脚注（默认，保留脚注格式）；"
                     "endnote=旧行为，脚注文字集中排在文末 ## 脚注 节")
ap.add_argument("--allow-orphan-notes", action="store_true",
                help="允许「有 [^n]: 定义、正文却没有 [^n] 引用」的脚注降级成文末编号段落；"
                     "默认这是硬错误——那正是 PDF 里脚注变成文末一节的原因")
ap.add_argument("--fig-meta", default=None,
                help="figure_layout.py 产出的 图片版式.csv：按原刊 bbox 占比给每张图定宽，"
                     "附录里只占半栏的图就不会被拉满整栏")
args = ap.parse_args()

# 原刊里每张图占正文栏宽的比例。没有这一层时一律 0.93\linewidth，附录的小图
# 会被放大一倍多；多联图也默认等分，和原刊的 41%/27%/27% 对不上。
FIG_META = {}
if args.fig_meta:
    import csv as _csv
    with open(args.fig_meta, encoding='utf-8-sig', newline='') as _fh:
        for _r in _csv.DictReader(_fh):
            try:
                FIG_META[pathlib.PurePosixPath(
                    str(_r.get('path', '')).replace('\\', '/')).name] = \
                    min(1.0, max(0.12, float(_r.get('width_frac') or 0)))
            except (TypeError, ValueError):
                continue


def fig_frac(path):
    """图片在原文里的栏宽占比；查不到返回 None。"""
    return FIG_META.get(pathlib.PurePosixPath(str(path).replace('\\', '/')).name)


def _pdf_pages(path):
    """用 pdfinfo 数页数；没有 poppler 就返回 '?'。"""
    try:
        out = subprocess.run(['pdfinfo', str(path)], capture_output=True).stdout.decode('utf-8', 'ignore')
        mm = re.search(r'Pages:\s+(\d+)', out)
        return mm.group(1) if mm else '?'
    except Exception:
        return '?'


MD = pathlib.Path(args.md)
TEX = pathlib.Path(args.tex)
SRCPDF = pathlib.Path(args.source_pdf) if args.source_pdf else None
text = MD.read_text(encoding='utf-8')

fm = {}
m = re.match(r'---\s*\n(.*?)\n---\s*\n', text, re.S)
if m:
    cur = None
    for line in m.group(1).splitlines():
        item = re.match(r'^\s*-\s+(.*)$', line)
        if item and cur:
            # YAML 列表（authors: 下面一列 «- 名字»）。旧版按行切 «:» 只拿到空值，
            # 结果 PDF 首页的「原文作者」永远是空白。
            more = item.group(1).strip().strip('"\'')
            fm[cur] = (fm[cur] + '; ' + more) if fm.get(cur) else more
            continue
        k, sep, v = line.partition(':')
        if not sep:
            continue
        cur = k.strip()
        fm[cur] = v.strip().strip('"\'')
    text = text[m.end():]


def demote_front_tables(src):
    """把正文开头那两节「符号一览」「保留英文术语一览」挪到文末。

    译稿按 skill 规范把它们放在最前，但 PDF 是给读者看的：首页应当是标题、
    作者、单位、摘要，翻两页符号表才看见作者是本末倒置。这两节是译本附表，
    PDF 里统一挪到文末（附录之后），Markdown 原文件不动。
    """
    mh = re.search(r'(?m)^#\s+\S', src)
    if not mh:
        return src
    head, rest = src[:mh.start()], src[mh.start():]
    sec = re.compile(r'(?ms)^##[ \t]*(?:符号一览|保留英文术语一览)[ \t]*\n.*?'
                     r'(?=^##[ \t]|^#[ \t]|\Z)')
    moved = [mm.group(0).rstrip() for mm in sec.finditer(head)]
    if not moved:
        return src
    head = re.sub(r'\n{3,}', '\n\n', sec.sub('', head)).rstrip() + '\n\n'
    return head + rest.rstrip() + '\n\n' + '\n\n'.join(moved) + '\n'


text = demote_front_tables(text)


# 预扫脚注定义：正文里的 [^n] 要变成 \footnote{…}，而定义行在文末，
# 必须先收集再排版，否则正文先走完时拿不到脚注文字。放在 front matter
# 剥离之后，避免把 YAML 里的字段误当成脚注。
def _clean_def(s):
    """定义正文清洗：剥 HTML 注释（含待译标记）与历史稿的「第 N 页脚注 n：」前缀。

    页面前缀是旧流程塞进来的，跟着 \footnote{} 排进页底会变成
    「第 6 页脚注 1：……」这种读者看不懂的正文。
    """
    s = re.sub(r'<!--.*?-->', '', s or '', flags=re.S).strip()
    s = re.sub(r'^\**\s*第\s*\d+\s*页[^：:\n]{0,24}[：:]\s*', '', s)
    s = re.sub(r'^\**\s*(?:页底)?(?:脚注|注释|尾注|注)\s*\w{0,4}\s*\**\s*[：:]\s*', '', s)
    return s.strip()


FN_DEFS = {m.group(1): _clean_def(m.group(2))
           for m in re.finditer(r'(?m)^\[\^(\w+)\]:\s*(.*)$', text)}
# 正文里真正出现的引用标记。历史稿常常只在文末补了脚注节、没有硬猜正文
# 引用位置；这些定义在页底模式下无处安放，必须降级成文末编号段落——但那是
# 缺陷不是常态，默认报错，别让「脚注变文末一节」再静默发生一次。
FN_USED = {m.group(1) for m in re.finditer(
    r'\[\^(\w+)\](?!:)',
    re.sub(r'(?m)^\[\^\w+\]:.*$', '',
           re.sub(r'<!--.*?-->', '', text, flags=re.S)))}
FN_ORPHAN = [n for n in FN_DEFS if n not in FN_USED]
# 反过来：正文有标记、定义却没有——PDF 里会留一个光秃秃的上标编号，没注释。
FN_UNBACKED = sorted(n for n in FN_USED if n not in FN_DEFS)
if FN_UNBACKED:
    sys.stderr.write("[WARN] 这些正文标记找不到脚注定义，PDF 里只有编号没有注释：%s\n"
                     % "、".join(FN_UNBACKED[:20]))

if FN_ORPHAN and args.footnotes == 'footnote' and not args.allow_orphan_notes:
    sys.stderr.write(
        "[FAIL] 这些脚注有定义、正文里却没有 `[^n]` 引用：%s\n"
        "       它们只能降级成文末编号段落，PDF 里就会出现「单独一节」的脚注列表。\n"
        "       先跑 `python scripts/footnote_recover.py … --apply --check` 把标记锚回正文"
        "（判不出位置的看 _work/脚注_待锚.csv；--place 回灌）；\n"
        "       确实要尾注形式或接受降级，再加 --footnotes endnote / --allow-orphan-notes。\n"
        % "、".join(FN_ORPHAN[:20]) + ("（共 %d 条）\n" % len(FN_ORPHAN)
                                      if len(FN_ORPHAN) > 20 else ""))
    sys.exit(2)


def pick(cli, *keys, default=''):
    if cli:
        return cli
    for k in keys:
        if fm.get(k):
            return fm[k].strip().strip('"')
    return default


TITLE_ZH = pick(None, 'title_zh', 'title_zh_cn') or (fm.get('title', '') and '')
TITLE_EN = pick(args.title_en, 'title', 'title_en')
def parse_authors(v):
    """把 '["Akyürek, Ekin", ...]'、'A; B'、'Last, First' 统一成 'Ekin Akyürek, Dale Schuurmans'。

    列表项之间用 «;» 分隔（front matter 的 YAML 列表拼出来就是这个形态），
    单项内部若只有一个逗号，按 «姓, 名» 换序。
    """
    v = (v or '').strip()
    if not v:
        return ''
    if v.startswith('['):
        try:
            items = [str(x) for x in json.loads(v)]
        except Exception:
            items = [x.strip().strip('"\'') for x in v.strip('[]').split(';')]
    else:
        items = [x.strip() for x in v.split(';') if x.strip()]
    out = []
    for it in items:
        if len(items) == 1 and it.count(',') == 1:
            last, first = it.split(',', 1)
            out.append(first.strip() + ' ' + last.strip())
        else:
            out.append(it)
    return ', '.join(x for x in out if x)


AUTHORS = parse_authors(pick(args.authors, 'authors', 'author'))
VENUE = pick(args.venue, 'journal', 'venue', 'booktitle', default='')
ARXIV = pick(args.arxiv, 'arxiv', default='')
DOI = pick(args.doi, 'doi', default='')
if not DOI:
    # arXiv 预印本的规范 DOI 就是 10.48550/arXiv.<id>；首页空着一栏不如填上。
    ax = ARXIV.replace('arXiv:', '').strip()
    if re.match(r'^\d{4}\.\d{4,5}', ax):
        DOI = '10.48550/arXiv.' + ax
DOCTYPE_MAP = {'conference': '会议论文', 'conferencepaper': '会议论文', 'journal': '期刊论文',
               'journalarticle': '期刊论文', 'preprint': '预印本', 'book': '专著',
               'chapter': '书章', 'thesis': '学位论文', 'report': '报告'}
DOCTYPE = pick(None, 'type', 'doctype', default='')
DOCTYPE = DOCTYPE_MAP.get(DOCTYPE.lower(), DOCTYPE) or ('会议论文' if VENUE else '文稿')
CITEKEY = pick(args.citekey, 'citekey', default=(pathlib.Path(args.tex).stem + '-zh'))
if not TITLE_ZH:
    mh = re.search(r'(?m)^#\s+(.+)$', text)
    TITLE_ZH = mh.group(1).strip() if mh else (TITLE_EN or MD.stem)
SHA = (hashlib.sha256(SRCPDF.read_bytes()).hexdigest() if SRCPDF and SRCPDF.exists()
       else fm.get('source_sha256', ''))
SRC_NAME = SRCPDF.name if SRCPDF else fm.get('source_file', '')

REP = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '&': r'\&', '%': r'\%',
       '#': r'\#', '_': r'\_', '^': r'\textasciicircum{}', '~': r'\textasciitilde{}',
       '$': r'\$'}

SYM = {'α': r'$\alpha$', 'β': r'$\beta$', 'γ': r'$\gamma$', 'δ': r'$\delta$',
       'ε': r'$\epsilon$', 'θ': r'$\theta$', 'κ': r'$\kappa$', 'λ': r'$\lambda$',
       'μ': r'$\mu$', 'ν': r'$\nu$', 'π': r'$\pi$', 'ρ': r'$\rho$', 'σ': r'$\sigma$',
       'τ': r'$\tau$', 'φ': r'$\phi$', 'χ': r'$\chi$', 'ψ': r'$\psi$', 'ω': r'$\omega$',
       'Δ': r'$\Delta$', 'Σ': r'$\Sigma$', 'Π': r'$\Pi$', 'Ω': r'$\Omega$',
       '⊙': r'$\odot$', '⊗': r'$\otimes$', '□': r'$\square$', '→': r'$\rightarrow$',
       '×': r'$\times$', '±': r'$\pm$', '≤': r'$\leq$', '≥': r'$\geq$',
       '≈': r'$\approx$', '∈': r'$\in$', '∝': r'$\propto$', '∼': r'$\sim$',
       '·': r'$\cdot$', '∞': r'$\infty$', '∑': r'$\sum$', '√': r'$\surd$'}


def esc(s):
    # MinerU 把 HTML 表格里的单引号等抽成数字实体；不解码会原样排成
    # \&\#x27; 并把单元格撑得很宽。
    s = re.sub(r'&#x([0-9A-Fa-f]+);', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
    return ''.join(SYM.get(c) or REP.get(c, c) for c in s)


lines = text.split('\n')
try:
    ref_start = next(k for k, l in enumerate(lines)
                     if l.strip() in ('## 参考文献', '## REFERENCES', '## References'))
except StopIteration:
    ref_start = len(lines)

ref_end = len(lines)
for k in range(ref_start + 1, len(lines)):
    if lines[k].startswith('## '):
        ref_end = k
        break
refs = [l.strip() for l in lines[ref_start + 1:ref_end] if l.strip()]
body_lines = lines[:ref_start] + ['@@REFS@@'] + lines[ref_end:]

CITE = re.compile(r'[（(]([^（）()]{0,150}?\b(?:19|20)\d{2}[^（）()]{0,30}?)[）)]')
PART = re.compile(r'^\s*([A-Z][A-Za-zÀ-ÿ’\'\-]+)'
                  r'((?:\s+et\s+al\.)|(?:\s*(?:\\?&)\s*[A-Z][A-Za-zÀ-ÿ’\'\-]+))?'
                  r'\s*,?\s*((?:19|20)\d{2})[。．.]?\s*$')

pairs = set()
for line in body_lines:
    for g in CITE.finditer(line):
        for part in g.group(1).split(';'):
            mm = PART.match(part)
            if mm:
                pairs.add((mm.group(1).lower(), mm.group(3)))

ref_anchor = {}
used = set()
for idx, r in enumerate(refs):
    years = re.findall(r'\b(?:19|20)\d{2}\b', r)
    year = years[-1] if years else ''
    head = r[:160].lower()
    cand = sorted(p for p in pairs if p[1] == year and p[0] in head and p not in used)
    if not cand:
        cand = sorted(p for p in pairs if p[0] in head and p not in used)
    if cand:
        used.add(cand[0])
        ref_anchor[cand[0]] = 'ref%d' % (idx + 1)


def link_group(match, already=False):
    whole = match.group(0)
    inner = match.group(1)
    segs = re.split(r'([;；])', inner)
    parts = segs[0::2]
    seps = segs[1::2]
    keys = []
    for part in parts:
        mm = PART.match(part)
        keys.append(ref_anchor.get((mm.group(1).lower(), mm.group(3))) if mm else None)
    if not any(keys):
        return whole
    op, cl = ('（', '）') if whole[0] == '（' else ('(', ')')
    uniq = {k for k in keys if k}
    cjk = re.search(r'[\u4e00-\u9fff]', inner)
    if len(uniq) == 1 and not cjk:
        # 整组只有一条文献且是纯引文：整段（含括号）都可点
        txt = whole if already else esc(whole)
        return r'\hyperlink{%s}{%s}' % (next(iter(uniq)), txt)
    # 多条/混合：逐条链接，左右括号并进首尾两条，尽量扩大可点区域
    linked = [i for i, k in enumerate(keys) if k]
    first, last = linked[0], linked[-1]
    res = []
    for idx, part in enumerate(parts):
        txt = part.strip() if already else esc(part.strip())
        if idx == first:
            txt = op + txt
        if idx == last:
            txt = txt + cl
        if idx < len(seps):
            # 半角分号原文后面带一个空格，补回去（全角分号本身自带间距）
            txt = txt + seps[idx] + (' ' if seps[idx] == ';' else '')
        res.append(r'\hyperlink{%s}{%s}' % (keys[idx], txt) if keys[idx] else txt)
    return ''.join(res)


NARR = re.compile(r'([A-Z][A-Za-zÀ-ÿ’\'\-]+)((?:\s+et\s+al\.)?)\s*[（(]((?:19|20)\d{2})[）)]')


def link_narr(match, already=False):
    key = (match.group(1).lower(), match.group(3))
    if key not in ref_anchor:
        return match.group(0)
    txt = match.group(0) if already else esc(match.group(0))
    return r'\hyperlink{%s}{%s}' % (ref_anchor[key], txt)


def link_cites(line, already=False):
    line = CITE.sub(lambda m: link_group(m, already), line)
    line = NARR.sub(lambda m: link_narr(m, already), line)
    return line


URL_PAT = re.compile(r'https?://[^\s<>，。；）)\]}]+')


def inline(s, nolink=False):
    r"""行内排版：数学/粗体/上标先占位，再整体识别引文（这样跨公式的引文组也能兜住）。

    URL 单独占位后走 \url{}：xurl 已加载，可断行可点击；直接 esc() 会变成
    一长串不可断的普通文本，在页底脚注里必然撑出 Overfull \hbox。
    """
    urls = []
    if 'http' in s:
        def _hide_url(m):
            urls.append(m.group(0))
            return '\x01U%d\x02' % (len(urls) - 1)
        s = URL_PAT.sub(_hide_url, s)
    store = []
    pieces = []
    for part in re.split(r'(\$[^$]+\$|<sup>[^<]*</sup>|\[\^\w+\])', s):
        if not part:
            continue
        if re.fullmatch(r'\[\^\w+\]', part):
            n = part[2:-1]
            if args.footnotes == 'footnote' and n in FN_DEFS:
                # 页底真脚注：脚注文字跟着引用标记走，PDF 里保留脚注格式。
                store.append(r'\footnote{' + inline(FN_DEFS[n], nolink=True) + '}')
            else:
                # 尾注模式：正文只留上标编号，文字在文末 ## 脚注 节。
                store.append(r'\textsuperscript{' + esc(n) + '}')
            pieces.append('\x01M%d\x02' % (len(store) - 1))
            continue
        if part.startswith('<sup>') and part.endswith('</sup>'):
            # 兜底：MinerU 抽出的 HTML 上标转成 LaTeX 可渲染形式，
            # 不让 <sup>1</sup> 这样的字面文本进 PDF。
            store.append(r'\textsuperscript{' + esc(part[5:-6].strip()) + '}')
            pieces.append('\x01M%d\x02' % (len(store) - 1))
            continue
        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            store.append(part)
            pieces.append('\x01M%d\x02' % (len(store) - 1))
            continue
        for sub in re.split(r'(\*\*[^*]+\*\*)', part):
            if not sub:
                continue
            if sub.startswith('**') and sub.endswith('**') and len(sub) > 4:
                store.append(r'\textbf{' + esc(sub[2:-2]) + '}')
                pieces.append('\x01B%d\x02' % (len(store) - 1))
            else:
                pieces.append(esc(sub))
    text = ''.join(pieces)
    if not nolink:
        text = link_cites(text, True)
    for idx, val in enumerate(store):
        text = text.replace('\x01M%d\x02' % idx, val).replace('\x01B%d\x02' % idx, val)
    for idx, u in enumerate(urls):
        text = text.replace('\x01U%d\x02' % idx, r'\url{' + u + '}')
    return text



out = []
i = 0
in_list = False
bm = 0
nota = []


def flush():
    global in_list
    if in_list:
        out.append(r'\end{itemize}')
        in_list = False


CAP_NUM = [None, None]          # 最近一次图注自带的（图/表, 编号）


def take_caption(j):
    r"""图注两种写法都认：**图 N**　… 与 图 N. …（后者常见于 MinerU 提取稿）。

    第二种必须带 . ． 、 : ： 分隔符，否则「图 1 显示了……」这类正文句子会被误吃。
    编号记在 CAP_NUM 里：译文正文按原刊编号引用（"如图 6 所示"），而 LaTeX 的
    \caption 是按出现顺序自增的——浮动对象一旦被重定位，两边就对不上。
    """
    k = j
    while k < len(body_lines) and not body_lines[k].strip():
        k += 1
    if k < len(body_lines):
        line = body_lines[k].strip()
        mm = re.match(r'\*\*(图|表)\s*(\d+)\*\*[　\s]?(.*)$', line, re.S)
        if not mm:
            mm = re.match(r'^(图|表)\s*(\d+)\s*[.．、:：][　\s]*(.+)$', line, re.S)
        if mm:
            CAP_NUM[0], CAP_NUM[1] = mm.group(1), int(mm.group(2))
            return mm.group(3), k + 1
    CAP_NUM[0], CAP_NUM[1] = None, None
    return None, j


def fig_counter():
    """让 PDF 里的图号与译文正文引用的图号一致（原刊编号，不按出现顺序重排）。"""
    if CAP_NUM[0] == '图' and CAP_NUM[1]:
        return r'\setcounter{figure}{%d}' % (CAP_NUM[1] - 1)
    return None


def find_imgs(blob):
    """从 figure 块里取图片；<img> 属性顺序任意，也认块内的 Markdown 图片。

    旧正则要求 src 后紧跟 alt，遇到 MinerU 常见的
    <img src="…" width="32%" alt="…"> 会整块识别失败，figure 里只剩 caption。
    """
    imgs = []
    for tag in re.finditer(r'<img\b([^>]*)>', blob, re.I):
        attrs = dict(re.findall(r'([\w-]+)\s*=\s*"([^"]*)"', tag.group(1)))
        if attrs.get('src'):
            imgs.append((attrs['src'], attrs.get('alt', '')))
    if imgs:
        return imgs
    return [(m.group(2), m.group(1)) for m in
            re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', blob)]


def split_md_row(line):
    """按 | 切 Markdown 表格的列，但不切 $…$ 里的竖线。

    数学里的 \\|、\\vert、\\Vert 乃至裸 | 都是公式内容；直接 split('|')
    会把一个单元格切成几段，反斜杠随后被 esc() 变成 \\textbackslash{}。
    """
    protected = []

    def hide(m):
        protected.append(m.group(0))
        return '\x01P%d\x02' % (len(protected) - 1)

    tmp = re.sub(r'\$[^$]*\$', hide, line)
    parts = [c.strip() for c in tmp.strip().strip('|').split('|')]
    return [re.sub(r'\x01P(\d+)\x02',
                   lambda m: protected[int(m.group(1))], c) for c in parts]


FIT = (r'\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{$\displaystyle ')

REL_CS = ('\\approx', '\\leq', '\\geq', '\\le', '\\ge', '\\equiv', '\\sim', '\\simeq')


def split_rel(s):
    """定位第一个顶层关系符（= 或 \\approx 等），返回 (起点, 长度)。"""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            j = i + 1
            while j < len(s) and s[j].isalpha():
                j += 1
            if s[i:j] in REL_CS:
                return i, j - i
            i = j
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '=' and depth == 0:
            return i, 1
        i += 1
    return None


def emit_group(blocks):
    """把同一组的多行公式合成一个环境：能等号对齐的用 align*，其余用 gather*（逐行装箱缩放）。

    两种情况都不再让每一行各自成一个 display，避免行间出现整段行高。
    """
    rows = []
    for b in blocks:
        mt = re.search(r'\\tag\{([^}]*)\}\s*$', b)
        tag = mt.group(1).strip() if mt else None
        if tag:
            tag = tag.replace('□', r'$\square$')
        body = b[:mt.start()].rstrip() if mt else b
        rows.append((body, tag, split_rel(body)))
    # 非数字编号（证明结束的 □）会把 align* 末行撑出页宽；整组降一号字，
    # 比退 gather* 更能保住等号对齐（见 references/pdf-latex.md 第二节）。
    special_tag = any(tag and not tag.isdigit() for _, tag, _ in rows)

    need_gather = False
    for i, (body, tag, sp) in enumerate(rows):
        if '\\begin{array}' in body or '\\begin{matrix}' in body or len(body) > 200:
            need_gather = True
            break
        if sp is None:
            # 没有关系符的行，只有当下一条以 = 开头时才当作左端（aff(...) / = RAW(...) 这种续行）
            nxt = rows[i + 1][2] if i + 1 < len(rows) else None
            if not (nxt is not None and nxt[0] == 0):
                need_gather = True
                break
    out.append(r'\begingroup\setlength{\abovedisplayskip}{4pt}\setlength{\belowdisplayskip}{4pt}'
               r'\setlength{\jot}{2pt}')
    if special_tag:
        out.append(r'\small')
    if need_gather:
        out.append(r'\begin{gather*}')
        for body, tag, _sp in rows:
            out.append(FIT + body + '$}' + (r'\tag{%s}' % tag if tag else '') + r'\\')
        out.append(r'\end{gather*}')
    else:
        out.append(r'\begin{align*}')
        for body, tag, sp in rows:
            if sp is None:
                line = body + ' & '
            else:
                pos, _ln = sp
                lhs = body[:pos].rstrip()
                rhs = body[pos:].lstrip()
                line = (lhs + ' & ' + rhs) if lhs else ('& ' + rhs)
            out.append(line + (r'\tag{%s}' % tag if tag else '') + r'\\')
        out.append(r'\end{align*}')
    out.append(r'\endgroup')


def emit_display(body, tight=False):
    mt = re.search(r'\\tag\{([^}]*)\}\s*$', body)
    tag = ''
    if mt:
        t = mt.group(1).strip().replace('□', r'$\square$')
        tag = r'\tag{%s}' % t
        body = body[:mt.start()].rstrip()
    # 局部重设公式间距：字体/环境切换可能把全局设置还原成类默认值
    out.append(r'\begingroup\setlength{\abovedisplayskip}{4pt}\setlength{\belowdisplayskip}{4pt}'
               r'\setlength{\abovedisplayshortskip}{4pt}\setlength{\belowdisplayshortskip}{4pt}')
    out.append(r'\begin{equation*}')
    out.append(FIT + body + '$}' + tag)
    out.append(r'\end{equation*}' + (r'\vspace{-1pt}' if tight else ''))
    out.append(r'\endgroup')


def strip_links(s):
    """去掉 \\hyperlink{...}{...} 的外壳（caption 里不能带链接）。"""
    res = []
    k = 0
    while True:
        j = s.find('\\hyperlink{', k)
        if j < 0:
            res.append(s[k:])
            break
        res.append(s[k:j])
        i = j + len('\\hyperlink{')
        depth = 1
        while i < len(s) and depth:
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
            i += 1
        if i < len(s) and s[i] == '{':
            i += 1
            start = i
            depth = 1
            while i < len(s) and depth:
                if s[i] == '{':
                    depth += 1
                elif s[i] == '}':
                    depth -= 1
                i += 1
            res.append(s[start:i - 1])
        k = i
    return ''.join(res)


def norm_annot(a):
    """把右侧标注整理成一行内可安全排版的片段。"""
    if '$' in a:
        b = a
        if b.startswith('\\text{'):
            b = b[len('\\text{'):]
        if b.endswith('}'):
            b = b[:-1]
        b = b.strip().strip('$')
        return '$' + b + '$'
    return '$' + a + '$'


def fit_inline(body, frac):
    return (r'\resizebox{\ifdim\width>%s\linewidth %s\linewidth\else\width\fi}{!}{$\displaystyle %s$}'
            % (frac, frac, body))


def emit_mixed(blocks):
    """混合组：bullet 行左对齐压紧；紧随其后的 (…)、(A^{-1}…) 当作右侧标注并入上一行。"""
    items = []
    for b in blocks:
        mt = re.search(r'\\qquad\\s*(\\text\\{.*\\})\\s*$', b, re.S)
        annot = ''
        if mt:
            annot = norm_annot(mt.group(1))
            b = b[:mt.start()].rstrip()
        if (items and items[-1][0].startswith('\\bullet') and not items[-1][1]
                and re.fullmatch(r'\(.{0,70}\)', b.strip())):
            items[-1] = (items[-1][0], '$' + b.strip()[1:-1] + '$')
            continue
        items.append((b, annot))
    out.append(r'\begingroup\setlength{\abovedisplayskip}{1pt}\setlength{\belowdisplayskip}{1pt}')
    for b, annot in items:
        if b.startswith('\\bullet'):
            if annot:
                line = r'\noindent\hspace*{1.2em}' + fit_inline(b, '0.78')
                line += r'\hfill{\small ' + annot + r'}'
            else:
                line = r'\noindent\hspace*{1.2em}' + fit_inline(b, '0.97')
            out.append(line + r'\par\vspace{0.5pt}')
        else:
            emit_display(b, tight=True)
    out.append(r'\endgroup')


def emit_compact_bullets(blocks):
    out.append(r'\begingroup\setlength{\abovedisplayskip}{0pt}\setlength{\belowdisplayskip}{0pt}')
    for body in blocks:
        mt = re.search(r'\\qquad\s*(\\text\{.*\})\s*$', body, re.S)
        annot = ''
        if mt:
            annot = norm_annot(mt.group(1))
            body = body[:mt.start()].rstrip()
        if annot:
            line = r'\noindent\hspace*{1.2em}' + fit_inline(body, '0.80')
            line += r'\hfill{\small ' + annot + r'}'
        else:
            line = r'\noindent\hspace*{1.2em}' + fit_inline(body, '0.97')
        out.append(line + r'\par\vspace{0.5pt}')
    out.append(r'\endgroup')


while i < len(body_lines):
    s = body_lines[i].strip()

    # 裸 Markdown 图片：![alt](path)。旧版会当普通文字排，PDF 里只剩一行路径，
    # 长路径还会造成 Overfull \hbox。
    if s.startswith('!['):
        m_figs = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', s)
        if m_figs:
            flush()
            i += 1
            caption, i = take_caption(i)
            sublabels = None
            if caption is None and len(m_figs) > 1:
                # 多联图底下常有一行子图标签（原刊的 "含类别特征 / 归一化 ROC AUC"），
                # MinerU 把它抽成了独立段落，图注在它后面。别让这行把图注吃掉。
                k = i
                while k < len(body_lines) and not body_lines[k].strip():
                    k += 1
                if k < len(body_lines):
                    ln = body_lines[k].strip()
                    if (0 < len(ln) <= 80
                            and not ln.startswith(('![', '**', '#', '|', '>', '<table'))):
                        c2, i2 = take_caption(k + 1)
                        if c2:
                            sublabels, caption, i = ln, c2, i2
            out.append(r'\begin{figure}[H]\centering')
            if len(m_figs) == 1:
                w = fig_frac(m_figs[0][1])
                out.append(r'\includegraphics[width=%.2f\linewidth]{%s}'
                           % (w if w else 0.93, m_figs[0][1]))
            else:
                # 一行多图 = 原刊里的一行多联图。有 图片版式.csv 就按原刊各栏
                # 宽窄分配（41%/27%/27%），没有才等分。
                fr = [fig_frac(p) for _a, p in m_figs]
                if all(fr):
                    scale = min(1.0, 0.97 / sum(fr))
                    widths = [max(0.10, f * scale) for f in fr]
                else:
                    widths = [0.93 / len(m_figs)] * len(m_figs)
                for k, (_alt, path) in enumerate(m_figs):
                    tail = r'\hfill' if k + 1 < len(m_figs) else r'\par\vspace{3pt}'
                    # [b] 底对齐：多联图各栏的裁切高度常不同，按顶端对齐会让
                    # 各栏的横轴错开一格；底对齐能把 x 轴拉回同一水平线。
                    out.append(r'\begin{minipage}[b]{%.2f\linewidth}\centering'
                               r'\includegraphics[width=\linewidth]{%s}\end{minipage}'
                               % (widths[k], path) + tail)
            if sublabels:
                # 子图标签要分开过 inline()：整串丢进去，`\quad` 会被当普通文本
                # 转义成字面 "quad"，页面上就成了「AquadB」。
                parts = [inline(x, nolink=True) for x in sublabels.split('　') if x.strip()]
                out.append(r'\par\vspace{2pt}{\small\centering '
                           + r'\quad '.join(parts) + r'\par}')
            if caption:
                fc = fig_counter()
                if fc:
                    out.append(fc)
                out.append(r'\caption{%s}' % inline(caption, nolink=True))
            out.append(r'\end{figure}')
            continue

    if s == '<!-- figure:start -->':
        flush()
        block = []
        i += 1
        while i < len(body_lines) and 'figure:end' not in body_lines[i]:
            block.append(body_lines[i])
            i += 1
        i += 1
        caption, i = take_caption(i)
        blob = '\n'.join(block)
        imgs = find_imgs(blob)
        num = 1
        if imgs:
            mn = re.search(r'图\s*(\d+)', imgs[0][1])
            num = int(mn.group(1)) if mn else 1
        cells = [c.strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', blob, re.S)
                 if '<img' not in c and not c.lstrip().startswith('![') and c.strip()]
        if not imgs:
            # 宁可只留图注文字，也不要排一个「只有 caption、没有图」的空 figure
            if caption:
                out.append(inline(caption))
            if cells:
                out.append(r'\par{\small ' + r'\quad '.join(inline(c) for c in cells) + '}')
            continue
        out.append(r'\begin{figure}[H]\centering')
        if num == 3 and len(imgs) == 3:
            for p, _ in imgs[:2]:
                out.append(r'\begin{minipage}[t]{0.48\linewidth}\centering'
                           r'\includegraphics[width=\linewidth]{%s}\end{minipage}\hfill' % p)
            out.append(r'\par\vspace{3pt}')
            if cells:
                out.append(r'{\small ' + inline(cells[0]) + r'}\par\vspace{3pt}')
            out.append(r'\includegraphics[width=0.93\linewidth]{%s}\par\vspace{2pt}' % imgs[2][0])
            if len(cells) > 1:
                out.append(r'{\small ' + inline(cells[1]) + r'}')
        else:
            per = {1: 1, 2: 2, 4: 2}.get(len(imgs), 3)
            frac = {1: 0.93, 2: 0.48, 3: 0.33}[per]
            for k, (p, _) in enumerate(imgs):
                tail = r'\hfill' if (k + 1) % per else r'\par\vspace{3pt}'
                out.append(r'\begin{minipage}[t]{%.2f\linewidth}\centering'
                           r'\includegraphics[width=\linewidth]{%s}\end{minipage}' % (frac, p) + tail)
            if cells:
                out.append(r'\par{\small ' + r'\quad '.join(inline(c) for c in cells) + '}')
        if caption:
            fc = fig_counter()
            if fc:
                out.append(fc)
            out.append(r'\caption{%s}' % inline(caption, nolink=True))
        out.append(r'\end{figure}')
        continue

    if s == '$$':
        flush()
        blocks = []
        while i < len(body_lines) and body_lines[i].strip() == '$$':
            i += 1
            buf = []
            while i < len(body_lines) and body_lines[i].strip() != '$$':
                buf.append(body_lines[i])
                i += 1
            i += 1
            body = '\n'.join(buf).strip()
            mt = re.search(r'\\qquad\s*\((\d+)\)\s*$', body)
            if mt:
                body = body[:mt.start()].rstrip() + r'\tag{' + mt.group(1) + '}'
            blocks.append(body)
            k = i
            while k < len(body_lines) and not body_lines[k].strip():
                k += 1
            if k < len(body_lines) and body_lines[k].strip() == '$$':
                i = k
            else:
                break
        if blocks and any(b.startswith('\\bullet') for b in blocks):
            emit_mixed(blocks)
            out.append('')
            continue
        # 不让公式另起一段：公式若成为段首，TeX 会额外垫一个 \baselineskip，
        # 使「段前空白」明显大于「段后」。去掉前面那个空行即可并回上一段。
        while out and out[-1] == '':
            out.pop()
        tight = len(blocks) > 1
        if tight:
            emit_group(blocks)
            out.append('')
            continue
        for b in blocks:
            emit_display(b, tight)
        out.append('')
        continue

    if s.startswith('<!--'):
        i += 1
        continue

    if s.startswith('<table>'):
        flush()
        blob = []
        while i < len(body_lines) and '</table>' not in body_lines[i]:
            blob.append(body_lines[i])
            i += 1
        blob.append(body_lines[i] if i < len(body_lines) else '')
        i += 1
        caption, i = take_caption(i)
        joined = '\n'.join(blob)
        rows = re.findall(r'<tr>(.*?)</tr>', joined, re.S)
        cells = [[c.strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)] for r in rows]
        ncol = max(len(c) for c in cells)
        # table[H] + tabular 不能跨页：几十行的附录表会被整块截断，而编译
        # 仍是 0 错误，日志里只有一句 Overfull \vbox，最容易漏。拆成多个
        # 各自可落页的 table；续块重复表头，caption 只挂第一块。
        MAX_ROWS = 45
        chunks = ([cells[k:k + MAX_ROWS] for k in range(0, len(cells), MAX_ROWS)]
                  if len(cells) > MAX_ROWS else [cells])
        for ci, chunk in enumerate(chunks):
            out.append(r'\begin{table}[H]\centering\small\setcounter{table}{0}')
            # 附录里的超长单元格（如整段 Python 字典）会把 tabular 撑出页宽几百 pt。
            # 自适应缩放只在真的超宽时生效，正常表格保持原尺寸。
            out.append(r'\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{%')
            out.append(r'\begin{tabular}{@{}l' + 'l' * (ncol - 1) + r'@{}}')
            out.append(r'\toprule')
            body_rows = ([cells[0]] + chunk) if ci else chunk
            for k, row in enumerate(body_rows):
                out.append(' & '.join(inline(c) for c in row) + r' \\')
                if k == 0:
                    out.append(r'\midrule')
            out.append(r'\bottomrule\end{tabular}}')
            if ci == 0 and caption:
                out.append(r'\caption{%s}' % inline(caption, nolink=True))
            elif caption and len(chunks) > 1:
                out.append(r'\caption*{（续表）}')
            out.append(r'\end{table}')
        continue

    if s.startswith('|'):
        flush()
        rows = []
        while i < len(body_lines) and body_lines[i].strip().startswith('|'):
            cells = split_md_row(body_lines[i])
            if not re.fullmatch(r'[-: ]+', ''.join(cells)):
                rows.append(cells)
            i += 1
        ncol = max(len(r) for r in rows)
        is_notation = ncol == 3 and '符号' in rows[0][0]
        spec = {2: [0.30, 0.66], 3: [0.26, 0.44, 0.26]}.get(ncol, [1.0 / ncol] * ncol)
        colspec = '@{}' + ''.join(r'p{\dimexpr%.2f\linewidth-2\tabcolsep\relax}' % w
                                  for w in spec) + '@{}'
        out.append(r'{\small\begin{longtable}{%s}' % colspec)
        out.append(r'\toprule')
        for k, row in enumerate(rows):
            row = row + [''] * (ncol - len(row))
            cells_tex = [inline(c) for c in row]
            if is_notation and k > 0:
                toks = []
                for chunk in re.findall(r'\$([^$]+)\$', row[0]):
                    for piece in chunk.split(','):
                        piece = piece.strip()
                        if piece:
                            toks.append(piece)
                anchor = 'nota%d' % k
                if toks:
                    nota.append((toks, anchor, k))
                # 第三列改成「首次出现」位置，并做成跳转链接
                cells_tex[2] = r'\hyperlink{%s}{@@POS%d@@}' % (anchor, k)
            if is_notation and k == 0:
                cells_tex[2] = '首次出现'
            out.append(' & '.join(cells_tex) + r' \\')
            if k == 0:
                out.append(r'\midrule\endfirsthead')
                out.append(r'\toprule\endhead')
        out.append(r'\bottomrule\end{longtable}}')
        continue

    # 标题页已单独排版，正文里重复的作者/单位行跳过
    if s.count('$^{') >= 2:
        i += 1
        continue
    if re.match(r'^\$\^\{1\}\$\s*\S', s):
        i += 1
        continue

    # 文末脚注定义：页底脚注模式下，正文里真的有 [^n] 引用的，内容已经进了
    # \footnote{}，这里跳过；没有引用的（以及 endnote 模式）一律排成文末编号段落，
    # 保证脚注文字不会因为「正文标记缺失」而在 PDF 里整个消失。
    # 文末脚注定义：页底脚注模式下，正文里真的有 [^n] 引用的，内容已经进了
    # \footnote{}，这里跳过；没有引用的（以及 endnote 模式）一律排成文末编号段落。
    # 这条路只会出现在 --footnotes endnote 或显式 --allow-orphan-notes 时，
    # 默认情况下 FN_ORPHAN 已在开头硬拦。
    m_fn = re.match(r'^\[\^(\w+)\]:\s*(.*)$', s)
    if m_fn:
        flush()
        if args.footnotes == 'endnote' or m_fn.group(1) not in FN_USED:
            out.append(r'\noindent\textsuperscript{%s}\, %s\par' %
                       (esc(m_fn.group(1)), inline(_clean_def(m_fn.group(2)))))
        i += 1
        continue

    if s.startswith('#'):
        flush()
        level = len(s) - len(s.lstrip('#'))
        title = s[level:].strip()
        i += 1
        if level == 1:
            continue
        bm += 1
        sub = bool(re.match(r'^\d+\.\d', title) or title.startswith('C.'))
        t = re.sub(r'[$\\{}]', '', title)
        out.append(r'\phantomsection\pdfbookmark[%d]{%s}{bm%d}'
                   % (2 if sub else 1, esc(t), bm))
        out.append((r'\subsection*{' if sub else r'\section*{') + inline(title) + '}')
        continue

    if re.match(r'^(\\-|•)', s):
        if not in_list:
            out.append(r'\begin{itemize}[leftmargin=1.6em,itemsep=1pt,topsep=3pt]')
            in_list = True
        out.append(r'\item ' + inline(re.sub(r'^(\\-|•)\s*', '', s)))
        i += 1
        continue

    if re.match(r'^\d+\.\s', s):
        flush()
        items = []
        while i < len(body_lines) and re.match(r'^\d+\.\s', body_lines[i].strip()):
            items.append(inline(re.sub(r'^\d+\.\s*', '', body_lines[i].strip())))
            i += 1
        out.append(r'\begin{enumerate}[leftmargin=1.8em,itemsep=1pt,topsep=3pt]')
        out += [r'\item ' + it for it in items]
        out.append(r'\end{enumerate}')
        continue

    if re.fullmatch(r'\(\d+\)', s):
        flush()
        # 原 PDF 里「只有编号、没有公式」的行：当作普通一行右对齐编号排，行距才不会多出一整行
        while out and out[-1] == '':
            out.pop()
        out.append(r'\par\vspace{-3pt}\noindent\hfill (%s)\par\vspace{-3pt}' % s.strip('()'))
        out.append('')
        i += 1
        continue

    if not s:
        flush()
        out.append('')
        i += 1
        continue

    flush()
    out.append(inline(s))
    i += 1

body = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
# MinerU 常把 \text{} 里的英文词间空格抽成 2–3 个，撑宽 display 行。
# 只压 \text{} 内的字面空格，不动 \; \quad 等数学间距命令。
body = re.sub(r'\\text\s*\{[^}]*\}',
              lambda m: re.sub(r' {2,}', ' ', m.group(0)), body)

def caption_ranges(text):
    spans = []
    for m in re.finditer(r'\\caption\{', text):
        i = m.end()
        depth = 1
        while i < len(text) and depth:
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
            i += 1
        spans.append((m.start(), i))
    return spans


caps = caption_ranges(body)
anchor_from = body.find('\\section*{摘要}')
if anchor_from < 0:
    anchor_from = body.find('\\section*{Abstract}')
if anchor_from < 0:
    anchor_from = body.find('\\section*{')
# 符号表与保留术语表在文末，它们自身也含 $…$。不截上限的话，first_pos 会把
# 「符号出现在符号表里」当成首次出现，第三列全退化成「符号一览」。
_lim = [p for p in (body.find(r'\section*{符号一览}'),
                    body.find(r'\section*{保留英文术语一览}')) if p >= 0]
anchor_to = min(_lim) if _lim else len(body)

# 正文里所有 $...$ 数学片段（跳跃目标落在片段起点，避免在数学模式里插 \hypertarget）
mathspans = []
_i = anchor_from
while _i < anchor_to:
    if body[_i] == '\\\\':
        _i += 2
        continue
    if body[_i] == '$':
        _j = _i + 1
        while _j < len(body):
            if body[_j] == '\\\\':
                _j += 2
                continue
            if body[_j] == '$':
                break
            _j += 1
        if _j < len(body) and not any(a <= _i < b for a, b in caps):
            mathspans.append((_i, _j + 1, body[_i + 1:_j]))
        _i = _j + 1
    else:
        _i += 1


def flex_pat(tok):
    """把 x_i 这类写法放宽成可匹配 x_{i} 的正则。"""
    out, i = [], 0
    while i < len(tok):
        c = tok[i]
        if c in '_^' and i + 1 < len(tok):
            if tok[i + 1] == '{':
                j = tok.find('}', i)
                if j > 0:
                    out.append(re.escape(c) + r'\{?' + re.escape(tok[i + 2:j]) + r'\}?')
                    i = j + 1
                    continue
            elif tok[i + 1] != '\\':
                out.append(re.escape(c) + r'\{?' + re.escape(tok[i + 1]) + r'\}?')
                i += 2
                continue
        out.append(re.escape(c))
        i += 1
    return ''.join(out)


def first_pos(toks):
    """在正文数学片段里找这些符号最早出现的位置。"""
    best = None
    for sym in toks:
        pat = re.compile(r'(?<![A-Za-z\\])' + flex_pat(sym) + r'(?![A-Za-z])')
        for s0, _s1, content in mathspans:
            if pat.search(content):
                if best is None or s0 < best:
                    best = s0
                break
    return best


def sec_label(title):
    """把书签标题压缩成「§2.1」这类短标签。"""
    m = re.match(r'^([A-H]|\d+)((?:\.\d+)+)', title)
    if m:
        return '§%s%s' % (m.group(1), m.group(2))
    m = re.match(r'^([A-H]|\d+)\s', title)
    if m:
        return '§%s' % m.group(1)
    return title.strip()[:10]


bookmarks = [(m.start(), m.group(1))
             for m in re.finditer(r'\\pdfbookmark\[\d\]\{([^}]*)\}\{bm\d+\}', body)]
inserts = []
labels = {}
for toks, anchor, k in nota:
    pos = first_pos(toks)
    if pos is None:
        labels[k] = '—'
        continue
    prev = [ttl for st, ttl in bookmarks if st < pos]
    labels[k] = sec_label(prev[-1]) if prev else '—'
    inserts.append((pos, anchor))
# 先插锚点（按位置从后往前，避免位移），再替换占位符（替换会改变长度）
for pos, anchor in sorted(inserts, reverse=True):
    body = body[:pos] + r'\hypertarget{%s}{}' % anchor + body[pos:]
for k, lab in labels.items():
    body = body.replace('@@POS%d@@' % k, lab)

reflines = []
for idx, r in enumerate(refs):
    anchor = 'ref%d' % (idx + 1)
    reflines.append(r'\hypertarget{%s}{}\noindent\hangindent=1.8em\hangafter=1 %s\par\vspace{3pt}'
                    % (anchor, inline(r)))
refs_head = r'\phantomsection\pdfbookmark[1]{参考文献}{bmref}' + '\n' + r'\section*{参考文献}' + '\n\n'
refs_tex = refs_head + '\n'.join(reflines)

preamble = r'''\documentclass[UTF8,11pt,a4paper,fontset=%(fontset)s]{ctexart}
\usepackage{geometry}
\geometry{left=2.3cm,right=2.3cm,top=2.5cm,bottom=2.2cm}
\usepackage{amsmath,amssymb,amsfonts,bm}
\usepackage{graphicx}
\usepackage{float}
\usepackage[font=small,labelsep=quad]{caption}
\usepackage{longtable,booktabs,array}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{xurl}
\usepackage{hyperref}
\usepackage{hyperxmp}
\hypersetup{colorlinks=true,linkcolor=blue!45!black,citecolor=blue!45!black,urlcolor=blue!55!black,
  pdftitle={%(tz)s},
  pdfauthor={%(au)s},
  pdfsubject={%(subj)s},
  pdfkeywords={%(kw)s},
  pdfcreator={XeLaTeX},
  pdfproducer={XeLaTeX (md2tex.py)},
  pdfdoi={%(doi)s},
  pdfpubtype={journalArticle},
  pdfcopyright={Translation for private study; original (c) the authors},
  pdfidentifier={%(doi)s},
}
%% 不要开 \XeTeXgenerateactualtext：它会给每个词套一层 /Span ActualText，
%% 阅读器按 ActualText 的字符宽度去算高亮框，于是"能复制、但框选只亮几个字母"。
%% 取而代之的是关掉 f-连字（NoCommon），保证 ffi→ffi 而不是 U+FB00。
\usepackage{fancyhdr}
\setmainfont{TeX Gyre Termes}[Ligatures={TeX,NoCommon}]
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\itshape %(te)s}
\fancyhead[R]{\small 中文译本}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\setlength{\parskip}{2pt}
\sloppy
\emergencystretch=2em
%% ctex 会在 \begin{document} 时重置行间公式间距，必须放到 AtBeginDocument 之后才生效
\AtBeginDocument{%%
  \setlength{\abovedisplayskip}{2pt}%%
  \setlength{\belowdisplayskip}{2pt}%%
  \setlength{\abovedisplayshortskip}{2pt}%%
  \setlength{\belowdisplayshortskip}{2pt}%%
  \setlength{\jot}{1pt}%%
}
\linespread{1.22}
\begin{document}
\begin{center}
{\LARGE\bfseries %(tz1)s\\[2pt]%(tz2)s\par}
\vspace{4pt}
{\large %(te)s\par}
\vspace{8pt}
{\normalsize %(au)s\par}
\end{center}
\vspace{4pt}
{\small
\noindent\begin{tabular}{@{}p{0.13\linewidth}p{0.8\linewidth}@{}}
文献类型 & %(doctype)s（%(venue)s）\\
原文题目 & %(te)s\\
原文作者 & %(au)s\\
DOI & %(doiline)s\\
\end{tabular}}\par
\vspace{2pt}
\noindent\rule{\linewidth}{0.6pt}

\vspace{8pt}
''' % dict(fontset='windows' if sys.platform == 'win32' else 'fandol',
           tz=TITLE_ZH,
           tz1=TITLE_ZH.split('？')[0] + '？' if '？' in TITLE_ZH else TITLE_ZH,
           tz2=TITLE_ZH.split('？')[1] if '？' in TITLE_ZH else '',
           te=esc(TITLE_EN), au=AUTHORS,
           subj=(TITLE_EN + ' 中文译本') if TITLE_EN else (TITLE_ZH + ' 中译本'),
           kw='%s, 中文译本, translation' % esc(CITEKEY),
           venue=esc(VENUE), arxiv=ARXIV, arxivid=esc(ARXIV.replace('arXiv:', '').strip()),
           doctype=esc(DOCTYPE), doiline=esc(DOI) or '—',
           doi=esc(DOI), key=esc(CITEKEY), sha=SHA[:32],
           srcfile=esc(SRC_NAME))

body = body.replace('@@REFS@@', refs_tex)

TEX.parent.mkdir(parents=True, exist_ok=True)
TEX.write_text(preamble + body + '\n\\end{document}\n', encoding='utf-8')
print('写出', TEX, '正文', len(body), '字符；文献', len(refs), '条；符号', len(nota), '个；引文锚', len(ref_anchor))

def _acquire_xelatex_lock(timeout=300):
    """跨进程串行化 xelatex。

    两个 XeLaTeX 同时编译（例如批量脚本并行跑两篇）会让其中一个在第 2 页
    附近静默中断，留下 0 字节 PDF，log 里连 `!` 错误都没有，极难诊断。
    锁文件内容是「pid 过期时间戳」，靠过期时间兜住陈旧锁，不需要删除文件
    （Windows 上删除有时会被环境钩子拦下）。
    """
    lock = pathlib.Path(tempfile.gettempdir()) / 'md2tex-xelatex.lock'
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            old = lock.read_text(encoding='utf-8', errors='ignore').split() if lock.exists() else []
            if (len(old) == 2 and float(old[1]) > time.time()
                    and old[0] != str(os.getpid())):
                time.sleep(2)
                continue
            lock.write_text('%s %f' % (os.getpid(), time.time() + 240), encoding='utf-8')
            return lock
        except (OSError, ValueError):
            time.sleep(1)
    print('提示：等待 xelatex 编译锁超时，继续编译（可能与另一进程冲突）', file=sys.stderr)
    return lock


def _release_xelatex_lock(lock):
    try:
        lock.write_text('0 0', encoding='utf-8')
    except OSError:
        pass


if args.pdf:
    lock = _acquire_xelatex_lock()
    outdir = TEX.parent
    # 两遍：第一遍定页码/书签，第二遍定交叉引用与链接目标
    # cwd 设为 md 所在目录：图片是相对 md 的 images/… 引用的。
    # 这里必须传相对路径——Windows 上带中文的绝对路径会让 xelatex 报 file error。
    base = MD.parent.resolve()
    rel_tex = os.path.relpath(TEX.resolve(), start=base).replace(os.sep, '/')
    rel_out = os.path.dirname(rel_tex) or '.'
    try:
        for i in range(2):
            r = subprocess.run(['xelatex', '-interaction=nonstopmode', '-output-directory', rel_out, rel_tex],
                               capture_output=True, cwd=str(base))
            if r.returncode != 0:
                log = TEX.with_suffix('.log')
                tail = log.read_text(encoding='utf-8', errors='ignore')[-1500:] if log.exists() else ''
                raise SystemExit('xelatex 失败（第 %d 遍）\n%s' % (i + 1, tail))
    finally:
        _release_xelatex_lock(lock)
    pdf = TEX.with_suffix('.pdf')
    print('PDF:', pdf, ('（%s 页）' % _pdf_pages(pdf)) if pdf.exists() else '未生成')
    log = TEX.with_suffix('.log')
    if log.exists():
        over = [ln for ln in log.read_text(encoding='utf-8', errors='ignore').split('\n')
                if ln.startswith('Overfull \\hbox') and 'too wide' in ln]
        if over:
            print('提示：有 %d 处 Overfull \\hbox，抽查一下是不是公式越界。' % len(over))
