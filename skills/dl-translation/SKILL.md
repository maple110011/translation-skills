---
name: dl-translation
description: 把英文的深度学习、机器学习、数学、统计学论文译成中文 Markdown，以准确为第一目标。公式与符号逐字符保真、定理/引理的条件与结论强度不走样、术语全文一致；没有通行中文译名的关键术语与概念保留英文原文、不造词，并在译文开头列「保留英文术语一览」；图、表按正文首次引用就近重定位，不再沿用 PDF 的浮动排版位置。译文开头另附「符号一览」。不做润色、不做本土化，允许翻译腔。输入可为 PDF、已提取的 Markdown、docx；输出正文段落与源文一一对应、引用原样，并对公式做逐条机械比对。Use when translating papers with formulas, theorem-proof structures, algorithm pseudocode and experiment tables (deep learning, machine learning, probability, statistics, optimization, mathematics) into Chinese under strict accuracy constraints, when untranslated key terms must be kept in English, when figures/tables must be moved next to their first citation, when a notation table has to be produced alongside the translation, and when a MinerU extraction step is needed first.
agent_created: true
---

# 深度学习·数学·统计学论文翻译

把一篇英文论文变成一份**能用来做推导、复现代码、复审证明**的中文 Markdown。

难点不在英文，在四件事：**公式不可改写**——差一个下标就不是同一个命题，而中文读起来毫无破绽；**定理的全部信息在条件与强度里**——省半句，结论就从"有条件成立"变成"无条件成立"；**符号全文复用而读者会回头查**——这就是开头那张符号表的作用；**没有通行译名的术语要保留英文**——造一个中文词，等于替读者做了一次不可逆的裁定。

顺序是**先不错，再读得通**：不追信达雅、不做本土化、允许翻译腔。

<what_this_skill_is_for>
**适用**：期刊/会议论文、arXiv 预印本、技术报告、教材章节、讲义、学位论文的英译中；正文含公式推导、定理—证明结构、算法伪代码、实验表格；译文要给导师、审稿人、项目组或自己长期查阅。

**不适用**：中译英（对账逻辑假定源为英文）；人文社科与文学（重点是语气与概念史，取舍相反）；只要摘要或要点；纯 LaTeX 工程复刻与编译修复——本 skill 只把**已定稿的中文 Markdown** 编成版式贴近原文的 PDF（`md2tex.py`，见 [references/pdf-latex.md](references/pdf-latex.md)）；扫描件无可提取文字层且未 OCR。
</what_this_skill_is_for>

<non_negotiable_rules>
六条硬规则。违反任何一条，译文就不合格，不管读起来多通顺。**判据、反例与逐条清单在 [references/accuracy-rules.md](references/accuracy-rules.md)，这里只列不可让的边界。**

**1. 公式逐字符保真。** 不译、不改写、不"等价变形"、不重排。上下标、撇号、转置、范数、括号大小、间距命令、`\tag` 编号全部原样。`x^2-1` 不写成 `(x-1)(x+1)`，`\log` 不写成 `\ln`，`\|x\|_2` 不写成 `|x|`。只有空白与换行可动；定界符统一由 `normalize_math.py` 机械完成。

**2. 定理类陈述的条件与结论强度保真。** Theorem／Proposition／Lemma／Corollary／Claim／Definition／Assumption／Remark／Conjecture／Proof 各译其名，不得互换（`Proposition` 译"定理"就是抬高结论等级）。量词、范围、正则性条件、概率模式（a.s.／依概率／以至少 $1-\delta$ 的概率）、常数依赖（"只依赖于 $d$"）、一致性与均匀性，一样不能少。`if` / `only if` / `iff` 三档不得合并。

**3. 正文结构保真；浮动对象只许搬位置、不许改内容。** 正文段落与源文严格一一对应：不合并两段、不拆一段、不省略"重复"的过渡句；`#` 层数与顺序、列表、`>` 深度、代码块、粗斜体原样。`(Smith et al., 2020)`、`[12]`、`\cite{}`、参考文献条目逐字保留。图的**内部版式只许恢复、不许重排**：原文并排的面板要并排，独立的两张图不许合成一张，不许裁掉半边。

**4. 术语与符号全文一致；关键术语保留英文原文。** 动笔前定表，全文照表；同一英文词不得一处一个译法，也**不得一处保留英文、另一处译成中文**。没有通行中文译名的概念保留英文、逐字符照抄，不造词（见 `<english_terms>`）。同一符号不得"统一"成别的字母，`\hat{f}` 不得简写成 `f`。

**5. 准确优先于通顺，不做润色。** 不合并句子、不调换从句顺序（若改变条件辖域）、不把被动改主动（若施事有意模糊）、不删重复、不改逻辑连接词（thus/hence/therefore 各有对应）。允许翻译腔，允许长句不拆；唯一底线是句子能读通，不能是病句。

**6. 不增不删，不替作者补步骤，不静默修正原文。** 不加原文没有的解释、背景、过渡句、译者按语。原文的符号前后不一致、假设与证明对不上、编号跳号——照原样译，写进"原文疑点"。两个例外：① **提取错误**（上下标压平、`O(n)` 误识为 `0(n)`、上标抽成 `<sup>`）以 PDF 为准改正并记账；② 译文开头的 YAML 元信息、符号一览、保留英文术语一览，用 HTML 注释包住，脚本会先剥掉，不算正文增写。

**`keep` 术语的中文简述只能写进「保留英文术语一览」的简述列，正文任何位置（包括首次出现）都不许补括注或同位语**。哪怕只有一句、哪怕不带原文没有的信息，那也是正文增写：`fidelity_check.py` 会拿简述列去正文反查 `（简述）` 形态，一出现就是硬性失败。
</non_negotiable_rules>

<accuracy_first>
这一节写"不要做什么"。它与常见的翻译习惯相反，所以要显式说明。

**不做的事**：不为顺口把两句话合成一句（"条件—结论"两句结构一合，条件常退化成插入语）；不把 `for all $n \ge n_0$`、"for sufficiently large $n$" 挪到句末或省掉；不把 `with high probability` 译成"大概率"（它是概率模式，不是口语里的"很可能"）；不把 `up to a constant` 译成"近似地"；不"统一"看似重复的符号；不在正文加译者注、"需要注意的是"或总结句；不在数学模式里写中文（原文已有的 `\text{}` 除外）；不给无通行译名的术语硬造中文词（"先验数据拟合网络"这类自造词，读者既查不到原文也没法与文献对上）；不把图表留在 PDF 的浮动位置上。

**可以做的事**：拆长句、补汉语必需的虚词、把名词化表达还原成动词——只要信息量完全等价、不改变条件辖域与指代；保留原文的重复与啰嗦；读起来略生硬。
</accuracy_first>

<english_terms>
**默认动作是"不译"。** 前沿论文里大量概念没有通行中文译名：作者自造的方法名、近两年新出的架构与指标、跨领域借来后含义变了的词。硬造一个中文名，等于替读者做了一次不可逆的术语裁定——他既查不到原词，也没法与英文文献、代码、检索结果对上。**一篇论文保留 10–30 个英文术语是正常密度**；只有两三个，反倒说明该保留的也被译掉了。

**一句话判据**：查项目表与种子表 → 有 `已定` 译法**且该译名在中文文献里确实通行**就译；**其余一律默认 `keep`**。判断"通行"只问一句：这个中文词丢进知网/谷歌学术，能不能检索到同一批论文？检索不到就是自造，改回 `keep`。

**登记方式**：`_work/<stem>_术语.csv` 用 `dst=@keep`、`kind=keep`、`status=已定`。此时 `alt` 列的语义变成**禁止出现的中文写法**（`|` 分隔），`fidelity_check.py` 见一个报一个，并反向检查该英文串确实出现在正文里（没出现＝漏了或误译）。

**译文开头必须有「保留英文术语一览」**，紧跟符号一览、同样用 HTML 注释包住；英文列与正文逐字符一致，简述列不得回填正文：

```markdown
<!-- kept-terms:start -->
## 保留英文术语一览

| 英文原文 | 中文简述 | 出现范围 |
|---|---|---|
| prior-data fitted networks (PFNs) | 在模拟数据上预训练、推断时固定的网络 | 全文 |
| in-context learning (ICL) | 不更新参数、由上下文提供训练信号 | 全文 |
<!-- kept-terms:end -->
```

判据表（哪些保留、哪些照译）、学科分流、标题与图注里的处理、项目表六列写法见 [references/terminology.md](references/terminology.md)。符号一览管记号、这张表管词：符号表「含义」列里若出现已 `keep` 的概念，直接写英文串，不要替它造中文名。
</english_terms>

<notation_table>
译文开头必须有「符号一览」，这是硬要求不是装饰：读者读到第 5 页要回查 $C$ 是什么，只有这张表能回答。位置在 YAML 之后、正文第一节之前，用 HTML 注释包住：

```markdown
<!-- notation:start -->
## 符号一览

| 符号 | 含义 | 出现范围 |
|---|---|---|
| $n$ | 样本量 | 全文 |
| $\hat{f}$ | 由训练集得到的估计 | 第 3 节起 |
| $\|\cdot\|_2$ | 欧氏范数 | 全文 |
<!-- notation:end -->
```

三条硬要求：**每格符号用 `$…$` 包住**（否则上下标会掉）；**符号串与正文逐字符一致**（`\hat{f}` 不是 `f`，`\mathbb{E}` 不是 `E`）；**竖线转义**成 `\|x\|` 或 `\Vert x\Vert`（写成 `|x|` 会被当列分隔符，且含义也变了）。另按**首次出现顺序**排、不按字母序；只收需要查的——$\mathbb{R}$、$\mathbb{N}$、$\mathbb{E}$、$\nabla$、索引 $i,j,k$ 不收（带下标的算子要收，$\mathbb{E}_{\Pi}$ 与 $\mathbb{E}$ 不是一回事），一篇 12–20 行为常态，超过 25 行先怀疑收宽了。

**注释包裹不是格式洁癖**：符号表是本次翻译新增的，原文没有；`fidelity_check.py`、`math_fidelity.py`、`notation.py` 靠这两个标记把表剥出去，否则结构对账会报"多了一个标题和 N 行表格"，公式比对会把表里的 `$n$` 当成"多出的公式"。收什么不收什么、与原文 Notation 节怎么相处，见 [references/notation.md](references/notation.md)。
</notation_table>

<figures>
Markdown 的图像语法是行内元素：没有宽度、没有图注、没有面板。而论文的一张图是复合对象（图像 + 图注 + 子图说明 + 正文里的"图 N"引用），抽取器按阅读顺序输出，四样就散开了。三种坏相：**拆散**（四面板图变四张竖排摞下来）、**游离**（图注跑到图上方或隔了三段）、**裸图**（图后没图注，正文引用指向空气）；另有一种不是结构问题但同样致命：**宽图被压小**，图里的刻度读不出来。

四条底线：**一个逻辑图 = 一个图块 + 一段紧跟其后的图注**；图注紧跟图，中间不插正文；图号与正文引用对得上；图块紧跟首次引用它的段落。判断"一个逻辑图"还是"N 个独立图"看原文图注：**一条图注里带 `(a)(b)(c)` 的是一个逻辑图**（哪怕被抽成四张图）；四条独立图注的是四个图，不许合并。

多面板图被拆散时，用无边框 HTML 表格恢复并排，并用 `<!-- figure:start -->` / `<!-- figure:end -->` 包住——`fidelity_check.py` 靠它把整块折成"一处"（否则一张四面板图会被算成"多出四张图"），`figures.py` 靠它识别已处理的块。**图注留在块外**当普通段落（塞进 `<figcaption>` 会让对账把它连同图一起折叠，段落数就错位）；**`alt` 必填**，格式「图 N(子图号) 一句描述」。

```bash
python scripts/figures.py audit 原文.md 译文_zh.md --csv _work/图目录.csv  # 图注数/图号/位置/引用/文件/alt
python scripts/figures.py group 译文_zh.md --apply                         # 连续裸图合成并排（先不带 --apply 看计划）
python scripts/figure_layout.py _work/extract -o _work --md 译文_zh.md     # 只出宽度清单，不改 md
```

**并排只是第一步，宽度和底对齐还得按原刊来。** 交付 PDF 常有三个毛病：三栏图被拆成三张各占 0.93 栏宽的图、附录里只占半栏的图被拉满整栏、`\caption` 自增出来的图号与正文"在图 6 中"打架。`figure_layout.py` 从 `content_list.json` 的 `bbox` 算出每张图占正文栏宽的比例（**栏宽取该页最宽文本块**；取中位数会被只有标题的附录页拉到几十磅，宽度反而更离谱），`md2tex --fig-meta` 据此定宽，多联图按各栏真实比例分配（实测 41%/27%/27%），不是等分；图注里的 `**图 N**` 同时转成 `\setcounter{figure}`，PDF 图号才跟译文正文一致。**`figure_layout.py --apply` 与 `figures.py group` 二选一**，同一份稿里两种写法别混用。

子图说明照译并保持 `(a)(b)(c)` 结构；烧在位图里的**不补写**（补写就是"增"），在报告里注明。宽图像素宽度不足约 1200px 的，回 PDF 用 `pdftoppm -r 300` 按图区域重裁，放大位图只会更糊。表格：多级表头与合并单元格用 HTML 表格，数字列右对齐，表注单独成段紧跟表下。完整规范、HTML/CSS 模板与交付清单见 [references/figures.md](references/figures.md)。
</figures>

<code_blocks>
伪代码的全部信息在**缩进**和**行序**里：循环体没有缩进，读者就看不出哪几步在循环内；两步并作一行，"第 3 步算梯度"就查不到。所以代码块不是"一段特殊正文"，而是**版式对象**，和公式同级。

三条硬要求：**一块一围栏**——不许合并两块，不许把块内文字摊成正文段落；关栏漏写，其后所有正文都会被当成代码，结构对账静默失效。**缩进、行序、步号逐字保留**——空格还是 tab 照原样、深度不变，一行步骤不许并进上一行；空行可删（空行不承载信息），非空行一行不能少。**语言标记照抄**——原文 `python`/`r`/`text` 就写 `python`/`r`/`text`，原文没有就不加。

两类文本待遇不同：**伪代码**（`Algorithm` 环境：`Require`/`Ensure`/`for`/`end for`）结构与关键字不动、**注释可译**，`Require`/`Ensure` 译"输入／输出"或"要求／保证"，一篇之内统一；**真代码块**（Python、R、Shell）**连注释都不动**——代码就是代码，译了就跑不起来。行内代码 `` `np.random.seed(0)` `` 保留反引号、内容不译、不拆句。**两者都不是浮动对象**，位置跟着正文段落走，不参与就近重定位。

MinerU 对算法框的表示不是围栏，而是 `<div class="mineru-algorithm" style="white-space: pre-wrap">`：**必须保留 div 外壳与 `class`/`style`**（`md2tex.py` 靠 `mineru-algorithm` 认出它，删了就只能当正文排，标签还会印到纸上），里面的步号、行序、缩进空格、`$…$` 一律不动。提取器把算法框按阅读顺序压成散文（`Algorithm 10.4 (…). The … can be computed …`）时，源文自己就没有格式可保，**回 PDF 恢复版式**：一步一行、缩进照 PDF 的层级、语言标记用 `text`，内容一字不改，并在交付报告里记一句——这不是"增"，和补回被过滤的页底脚注同一性质。

**反例（不许出现）**：整块伪代码被压成一句散文，步号变成分号分隔，缩进与层次全丢——可复现性随之消失。

渲染端：`md2tex.py` 把围栏块排成 `codeblock`（verbatim，缩进与反斜杠原样、不做转义）、算法 div 排成逐行算法块（连续空格换 `\hspace*` 还原层级）、行内代码排成 `\texttt`；`verify_pdf.py` 再核每块首行是否进了 PDF 文本层。判据、四类差异（块数/行数/缩进/语言标记）与恢复流程见 [references/accuracy-rules.md](references/accuracy-rules.md) 第 4 节。
</code_blocks>

<floats_reflow>
PDF 为了不拆段落、不浪费版面，把图表浮动到页顶页底甚至下一页，与正文"如图 3 所示"能隔好几页；抽取器按阅读顺序把这个距离原样带进 Markdown。**Markdown 没有页、没有栏、没有浮动体**，这个约束不该保留。

**规则**：把每个浮动对象（图片／并排图块＋图注＋子图说明、表格＋表注）整体移到**正文中第一次引用它的段落之后**，图注仍紧跟图块、表注仍紧跟表格。一条图被多处引用时以**首次**为准；**正文完全没引用的**（封面图、附录无编号图）保持原位，列进报告的"未就近对象"，不猜位置；原本就紧挨引用段（≤3 行）的不动，脚本判为"原本就近"；`relocate` 先跳过 front matter 再找锚点，不会把图搬到文件开头。

**只搬位置，不搬内容**：图片路径、`alt`、`width`、面板并排关系、图注文字与编号、表格行列与数值、正文段落内容与顺序，一个都不改。搬完图号与交叉引用不变，所以正文引用不用改。

**由脚本执行，不要手工拖拽**（手工搬容易把图注落下、把两块图叠在一起）：

```bash
python scripts/figures.py relocate <stem>_zh.md --csv _work/图表重定位.csv          # 先看它打算搬哪几块
python scripts/figures.py relocate <stem>_zh.md --apply --csv _work/图表重定位.csv  # 写回；幂等
```

脚本给搬过的块加一对 `<!-- float:moved fig=3 anchor=L214 -->` … `<!-- float:end -->`，三个用途：`relocate` 判幂等、`figures.py audit` 核就近性、`fidelity_check.py --float-reflow` 把浮动块从块序列剥离后单独核对。那个参数只放宽"浮动对象的位置"，**正文段落的块序列仍须逐块一致**——删一段、合并两段照样硬失败。判据表与边界见 [references/figures.md](references/figures.md) 第 2 节。
</floats_reflow>

<workflow>
按顺序执行。每步都有产物，下一步读上一步的产物，不要跳步凭记忆往下写。

## 第 0 步：确认源与交付

- 源优先级：**出版版 PDF > 作者提供的 tex/docx > MinerU 提取的 Markdown**。三者冲突以 PDF 为准，提取结果只是工作草稿。
- 交付默认 Markdown（含开头符号一览与 YAML front matter）；**PDF 是可选交付，不是自动步骤**——用户没说格式就顺口问一句「要不要 PDF」，别事后补做。
- 输出放源文件同目录，命名 `<stem>_zh.md`；中间产物放 `_work/`。用户没说清只问一次，不要为格式细节来回确认。

## 第 1 步：取得可译的正文

**已有 Markdown** → 直接用，先扫提取缺陷：公式是否成了图片、`\begin{align}` 是否塌成一行、表格是否塌成纯文本、脚注是否丢失、上下标是否被压平（`x_i^2` 变成 `xi2`）。

**有 arXiv 版本（首选）** → 直接取作者源码，别从 PDF 抠：

```bash
python scripts/arxiv_src.py 2207.01848 -o ./_work/arxiv
```

产出 `main.flat.tex`（已展开 `\input`）、`figures/`、`结构清单.md`、`脚注.csv`。清单里有一行**「算法/代码环境」**，那就是译文该有的围栏代码块数量：`\begin{algorithm}` / `algorithmic` 里的 `\State`/`\For` 要按 [references/arxiv-source.md](references/arxiv-source.md) 的对照表**一行一步转成代码块**，别当正文译。**先确认版本**：一个包里常有好几个可编译主文件，`main.tex` 未必是手上那篇 PDF 的版本；用章节数、附录范围、图表数与 PDF 比对，对不上就 `--main`。arXiv 版常比会议版多附录、多脚注，**以哪版为准要问用户**。

**没有源码或版本对不上** → `python scripts/mineru_extract.py paper.pdf -o ./_work/extract --model vlm`（首次运行引导录入 token，`--token-status` 可查）。参数与排障见 [references/mineru.md](references/mineru.md)。

**脚注必须一条不落，但两条路线来源不同。** 走 tex 路线时脚注不在 `content_list.json` 里，`footnote_recover.py` 那条链路走不通：脚本已产出 `脚注.csv`（`page` 为空），填 `zh` 后回填译文，条数须与结构清单「脚注明细」相等，`fidelity_check.py` 加 `--skip-footnote-check`，完整性改由**条数相等**保证（见 [references/arxiv-source.md](references/arxiv-source.md) 第三节）。

走 PDF 路线时**提取完立刻恢复脚注**（硬性，动笔之前）：MinerU 的版面识别认得出页底脚注（`content_list.json` 里 `type=page_footnote`），但生成 `full.md` 时按类型白名单把它**整类过滤**——正文常只剩 `<sup>n</sup>`，脚注正文 100% 丢失。脚注里常有条件、假设、复现链接，漏掉等于改条件。

```bash
# 1) 恢复并把标记锚进正文、定义落到文末（--pdf 可选，做文字层交叉验证）
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf
# 2) 填 脚注_待译.csv 的 zh 列（中文脚注译文），再回填
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check
# 3) 脚本判不出位置的：填 脚注_待锚.csv 的 anchor 列（正文里紧邻标记前的一句原话）后回灌
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --target <stem>_zh.md --apply --place _work/脚注_待锚.csv --check
```

`--apply` 把正文 `<sup>n</sup>` 归一成 `[^n]`、把每条标记**锚进正文对应句子**、把 `[^n]: 脚注正文` 定义放在文末，**不写 `## 脚注` 标题、不写「第 N 页脚注 n：」页面前缀**（页码只留在 `脚注.csv`）。写回前留 `.bak_footnotes` 备份且可重复运行；译文侧未填中文时定义行留 `<!-- 待译 -->`，`--check` 因此返回 1。旧稿的「文末补一节」会自动迁移。作者机构／版权注常与正文脚注同号，不占 `[^n]` 编号，单列 `脚注_原刊信息.md` 不进交付稿；`noise`（如 `40<sup>th</sup>`）不补。

**标记必须落进正文**：脚本只确定性处理 `<sup>n</sup>`；句末裸数字、塞进行内公式的 `^{7}`、提示语对不上的会进 `脚注_待锚.csv` 并让 `--check` 返回 1（确认是裸编号/公式残留可加 `--anchor-bare` / `--anchor-math`）。**宁可阻塞，也不要把标记塞到段末**——脚注落错句子比缺一条更坏。

**这一步不可跳过**：`fidelity_check.py --strict` 硬查 `脚注.csv` 存在，并逐条核每条脚注**既有 `[^n]:` 定义、又有正文 `[^n]` 引用**（悬空定义、孤儿标记、编号乱序、`## 脚注` 残留、`<sup>` 残留都拦）。豁免只有两种：纯 Markdown 输入无提取包；或走 arXiv 路线——都要显式 `--skip-footnote-check`，并在报告写明理由与替代判据。

**有 docx** → pandoc 转 Markdown，同样查公式与表格。

提完**必须对照 PDF 抽查**：段落数、公式、表格、脚注。数学论文的提取错误集中在三处——多行公式被切碎、正体斜体被抹平、参考文献年份并入正文。提取错了再译，等于把错误洗进译文。

## 第 2 步：定术语与符号（动笔之前）

这一步的目的是消灭"边译边定"——术语不一致的唯一根源。

```bash
python scripts/extract_terms.py 原文.md -o _work/ --glossary references/glossary --min-count 3
python scripts/lookup_term.py "excess risk" "consistency" --glossary references/glossary/
python scripts/notation.py extract 原文.md -o _work/符号候选.csv   # 先抽再读；通读找符号又慢又漏
```

种子表三份（数学/统计/机器学习）约 400 条，带 `status`（`已定`/`待裁决`）与 `note`；`待裁决` 的要你选一个，记进项目表。**项目表定稿后再动笔**：`_work/<stem>_术语.csv`（`src,dst,alt,kind,status,note`）是此后每一块的唯一依据，只收本篇真正用到的 20–40 条——要进表的是**换一种译法读者会理解成另一个概念**的词，`data`/`model`/`result` 不进表。

`extract_terms.py` 的 `keep_default=yes` 把"种子表查不到既有译法"的候选标出来，**这些默认保留英文**。逐条判定：有 `已定` 译法且通行 → 照译 `kind=term`；有权威依据 → 定译名并把依据写进 `note`；**其余全部** → `dst=@keep`、`kind=keep`、`status=已定`，`alt` 填不许出现的中文写法。判完把 `kind=keep` 抄成译文开头那张表。**这一步不做，后面就会边译边造词**——第 2 页"上下文学习"、第 12 页"语境内学习"，谁也查不回去。学科分流规则见 [references/terminology.md](references/terminology.md) 第 2 节。

## 第 3 步：搭符号表骨架，再分块翻译

**3.1 先把两张表写进译文开头。** 读完摘要、引言与"问题设定"节，就能把主记号（$n$、$d$、$x_i$、$\theta$）与本篇的 `kind=keep` 术语定下来。先写表再翻译：后面不必回头补，表的"含义"列还会反过来约束术语选择。

**3.2 分块。** 以 `##` 二级标题为界；单块超过约 3000 字（中文）再按段落切。切口不要落在 `$$` 块、`align` 环境或 `cases` 中间。每块开工前读**上一块末尾三段**，保证代词、术语、符号不断裂。

**3.3 逐块落地的规矩**

1. 读一块 → 数清段落、列表项、行间公式、表格、定理各几处 → 译 → **立刻按同样的段落数写回**。不要整篇译完再拼，对不上账时无法定位。
2. **段落一进一出。** 英文常把一个论点塞进一个长段，中文读者习惯分开——但不能分，只能在段内调节。
3. **标题译，`#` 数量不变**，编号保留，标题里的术语照项目表。
4. **行间公式整块不动**（含 `(3)`、`\tag{3}`）；**行内公式不改行间**，否则段落结构与公式编号都会错位。
5. **定理环境照标签译**：`**Theorem 2.1.**` → `**定理 2.1.**`，编号不变；`*Proof.*` 保留标记、内容照译。
6. **伪代码/代码块**：结构不动，按 `<code_blocks>` 处理；被压成散文的先恢复版式再译。
7. **表格**：表头译，数字、单位、`±`、星号显著性、括号里的标准误原样，表注照译。
8. **图片**：`alt` 译成「图 N + 一句描述」，路径一字不改；多面板被抽散时按 `<figures>` 拼并排。
9. **脚注**：内容照译，标记只用 `[^n]`，**不要写 `<sup>n</sup>`**（交付稿与 PDF 里都不许出现字面 `<sup>`）；第 1 步已锚好，这里只填中文。作者角标、版权与会议声明不占编号；断词与 URL 空格按"以 PDF 为准"处理并记账。
10. **引用块 `>` 层级保留、内容译**；参考文献条目、`\cite{}`、`[12]` 原样。
11. **`keep` 术语照抄**，大小写、单复数、连字符与原文该处完全一致；不确定某符号指什么，回 `符号候选.csv` 与首次定义它的句子核对，不要凭印象。
12. **图表先按原位译完，位置最后统一搬**（3.4 用脚本一次性重定位），边译边搬会让段落编号与进度对不上。
13. **不写译者注**，需要说明的写进"原文疑点"。语体是学术书面语，但不为顺口改写逻辑关系（判据见 [references/accuracy-rules.md](references/accuracy-rules.md) 第 7 节）。

**3.4 全文译完后，把浮动对象移到引用段落附近**

```bash
python scripts/figures.py relocate <stem>_zh.md --apply --csv _work/图表重定位.csv
```

看 CSV：每块从哪行搬到哪个锚段落、有没有"无正文引用"的块（保持原位、写进报告）。搬完再进第 4 步。

## 第 4 步：机械校验

译完（且跑完重定位）不算完。五个脚本，把机械错误挡在人工校对之前。

```bash
python scripts/normalize_math.py <stem>_zh.md --inplace                                        # 1) 定界符统一（幂等）
python scripts/math_fidelity.py <stem>_原文.md <stem>_zh.md --csv _work/公式差异.csv --strict   # 2) 公式逐条
python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --float-reflow --strict                                    # 3) 结构对账
python scripts/notation.py check <stem>_原文.md <stem>_zh.md --csv _work/符号缺漏.csv            # 4) 符号表
python scripts/figures.py audit <stem>_原文.md <stem>_zh.md --csv _work/图目录.csv               # 5) 图审计
```

**`--float-reflow` 是重定位之后必带的参数**：不带它，搬过的图表行会让块序列对账报"结构不一致"；带了它，双方浮动对象剥离后逐块比对正文，再按多重集合核对图片路径、图注编号与表格行数。它同时检查 `kind=keep` 术语：英文串在正文出现、`alt` 里禁止的中文写法没有出现。

**`math_fidelity.py` 是核心检查，不是可选项。** 它把每一处公式抽出来按顺序对齐、逐字比较，差异分四类：**缺失/多出**（必须补删）、**内容不同**（必须改回）、**微差**（只差一两个字符——上下标、重音、不等号方向——最危险，必须逐字核）、**文内文字不同**（只有 `\text{}` 里的说明不同，一篇之内统一即可）。它还核 `\tag` 序列、`\label`/`\ref` 集合、`$` 是否成对。**差异清零才算过。** 同一句里挪动公式位置不算差异：脚本会把落单而内容相同的配回来，单独报"仅位置调整"；若这个数字很大，那不是翻译，是重排。

**口径要分清**：块结构、引用、公式、**代码块**（围栏未闭合／块数／行数）、正文卫生、脚注门禁是**真硬校验**（`--strict` 返回 1）；代码块内缩进与代码记号、语言标记丢失、"行首 Algorithm N 但无围栏"、疑似未译段、段长异常、术语一致、`notation check`、`figures audit` 是**建议性发现**（误报多，只打印不拦）。要零容忍给 `fidelity_check.py` 加 `--strict-soft`。`figures.py audit` 全绿之后，只剩"宽图会不会被压小"要眼睛看。

**脚本判不了的事情，人工过一遍**：公式里每个符号指的事对不对、定理条件有没有少、数值与表格有没有被"简化"、中文能不能读通。清单见 [references/review-checklist.md](references/review-checklist.md)。

## 第 5 步：审校清单与回填

有些判断不能替用户做，也不该悄悄做掉：**语义歧义**、**术语多译法**、**原文疑误**、**公式确认**。这一步把它们交出去，再把人的意见收回来。

**翻译时就记，不要等到最后补。** 开始第 3 步之前先建人工待校表：

```bash
python scripts/review_queue.py --init-manual _work/<stem>_人工待校.csv
```

遇到情况随手写一行（`位置,类型,原文,译法A,译法B,建议,理由`）：`多译法`（`sharp bound` 最优界／尖锐界）、`歧义`（`for any $x$` 任意／存在）、`学科分流`（`consistency` 相合性／一致性）、`原文疑误`（符号前后不一致、假设与证明对不上、编号跳号）、`符号冲突`（$T$ 步数／转置）。

```bash
python scripts/review_queue.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --manual _work/<stem>_人工待校.csv \
    --math _work/公式差异.csv --notation _work/符号缺漏.csv \
    --suggest _work/<stem>_候选术语_建议.csv \
    --resolved _work/<stem>_已决定.csv -o _work/<stem>_待校对.md
```

清单分五节（要你定的／公式差异／符号一览／术语不一致／候选术语），一条一个问题，下面留「你的意见：」。人回完后一条命令收口：

```bash
python scripts/review_apply.py --target <stem>_zh.md --glossary _work/<stem>_术语.csv \
    --decisions _work/<stem>_决定.csv --resolved _work/<stem>_已决定.csv \
    --source <stem>_原文.md --manifest _work/<stem>_待校对.md \
    --manual _work/<stem>_人工待校.csv --suggest _work/<stem>_候选术语_建议.csv \
    --math _work/公式差异.csv --notation _work/符号缺漏.csv
```

决定表列 `键,动作,旧,新,说明`，键四类：`term:<原文>`（改术语表；`旧` 非空时顺带把译文里的旧写法换掉）、`text:<任意>`（只替换译文；改公式也用它，写整段 LaTeX）、`candidate:<原文>`（`accept`/`drop`）、`manual:`／`math:`／`notation:`（`keep` 仅登记）。脚本一条龙改表改译文、重跑公式归一与三项校验、登记已决、重生成清单；**任何一条改不动都停下来报出来，不静默跳过**。

**交付时按这个顺序说**：必须你定的（给两种译法和各自后果，不要只说"请确认"）→ 建议确认的（证据薄的条目）→ 已按约定处理的（一句话带过）。**清单是空的也要说清空的是哪一层**——"机械检查零发现"只等于结构、公式、引用、术语都对得上，不等于译文没有问题。

## 第 6 步：交付与归档

| 文件 | 内容 |
|---|---|
| `<stem>_zh.md` | 译文：YAML front matter + 符号一览 + 保留英文术语一览；**脚注是正文内联 `[^n]` + 文末 `[^n]:` 定义**（无 `## 脚注` 节）；浮动对象已就近重定位；`normalize_math.py`、`math_fidelity.py`、`fidelity_check.py --float-reflow --strict` 全通过 |
| `_work/<stem>_术语.csv` | 本项目定下的术语、专名与 `kind=keep` 条目 |
| `_work/图表重定位.csv`、`符号候选.csv`、`公式差异.csv`、`符号缺漏.csv`、`图目录.csv` | 各脚本产物；公式差异清零后仍保留，作交付证据 |
| `_work/<stem>_待校对.md`、`<stem>_校对报告.txt` | 审校清单与三个校验脚本的原始输出 |
| `_work/脚注.csv`、`脚注_原文.md` | 第 1 步的脚注恢复清单，**交付证据**；缺失即被 `--strict` 判硬失败 |
| `<stem>.pdf`（可选） | 只在用户要 PDF 时产出 |

```bash
python scripts/paper_meta.py --init 原文.md -o _work/meta.yaml      # 生成草稿
python scripts/paper_meta.py --inject <stem>_zh.md --meta _work/meta.yaml
python scripts/paper_meta.py --check <stem>_zh.md                   # 查漏字段
```

**`title` 常常要手改**：MinerU 的 H1 有一半时候是期刊名或 "Preprint"，不是论文标题；`authors` 也人工填，脚本不猜，猜错比空着麻烦。

**front matter、符号一览、术语一览都不算"增"**：它们是文件属性与清点，标准渲染不显示、脚本会先剥掉。但边界要守住——只放元信息与符号/英文串，不许塞内容摘要、译者按语。

**交付时对话里只回复**：译文绝对路径；校验结论（公式几处逐字一致、结构是否通过、定理环境几条、符号表缺几条、`keep` 几条是否全部保住、浮动对象搬几处／几处无引用）；原文疑点与提取缺陷；没做的部分；**Zotero 挂载状态**。**不复述译文内容。**

### 可选：编译 PDF 版

用户要 PDF 时走这条，**不要临时手搓模板**——坑都写进脚本与 [references/pdf-latex.md](references/pdf-latex.md)：

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex \
    --source-pdf 原文.pdf --fig-meta _work/图片版式.csv --pdf
python scripts/verify_pdf.py _work/pdf/paper.pdf --tex _work/pdf/paper.tex \
    --md <stem>_zh.md --footnotes _work/脚注.csv
```

脚本已内置：图片/裸图/块内图与 HTML 表格适配、超宽表格自动缩放、公式分组对齐与 `\tag` 右对齐、符号表锚点与书签、**围栏代码块 → `codeblock`、算法 div → 逐行算法块、行内代码 → `\texttt`**、图宽按 `--fig-meta` 还原原刊比例、图号按原刊编号、`--pdf` 用跨进程锁串行化 xelatex（**两个 xelatex 并行会让其中一个在第 2 页附近静默中断，留下 0 字节 PDF 而日志里一个 `!` 都没有**）。

**默认 `--footnotes footnote`**：`[^n]` 渲染成页底 `\footnote{}`，脚注格式保留在 PDF 里；`--footnotes endnote` 才是尾注。**默认还拦「有定义没引用」的悬空脚注（`exit 2`）**——它们只能退化成文末编号列表，确认要降级才加 `--allow-orphan-notes`。URL 走 `\url{}`（已加载 `xurl`），否则长链接在页底脚注里必撑出 `Overfull \hbox`。

`verify_pdf.py` 查编译 `!` 错误、`Overfull \vbox`/`\hbox`、`includegraphics` 数、书签重复、文本层汉字与连字、**逐条核脚注内容是否进了 PDF 文本层**、**代码块数与首行是否进 PDF**。七条版式约定（`\tag` 编号、同组公式合并 `align*`/`gather*`、公式不另起段落、数学里不写裸 `|`、书签只用 `\pdfbookmark`、锚点不进 `\caption`、**不开 `\XeTeXgenerateactualtext`**）见 reference，动模板前先读。

**不要在正文末尾追加"译者说明""术语对照表""译后记"**，除非用户明确要求。

## 第 7 步：回挂 Zotero（有 PDF 时）

文献多半是从 Zotero 里拖来的，译文 PDF 出完、`verify_pdf.py` 通过之后要挂回原条目——产物散在工作区，过三个月没人知道它对应哪一条。这一步**向外部系统写数据**，所以有独立的状态、退出码和账本。

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md   # 单篇
python scripts/zotero_attach.py --batch . --strict                # 一次多篇
```

走 **Zotero 本地 API**（`127.0.0.1:23119`），不碰 `zotero.sqlite`、不需要 zotero.org 账号：读（锚定、判重）不需授权；写（建附件、传文件）第一次弹窗点 **Always Allow**，key 存 `~/.workbuddy/zotero.json`。锚定按可靠性：`--parent-key` → DOI/arXiv → `source_pdf` 与附件文件名精确匹配 → 英文标题相似度（≥0.85 且唯一）；**中文标题不参与匹配**。状态六种 `attached`/`updated`/`unchanged`/`ambiguous`/`pending`/`error`，退出码 0/1/2/3，**`--strict` 把任何没挂上的都算失败**。写不进去时不要手工复制：脚本在 `_zotero/` 产出 `pending.md`（汇总表）与 `attach.js`（粘进 Zotero「工具 → 开发者 → 运行 JavaScript」一次挂完）。判重用 filename+md5，改稿重出直接重跑即原地覆盖，附件命名 `zh - <原文附件名>.pdf`。详见 [references/zotero.md](references/zotero.md)。
</workflow>

<scripts>
| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `scripts/arxiv_src.py` | 取 arXiv e-print 源码：解包、找主文件、展开 `\input`、收图、出结构清单与脚注清单 | `<id\|url>`、`-o`、`--from`、`--main`、`--md`、`--no-flat`、`--refresh` |
| `scripts/mineru_extract.py` | PDF/图片/Office → Markdown；**没有 arXiv 源码时才用** | `--set-token`、`--token-status`、`--pages`、`--ocr`、`--model` |
| `scripts/footnote_recover.py` | 从 `content_list.json` 恢复 `page_footnote`；`--apply` 把 `[^n]` **锚进正文**、定义落文末（不插节）、迁移旧稿、中文回填、PDF 文字层交叉验证；判不出位置的进 `脚注_待锚.csv`（与政经同一实现） | `-o`、`--source`、`--target`、`--apply`、`--place`、`--anchor-bare`、`--anchor-math`、`--translations`、`--check`、`--pdf`、`--pdf-out`、`--skip-footnote-check` |
| `scripts/mathscan.py` | 内部模块：定位全部公式片段，供其余脚本共用 | 不作为命令调用 |
| `scripts/normalize_math.py` | 统一 `\[…\]`→`$$…$$`、`\(…\)`→`$…$`，跳过代码块与 `\\[2pt]` | `--inplace`、`-o`、`--check` |
| `scripts/math_fidelity.py` | 公式逐条比对：数量、逐字一致、`\tag`、`\label`、`$` 成对 | `--csv`、`--max`、`--near`、`--allow-text-only`、`--strict` |
| `scripts/notation.py` | `extract` 抽符号骨架；`check` 核对表与正文；`prune` 删只含通用记号的行 | `extract -o --keep-common`｜`check --csv --strict`｜`prune --apply` |
| `scripts/fidelity_check.py` | 结构对账：正文块、标题、列表、引用块、浮动对象集合、图片路径、引用原样、定理环境、**代码块（围栏、块数、行数、缩进）**、未译段、术语一致性（含 `keep` 反向检查）；**硬校验**：正文卫生（`<sup>` 残留、简述回填）、**脚注逐条**（定义 + 引用双全、无悬空/孤儿/乱序、无 `## 脚注` 残留）；另报"行首 Algorithm N 但无围栏" | `--glossary`、`--strict`、`--strict-soft`、`--float-reflow`、`--allow-block-drift`、`--skip-footnote-check` |
| `scripts/figures.py` | `audit` 核图注/图号/位置/就近性/引用/文件/alt；`group` 合成并排图块；`relocate` 就近重定位；识别前先屏蔽围栏代码块（代码里的 `\|` 对齐行、`图 3` 注释不会被当表格/图注搬走） | `audit --csv --strict --tol`｜`group --apply`｜`relocate --apply --csv --tol` |
| `scripts/figure_layout.py` | 从 `content_list.json` 的 bbox 算每张图占正文栏宽的比例，产 `图片版式.csv`；可选把同页同排的图合成 md 一行多图（与 `figures.py group` 二选一） | `<extract>`、`--md`、`-o`、`--apply` |
| `scripts/extract_terms.py` | 从原文挖候选术语，标注已收录/新增，`keep_default` 标出默认保留英文的候选 | `--glossary`、`--min-count`、`--top`、`--write-project` |
| `scripts/lookup_term.py` | 按词查项目表与种子表；`dst=@keep` 显示「保留英文原文（不译）」 | `--glossary`、`--exact`、`--max` |
| `scripts/review_queue.py` | 生成审校清单：要你定的、公式差异、符号表、术语不一致、候选术语 | `--manual`、`--init-manual`、`--math`、`--notation`、`--resolved` |
| `scripts/review_apply.py` | 执行人的意见：改术语表与译文、重跑四步校验（结构对账带 `--strict`）、登记已决、重生成清单 | `--decisions`、`--resolved`、`--manifest`、`--math`、`--notation` |
| `scripts/md2tex.py` | 译文 Markdown → XeLaTeX（`--pdf` 顺带编译两遍）：`[^n]` 默认排页底 `\footnote{}`、URL 走 `\url{}`、公式分组对齐、编号右对齐、引文跳转、书签与元信息；内置图片/裸图适配、**围栏块 → `codeblock`、算法 div → 逐行算法块、行内代码 → `\texttt`**、数学竖线保护、超宽表格自适应、图宽按 `--fig-meta` 还原原刊比例、图号按原刊编号、跨进程编译锁 | `--source-pdf`、`--pdf`、`--footnotes`、`--fig-meta`、`--title-en`、`--authors`、`--venue`、`--doi`、`--arxiv`、`--citekey` |
| `scripts/verify_pdf.py` | PDF 验收：编译 `!` 错误、`Overfull`、`includegraphics` 数、书签重复、文本层汉字与连字、**逐条核脚注是否进 PDF**、**代码块数与首行是否进 PDF** | `<PDF>`、`--tex`、`--md`、`--footnotes` |
| `scripts/zotero_attach.py` | 把已验收的译文 PDF 挂回 Zotero 父条目（本地 API，filename+md5 判重，改稿原地覆盖，不碰 sqlite） | `<PDF>`、`--md`、`--batch`、`--strict`、`--parent-key`、`--title`、`--doi`、`--attach-title`、`--prepare-only`、`--dry-run`、`--stage` |
| `scripts/paper_meta.py` | 生成、写入、检查译文顶部的 YAML 元信息 | `--init`、`--inject`、`--check` |

全部只用 Python 标准库，无需安装依赖。唯一外部依赖是 MinerU 的 token（仅从 PDF 提取时需要）。
</scripts>

<glossary_resources>
`references/glossary/` 下三份种子表，六列（`src,dst,alt,kind,status,note`）：`math_core.csv`（130 条：定理标签、收敛模式、正则性、范数、渐近记号、缩写）、`stat_core.csv`（135 条：估计量、渐近理论、假设检验、非参数与高维、因果推断）、`ml_dl_core.csv`（135 条：训练优化、架构与注意力、生成模型、评测指标）。

用法：`status=已定` 直接用；`待裁决` 表示两种译法都通行——**本篇找不到权威依据就不要硬选，改记 `kind=keep`**。`alt` 是备选译法（`kind=keep` 时语义变成"禁止出现的中文写法"）。`kind=name`（Transformer、ImageNet 等专名）在一致性检查里跳过。种子表只覆盖通用词，**每篇的项目表才是权威**；同一个词在不同学科译法不同时（`consistency`、`robust`、`kernel`、`inference`）按上下文分流，不要把两个领域的译法硬统一。
</glossary_resources>

<fidelity_notes>
几条容易做错、且对账脚本抓不到的判断：

**原文错误不许静默修正。** 公式漏下标、符号前后不一致、假设与证明对不上、引用年份与文献表不符——照原样译，然后在报告里写明位置与判断。改了就变成"你的版本"而不是"译作"。

**提取缺陷不算原文。** 上下标压平、`O(n)` 读成 `0(n)`、`\mathcal{L}` 读成 `L`、连字符断词接错——凡与 PDF 目视不符，以 PDF 为准改正并记账。

**"显然"不是可以跳过的地方。** 作者写 `clearly`、`it is easy to see`、`trivially` 时，后面跟的往往正是关键一步。照译，不要因为"看不懂所以略过"。

**否定与量的范围。** `not all` 不是 `none`；`few` 不是 `some`；`at most` 不是 `less than`；`tends to` 不是 `does`。论证常建立在这类量的差别上。

**概率模式是条件的一部分。** `almost surely`、`in expectation`、`with probability at least $1-\delta$`、`in probability` 四者强度不同，不能都译成"大概率成立"。

**渐近记号不可混。** $\mathcal{O}$（上界）、$\Omega$（下界）、$\Theta$（同阶）、$o$（低阶）、$\tilde{\mathcal{O}}$（忽略对数因子）、$O_p$（依概率有界）。不要译成"复杂度"。

**定理编号与引用编号是同一套。** 删一个公式或合并两条定理，后面所有 `(3)`、`by Lemma 2.3` 都会错位；要动就在报告里说清。

**符号表不是"翻译"，是"清点"。** 每个符号都必须能在正文找到同一个串；抄错一个下标，表就从帮助变成误导。

**"保留英文"不是"没译完"，是一种裁定。** 别在通读时顺手把 `keep` 术语改成中文——那会破坏已定好的一致性，而且多半造出一个查不到的词。要改就回项目表改 `dst`，整篇一起改并重跑校验。

**搬动图表最容易丢的是图注和表注。** 它们是独立段落，手工拖拽时常留在原地；`relocate` 会把图块、图注、子图说明、表格、表注作为一个整体搬运，交付前对着 CSV 数一遍"搬了几块、有没有无引用的块"。
</fidelity_notes>

<reference_files>
| 文件 | 何时读 |
|---|---|
| [references/accuracy-rules.md](references/accuracy-rules.md) | 动笔前必读；拿不准某处算不算改写、条件有没有少、代码块怎么处理、语体怎么把握时 |
| [references/notation.md](references/notation.md) | 搭符号表时；原文有 Notation 节、符号多义、表格竖线转义出问题时 |
| [references/figures.md](references/figures.md) | 处理图与实验表格时；多面板图被拆散、图注游离、宽图读不清、要导出 HTML/docx 时 |
| [references/terminology.md](references/terminology.md) | 定译法、判断学科分流、缩写处理、维护术语表时 |
| [references/workflow.md](references/workflow.md) | 长文（>1.5 万词）、断点续译、原文更新、批量多篇时 |
| [references/arxiv-source.md](references/arxiv-source.md) | 论文有 arXiv 版本、要取源码而不是从 PDF 提取时 |
| [references/mineru.md](references/mineru.md) | 没有源码、只能从 PDF 提取时；token 配置、提取质量、脚注分类与交叉验证判据 |
| [references/pdf-latex.md](references/pdf-latex.md) | 用户要 PDF 时；页底脚注模式、版式约定与已知排版坑 |
| [references/review-checklist.md](references/review-checklist.md) | 交付前；人工过一遍时 |
| [references/zotero.md](references/zotero.md) | 文献来自 Zotero、要把译文 PDF 挂回条目时 |
</reference_files>
