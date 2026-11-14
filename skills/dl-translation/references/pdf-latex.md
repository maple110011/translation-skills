# 从译文 Markdown 编译 PDF（版式尽量贴近原文）

只在用户要 PDF 时才做。目标不是"排得好看"，而是**让中文读者看到的版面结构与原论文一致**：公式编号右对齐、多行推导等号对齐、图并排、引文可跳、书签可用。

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex \
    --source-pdf <原文>.pdf --pdf
# --pdf 会自动跑两遍 xelatex（第一遍定页码书签，第二遍定交叉引用）
```

前置：TeX Live（`xelatex` + ctex + `\usepackage{ctex}` 所需的字体）。Windows 用 `fontset=windows`，其他平台脚本会自动切 `fandol`。
元信息优先取译文 front matter（`title_zh` / `title` / `authors` / `journal` / `source_sha256` / `source_file`），缺的用命令行补：`--title-en --authors --venue --doi --arxiv --citekey`。

---

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

- 并排图用 `<table><td>` → `minipage` + `\includegraphics[width=\linewidth]`，宽度由脚本按图片张数分配（1 张 0.93、2 张 0.48、3 张 0.33）。**不要在 md 里依赖 `<img width="32%">` 控制宽度**（百分比相对所在 `<td>` 会塌成 0 宽）；写了也不影响解析。
- `<img>` 属性顺序任意（`src` / `width` / `alt` 怎么排都行），裸 Markdown 图 `![alt](path)` 与块内 `![](path)` 同样识别。图注认 `**图 N**　…` 和 `图 N. …` 两种写法。解析不到图片时脚本宁可只留图注文字，也不排「只有 caption、没有图」的空 `figure`。
- 宽矩阵、宽公式一律走 `\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{$\displaystyle …$}`，比按源码长度猜阈值可靠。
- `align*` 里不能对整行 `\resizebox`（会破坏对齐）；实测在 align 单元里 `\sbox{0}{...}` 量宽度会踩坏 amsmath 的盒子寄存器，报几百 pt 的 overfull——要么整组退 `gather*`，要么别对齐。
- **长表必须分块**：`table[H] + tabular` 不能跨页，几十行的附录表会被整块截断，而编译仍是 0 个 `!` 错误，日志里只留一句 `Overfull \vbox`。脚本按 **45 行**自动拆成多个各自可落页的 `table`，续块重复表头、只第一块挂 `\caption`（其余用 `\caption*{（续表）}`）。`longtable` 不是万能替代：多列宽表格改等宽 `p{}` 列会把方法名压在数字上。验收时**必须同时查 `\vbox`**，只数 `\hbox` 会漏掉整块数据丢失。

## 六、验收清单

1. 编译 **0 个 `!` 错误**；`Overfull \hbox` 只允许 1pt 以内的（多半是标点挤压）；**`Overfull \vbox` 必须为 0**（出现就是整块长表被截断，数据丢了）。
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

同理，正文里若出现「术语一览中文简述」的括注（如 `…(PFNs)（一种在模拟数据上预训练…）`），属于规则 6 的「增」：`fidelity_check.py` 会拿简述列去正文反查 `（简述）` 形态并硬失败。简述只属于表，不属于正文。

**脚注渲染**：译文用 Markdown 脚注语法——正文写 `[^n]` 引用，文末 `## 脚注` 节写 `[^n]: 第 N 页脚注 n：…` 定义。`md2tex.py` 把 `[^n]` 转成 `\textsuperscript{n}`，定义行排成 `\noindent\textsuperscript{n}\, …\par`。不要写 `<sup>n</sup>`：那是 MinerU 的 HTML 提取产物，`inline()` 虽有兜底转换，`fidelity_check.py` 的正文卫生硬校验仍会拦。脚注文字本身由 `footnote_recover.py` 从 `content_list.json` 恢复，见 [mineru.md](mineru.md) 第三节第 4 条。

**仍要人工判断的**：图片本身是位图、图内英文标注不可检索；原文自己的公式/表格缺陷照原样保留；语义与润色不在脚本范围内。
