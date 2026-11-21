# 从译文 Markdown 编译 PDF（版式尽量贴近原文）

> **适用范围**：本文件是 `political-economy-translation` 与 `dl-translation` 两个 skill 共用的 LaTeX 排版参考，两边 `scripts/md2tex.py` / `verify_pdf.py` 是同一份实现。政经稿件通常没有符号表、定理环境与伪代码，相应章节可略过；**脚注流程两边完全一致**：译文 Markdown 只写正文 `[^n]` 引用 + 文末 `[^n]:` 定义（没有 `## 脚注` 节），PDF 默认渲染成页底 `\footnote{}`。政经稿另有公众号排版分支（`build_wechat.py`），与 PDF 分支互不干扰，两者都以同一份 `[^n]` 译稿为源。

只在用户要 PDF 时才做。目标不是"排得好看"，而是**让中文读者看到的版面结构与原论文一致**：公式编号右对齐、多行推导等号对齐、图并排、引文可跳、书签可用。

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex \
    --source-pdf <原文>.pdf --pdf
# --pdf 会自动跑两遍 xelatex（第一遍定页码书签，第二遍定交叉引用）
```

前置：TeX Live（`xelatex` + ctex + `\usepackage{ctex}` 所需的字体）。Windows 用 `fontset=windows`，其他平台脚本会自动切 `fandol`。
元信息优先取译文 front matter（`title_zh` / `title` / `authors` / `journal` / `arxiv` / `doi` / `type`），缺的用命令行补：`--title-en --authors --venue --doi --arxiv --citekey`。YAML 列表也认（`authors:` 下面那列 `- 名字`）；arXiv 号会自动补成 `10.48550/arXiv.<id>` 的 DOI。

---

## 首页版式

首页只有三行，居中：中文标题 → 英文原题 → 作者，一条细横线之后就是正文第一段。

**字号 12pt、版心 17cm（左右各 2cm，上下 2.2／2.0cm）。** 11pt + 2.3cm 边距是早先的默认，中文正文每行挤到 44 字、字面偏小，打印和屏读都吃力；改完之后一行约 40 字，是中文论文的常见密度，页数会多两页左右，这是字大了的正常代价。

- **不加「文献类型 / 原文题目 / 原文作者 / DOI」那张表。** 这些信息在 front matter 里，读者打开正文不需要先看一遍著录；标题与作者在上方已经出现过一次，再列一遍就是重复。（`dl-translation` 那边反过来，保留信息表——它的读者要先判断"这是什么论文"，口径不同，**不要同步**。）
- **正文开头的 H1 与紧随其后的作者行会被跳过**：首页的标题、英文题名、作者都由 front matter 排，正文里再来一遍就是标题下面又挂一行作者名。只在开头这一处跳，正文中间的同形行不碰。
- **不放**出处、原文文件、译本说明。
- **符号一览与保留英文术语一览挪到文末**（附录之后）。译稿按 skill 规范放在最前，但 PDF 里那样会把论文自己的标题、作者、摘要压到一两页符号表后面。Markdown 原文件不动，只有排版这样处理。
- 页眉保留英文原题（左）与「中文译本」（右），这是每页的版式，不属于"文首信息"。

## 一、六条硬约定（每条都是踩坑踩出来的）

| 约定 | 为什么 |
|---|---|
| 编号写 `\tag{n}`，**不要**在 md 里写成 `\qquad (n)` 交差 | `\tag` 才能右对齐；md 里为兼容预览器才退化成 `\qquad (n)`，转 LaTeX 时要换回 |
| 同一组多行公式合并成 `align*` / `gather*`，不要每行一个 `equation*` | 逐行成 display 时，行与行之间会多出一整段公式间距；(9)(10) 这类两行公式会散开 |
| 公式**不另起段落** | 段首公式会让 TeX 额外垫一个 `\baselineskip`，表现为"段前空白明显大于段后" |
| 数学里不写裸 `|`，一律 `\vert` / `\Vert` | 某些 Markdown 预览器把竖线当表格分隔符，整条公式被拆成表格 |
| 书签只用 `\pdfbookmark` | 再配 `\addcontentsline` 会让每个标题出现**两条**书签 |
| 锚点（引文、符号表）不能落在 `\caption` 里 | hyperref 在 caption 里放 `\hyperlink` 会报 `\Hy@wrapper@babel` 错 |
| **不要开 `\XeTeXgenerateactualtext=1`** | 它给每个词套一层 `/Span <</ActualText (word)>>`，阅读器按 ActualText 的字符宽度算高亮框，结果是"能复制、但按住鼠标框选只亮几个字母"。改用关 f-连字（`Ligatures={TeX,NoCommon}`）来保证 `ffi` 不被压成 U+FB00 |

## 二、多条公式怎么分组合并

md 里连续的 `$$` 块不一定是"同一组"：可能是同一推导的续行，也可能是各自独立的公式。脚本按下面的规则判断：

1. **每行都有顶层关系符**（`=`、`\approx`、`\leq`…）→ `align*`，在第一个关系符处对齐，行末 `\tag`。
2. **"左端 + 续行"**：某行没有关系符、但下一行以 `=` 开头（`aff(...)` 后跟 `= RAW(...)`）→ 该行按左端处理，仍可对齐。
3. **含 `array`/`matrix`，或某行超过 200 字符** → `gather*`，逐行装箱（`\resizebox` 按页宽自适应），只保证紧凑、不保证对齐——对齐会越出页边。
4. 其余情况（如 (9)(10)：首行是纯表达式、次行以文字开头）→ `gather*`。

行距由 `\jot` 控制（脚本设 2pt）。别用 `\\[2pt]` 逐行调，会和 display skip 打架。

## 三、间距：怎么调、怎么量

- **先确认命中的是不是 short 分支**：改 `\abovedisplayshortskip` 看间距有没有变。变了说明公式跟在"短行"后面，只调 `\abovedisplayskip` 是白调。
- **ctex 会在 `\begin{document}` 时重置 display skip**，导言区的 `\setlength` 会失效，要放进 `\AtBeginDocument{}`。
- 量化验收（比肉眼可靠）：

```bash
pdftoppm -r 150 -f 5 -l 5 -gray -png paper.pdf page
# 用 PIL 对每行做墨迹投影，算相邻墨迹块的间距；正文行距约 5–7pt 时，
# 公式前后的间距也应落在 4–7pt，heading 前后 15–25pt 属正常
```

## 四、引文与符号表跳转

- 参考文献条目先建 `\hypertarget{refN}`，正文里的 `(作者 et al., 年)` 逐条换成 `\hyperlink{refN}{...}`。
- **整组只有一条文献时，把整段（含括号）都包进链接**——否则用户点在括号或中文说明上没反应。
- 多条文献时逐条链接，把左括号并进第一条、右括号并进最后一条。
- 分组要同时认半角 `;` 和**全角 `；`**；`A \& B, 2020` 这种两人合著要能匹配（正则里写成 `\\?&`，不是 `\\\\&`）。
- 跨行内公式的引文组（`…（见 $x$ 的讨论；Brown et al., 2020）`）：先把数学片段占位、整体做引文匹配、再还原。
- 符号表：锚点落在正文**数学片段起点**（`\hypertarget{}{}` 放在 `$` 前面，别插进数学模式里），"首次出现"那一列做成链接。

## 五、图与表

- **多联图必须是"一张图"，不是三张图。** 原刊 Figure 6 是左／中／右三栏并排一行，MinerU 会把它识别成三个 `image` 块，`full.md` 里就是三条独立的 `![…](…)`。照着逐条渲染，PDF 里就成了三张各自 0.93 栏宽、上下堆叠的图，**一页只能容一张**，图注也被拆开——这是"图片过大 + 图注分离"的典型成因。正确形态是让这几张图落在**同一行**（`![](a) ![](b) ![](c)`），`md2tex` 会排成一行 minipage。
  归一交给 `scripts/figure_layout.py`：它按 `content_list.json` 的 `bbox` 判断哪些图同页同排（竖直重叠过半），把 md 里那几条图片行合并成一行，并把夹在中间的子图标签（"含类别特征""归一化 ROC AUC"）收成一行小字放在图与图注之间。不要手工删那些标签——它们是 MinerU 从图里切出去的文字，图片本身没有。
- **图片宽度按原刊 bbox 走，不要一律 0.93 栏宽。** 附录里常有一张图只占半栏（本 skill 实测 44%／46%／74%），一律 0.93 会把它放大一倍多。`figure_layout.py` 产出 `_work/图片版式.csv`（每张图的 `宽 / 正文栏宽`），`md2tex --fig-meta` 读它定 `width=N\linewidth`；多联图按各栏真实比例分配 minipage（41%／27%／27%），不是等分。栏宽取该页**最宽**文本块，别用中位数——只有标题和轴标签的附录页会把中位数拉到几十磅。
- **图号用原刊编号，别让 LaTeX 按出现顺序重排。** 浮动对象一经重定位（`<!-- float:moved -->`），出现顺序就和原刊编号不一致，`\caption` 自增出来的"图 7"会与正文里"在图 6 中"打架。`md2tex` 把图注里的 `**图 N**` 记下来，在 `\caption` 前发 `\setcounter{figure}{N-1}`，PDF 图号与正文引用一致。
- 并排图也可以用 `<table><td>` 写（`minipage` + `\includegraphics[width=\linewidth]`，宽度由脚本按张数分配）。**不要在 md 里依赖 `<img width="32%">` 控制宽度**（百分比相对所在 `<td>` 会塌成 0 宽）；写了也不影响解析。两种写法二选一，`figure_layout.py` 见到 `<table>` 会跳过。
- 多联图各栏的裁切高度常不同，`minipage` 用 `[b]` 底对齐，否则各栏横轴会错开一格。
- `<img>` 属性顺序任意（`src` / `width` / `alt` 怎么排都行），裸 Markdown 图 `![alt](path)` 与块内 `![](path)` 同样识别。图注认 `**图 N**　…` 和 `图 N. …` 两种写法。解析不到图片时脚本宁可只留图注文字，也不排「只有 caption、没有图」的空 `figure`。
- **已知的裁切瑕疵**：MinerU 的图片裁切框偶尔切进子图标题，图片顶端会留下半截英文字母。这是图片像素本身的问题，版式改不了；要修得按 `bbox` 从原 PDF 重切（`pdftoppm -x -y -W -H`，注意 MinerU 的 bbox 是 100 dpi 像素坐标，pt = bbox × 0.72）。
- 宽矩阵、宽公式一律走 `\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{$\displaystyle …$}`，比按源码长度猜阈值可靠。
- `align*` 里不能对整行 `\resizebox`（会破坏对齐）；实测在 align 单元里 `\sbox{0}{...}` 量宽度会踩坏 amsmath 的盒子寄存器，报几百 pt 的 overfull——要么整组退 `gather*`，要么别对齐。
- **长表必须分块**：`table[H] + tabular` 不能跨页，几十行的附录表会被整块截断，而编译仍是 0 个 `!` 错误，日志里只留一句 `Overfull \vbox`。脚本按 **45 行**自动拆成多个各自可落页的 `table`，续块重复表头、只第一块挂 `\caption`（其余用 `\caption*{（续表）}`）。`longtable` 不是万能替代：多列宽表格改等宽 `p{}` 列会把方法名压在数字上。验收时**必须同时查 `\vbox`**，只数 `\hbox` 会漏掉整块数据丢失。

## 六、验收清单

1. 编译 **0 个 `!` 错误**；`Overfull \hbox` 只允许 1pt 以内的（多半是标点挤压）；**`Overfull \vbox` 必须为 0**（出现就是整块长表被截断，数据丢了）。
   **还要正面确认日志末尾有 `Output written on …`。** XeTeX 有一类内部错误（`bad native font flag in map_char_to_glyph` 最典型）**只写 stdout，一个字都不进 `.log`**：`!` 行数 0、`Output written` 没有，PDF 文件却还躺在那儿——是上一遍的、或者编到第 11 页断掉的。只数 `!` 行会把这种稿子判成通过（实测踩过：16 页的稿子崩在第 11 页，验收报 PASS）。
2. **文本层自检**（30 秒，最容易被忽略）：`pdftotext` 抽一页出来看——
   - 中文连续、没有乱码；
   - 没有 `ﬀ ﬁ ﬂ` 连字符（有就说明没关 `NoCommon`）；
   - 抓一页的内容流数 `BT`：一页应该是二十来个（一行一个），**不是几百个**（每词一个 BT + `/ActualText` 就是踩了上面那条坑）：

```bash
python - <<'PY'
import PyPDF2
p = PyPDF2.PdfReader('paper.pdf').pages[4]
c = p.get_contents()
data = c.get_data() if hasattr(c, 'get_data') else b''.join(x.get_object().get_data() for x in c)
s = data.decode('latin-1')
print('BT', s.count('BT'), '/ActualText', s.count('/ActualText'), 'TJ', s.count('TJ'))
PY
```

3. 书签树用 `PyPDF2.PdfReader(...).outline` 递归打印，确认**每个标题只出现一次**、层级正确。
4. 链接：统计 `/Link` 注解数；有 pdf.js 的话逐个 `getDestination` 解析，确认能落到参考文献页。
5. 把超链接外壳剥离后重扫正文，确认**没有漏链的引文组**。
6. 抽页面对照原文：公式块是否等号对齐、编号是否右对齐、图是否并排、附录链条是否左对齐紧排。
7. 页码：`pdfinfo` 看页数是否合理（一般比原文多 15–30%，中文行宽不同）。
8. **图片数**：`grep -c includegraphics paper.tex` 应对得上译文里 `![` 与 `<img src=` 的总数。早期版本的典型故障是「编译 0 错误、PDF 有页数，但一张图都没有，只剩路径文字与 caption」——只看 `!` 错误发现不了，必须数一遍。
9. **脚注**：逐条核 `_work/脚注.csv` 的中文/英文关键串是否进了 PDF 文本层，TeX 里 `\footnote{}` 数不少于清单内容脚注数，文本层无字面 `[^n]` / `<sup>`。脚注在 Markdown 里是正文 `[^n]` 引用 + 文末 `[^n]:` 定义，编译后必须变成页底真脚注，不能只剩一个上标数字。

1–2、8、9 已脚本化，编译后直接跑（有问题返回 1）：

```bash
python scripts/verify_pdf.py _work/pdf/paper.pdf \
    --tex _work/pdf/paper.tex --md <stem>_zh.md --footnotes _work/脚注.csv
```

`md2tex.py` 默认 `--footnotes footnote`（页底真脚注）；若稿件要求尾注形式，用 `--footnotes endnote`，脚注文字集中排在文末。两种模式都由 `verify_pdf.py` 验收。**页底模式下，有定义却找不到正文引用的脚注会让脚本 `exit 2`**——它们只能降级成文末编号段落，那正是「脚注变一节」的成因；确认要降级才加 `--allow-orphan-notes`。URL 走 `\url{}`（已加载 `xurl`），否则长链接在页底脚注里必然撑出 `Overfull \hbox`。

## 七、脚本解决不了的部分（交付时要说明）

- **MinerU 丢行**：个别多行公式的行在提取时整行丢失，只剩下一个编号，或编号整体错位一位。表现为"只有编号没有公式的行"。可机械修补的情况：前一块没有编号、后面紧跟裸编号 → 把编号并回前一块。其余的要么逐行对照原 PDF 重建，要么原样保留并注明。
- **原文自己的缺陷**：不少 ICLR/arXiv 论文里确实存在"只有编号、没有公式"的空行（作者 LaTeX 的遗留），这些应当**照原样保留**，不要擅自删。
- **超宽长行**：有些公式行本身就是满版宽（如 RAW 算子定义），对齐必然溢出，只能居中或缩排。

## 八、脚本已内置的适配（2026-11-14，不要再手搓排版副本）

一次双代理批量翻译里，两篇译文直接喂给旧版脚本时能编译出 PDF，但**一张图都没有**，还带着 10 处表格越界。逐条定位后已写进 `md2tex.py`：

| 现象 | 原因 | 现在怎么处理 |
|---|---|---|
| `figure` 环境只有 `\caption`、零张图 | 正则要求 `<img src="…" alt="…">` 里 `src` 后紧跟 `alt`，MinerU 实际写的是 `src="…" width="32%" alt="…"` | 逐个 `<img>` 标签解析属性字典，`src` 必需、`alt` 可选；同时兼容块内 Markdown 图 |
| PDF 里出现一长串图片路径，并伴随 Overfull | 裸 Markdown 图 `![alt](path)` 落到普通段落，被 `esc()` 转义成文字 | 主循环新增裸图分支，转成 `figure` + `\includegraphics`，并取走紧随的图注 |
| 「图 1. …」图注留在正文里，图没有编号 | `take_caption()` 只认 `**图 N**　…` | 兼容 `图 N. …` / `图 N：…`（要求有分隔符，避免误吃「图 1 显示了……」这类正文） |
| 符号表某行变成 `\textbackslash{}` 乱码、符号数归零 | Markdown 表格 `split('|')` 把 `$\\|\boldsymbol{X}-\boldsymbol{x}\\|$` 里的 `\|` 当列界 | `split_md_row()` 先给 `$…$` 片段占位再切列，切完还原 |
| 附录超长 Python 字典表撑出 793pt | `tabular` 用 `l` 列，长单元格不换行 | `tabular` 套 `\ifdim\width>\linewidth` 自适应 `\resizebox`（`longtable` 不能这么包） |
| 单元格里满是 `\&\#x27;` | MinerU 把单引号抽成 HTML 数字实体 | `esc()` 先解码 `&#xNN;` / `&#NN;`，再逐字符转义 |
| 证明末行 `\tag{□}` 撑出 23.9pt | 非数字 tag 未识别，`align*` 末行太长 | tag 正则放宽到 `[^}]*`、`□`→`$\square$`，含非数字 tag 的组整组 `\small`（`align*` 内不能整行缩放） |
| `\text{}` 里英文词间有 2–3 个空格 | 抽取器把字距化成了空白 | body 生成后压回单空格，不动 `\;` / `\quad` |
| 两篇同时编译时其一留下 0 字节 PDF | 两个 XeLaTeX 并行，日志无 `!` 错误、极难诊断 | `--pdf` 加跨进程锁（锁文件写「pid 过期时间戳」，靠过期兜陈旧锁，不依赖删除文件） |
| PDF 正文里出现字面的 `<sup>1</sup>` | MinerU 把作者机构角标/脚注引用抽成 HTML 上标，LaTeX 文本模式原样排出 | 译文阶段按脚注规则清理（原稿与译文同步删或补脚注文字），`fidelity_check.py` 硬校验拦住；`md2tex.py` 的 `inline()` 另有兜底，把残留 `<sup>n</sup>` 转成 `\textsuperscript{n}` |
| 编译到第 11 页突然停住，`! Internal error: bad native font flag`，日志里 0 条 `!`、也没有 `Output written` | 数学里的旧式 `\bf`（OCR 原样带过来的，如 `${\bf \dot{\mu}}_1$`）把编码切到 TU 文本字体，再用它排希腊字母，XeTeX 内部断言失败。**这类错误只写 stdout，一个字不进 `.log`** | `md2tex.py` 把数学片段里的 `\bf` 换成 `\bm`（bm 包，语义相同、不切编码）；`verify_pdf.py` 正面检查日志有没有 `Output written`，没有就判失败 |
| 日志刷出几十条 `! Package fontspec Error: The font "TeX Gyre Termes" cannot be found` | TeX Gyre 只装在 texmf 里，没装进系统字体目录，按**字体名**加载查不到（Windows 上必现）；退回默认字体后 PDF 能用，但字号与字宽全变了 | `\setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, …]`：按**文件名**走 kpathsea，跟系统装没装字体无关 |
| 书目里 `Marx's` 显示成 `Marx’ s`，撇号后面多一个空隙 | U+2019 被 xeCJK 归进中文标点类，与西文字母相邻时按全角排 | `\xeCJKDeclareCharClass{Default}{"2019}`：只把这一个字符移出标点类，中文双引号 `“”` 仍按 CJK 处理 |
| 加了参考文献节，PDF 里却只剩一个空的「参考文献」标题 | 书目识别只认 `## 参考文献`／`## References` 三种写法，`split_refs --restore` 给的是 `# 参考文献`（一级），认不出就把整段当正文 | 标题级别放宽到 `#{1,6}`，中英与 bibliography／works cited 都认；取**最后一个**匹配，避免附录里 "see References" 误判 |
| 书目拼回后，全篇脚注静默消失 | 脚注定义（`<!-- 脚注定义 -->` + `[^n]:`）跟在书目后面，被当成书目行收走，正文里就找不到 `\footnote` 的文字了 | 书目区遇到 HTML 注释或 `[^n]:` 定义就截断；收条目时再过滤一遍 |
| `--heading 参考文献` 拼出来的那行没有 `#`，Markdown 里成了普通段落 | 参数值被原样当整行写入，没有沿用原标题的井号级别 | 值不以 `#` 开头时自动补上原标题的级别（`#` 还是 `#`，`##` 还是 `##`） |
| 表头「第 I 部类」「第 II 部类」与下面的 5 列数据整体错开一格 | HTML 表格的 `colspan="2"` 被丢掉，两个部类名各占 1 列，挤到「剥削率」和「剥削形式」上面 | 解析 `<td colspan>`，生成 `\multicolumn{2}{c}{…}`；列数按跨列数求和 |
| 表格里印出字面的 `μ2 &lt; μ1`、`μ2 &gt; μ1` | `esc()` 只解数字实体（`&#x27;`），不认命名实体；而裸 `<` `>` 在文本模式会排成 `¡` `¿` | 先 `deent()` 解 `&lt;`/`&gt;`/`&amp;` 等命名实体，再把 `<` `>` 一律转成 `$<$` `$>$` |
| 表格第一列的 `μ1`、`μ2` 下标掉成正文数字 | MinerU 把 `$\mu_1$` 抽成了裸文本 `μ1` | 表格单元格里的 `μN` 写成 `$\mu_N$`；这类整块是 OCR 缺陷，md2tex 不猜，译稿阶段修 |

同理，正文里若出现「术语一览中文简述」的括注（如 `…(PFNs)（一种在模拟数据上预训练…）`），属于规则 6 的「增」：`fidelity_check.py` 会拿简述列去正文反查 `（简述）` 形态并硬失败。简述只属于表，不属于正文。

**脚注渲染**：译文用 Markdown 脚注语法——正文写 `[^n]` 引用（紧跟被注词句、句读之前），文末写 `[^n]: …` 定义，**没有 `## 脚注` 标题，也不带「第 N 页脚注 n：」页面前缀**。`md2tex.py` 把带引用的 `[^n]` 转成页底 `\footnote{…}`；只有 `--footnotes endnote` 或显式 `--allow-orphan-notes` 时才退成 `\noindent\textsuperscript{n}\, …\par` 的文末段落。不要写 `<sup>n</sup>`：那是 MinerU 的 HTML 提取产物，`inline()` 虽有兜底转换，`fidelity_check.py` 的正文卫生硬校验仍会拦。脚注文字本身由 `footnote_recover.py` 从 `content_list.json` 恢复，见 [mineru.md](mineru.md) 第三节第 4 条。

**仍要人工判断的**：图片本身是位图、图内英文标注不可检索；原文自己的公式/表格缺陷照原样保留；语义与润色不在脚本范围内。
