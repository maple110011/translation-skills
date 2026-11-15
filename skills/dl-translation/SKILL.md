---
name: dl-translation
description: 把英文的深度学习、机器学习、数学、统计学论文译成中文 Markdown，以准确为第一目标。公式与符号逐字符保真、定理/引理的条件与结论强度不走样、术语全文一致；没有通行中文译名的关键术语与概念保留英文原文、不造词，并在译文开头列「保留英文术语一览」；图、表按正文首次引用就近重定位，不再沿用 PDF 的浮动排版位置。译文开头另附「符号一览」。不做润色、不做本土化，允许翻译腔。输入可为 PDF、已提取的 Markdown、docx；输出正文段落与源文一一对应、引用原样，并对公式做逐条机械比对。Use when translating papers with formulas, theorem-proof structures, algorithm pseudocode and experiment tables (deep learning, machine learning, probability, statistics, optimization, mathematics) into Chinese under strict accuracy constraints, when untranslated key terms must be kept in English, when figures/tables must be moved next to their first citation, when a notation table has to be produced alongside the translation, and when a MinerU extraction step is needed first.
agent_created: true
---

# 深度学习·数学·统计学论文翻译

把一篇英文论文变成一份**能用来做推导、复现代码、复审证明**的中文 Markdown。

这类文本的难点不在英文，在三件事：

1. **公式是不可改写的对象。** 差一个下标、少一个绝对值、`\le` 写成 `<`，命题就不是同一个命题。而这类错误在中文里读起来毫无破绽。
2. **定理的全部信息都在条件与强度里。** "其中 $C$ 只依赖于 $d$"、"以至少 $1-\delta$ 的概率"、"至多相差一个通用常数"——省掉半句，结论就从"有条件成立"变成"无条件成立"。
3. **符号在全文范围复用，而读者会回头查。** 同一个 $C$ 在第 3 页是常数、第 12 页是协方差；$\hat{f}$ 与 $f$ 是两个量。作者默认读者记得住，译文必须替读者记住——这就是开头那张符号表的作用。

另外两条约束来自"译文是 Markdown、不是 PDF"这一事实：**没有通行译名的关键术语保留英文原文**（硬造一个中文词，读者既查不到原文也没法与文献对上）；**图与表移到正文首次引用它们的段落附近**（PDF 为分页/双栏把浮动对象挪远，Markdown 是线性文档，没有这个限制）。

所以本 skill 的顺序是：**先不错，再读得通**。不追"信达雅"，不做文字本土化，不做润色。

<what_this_skill_is_for>
**适用**：期刊/会议论文、arXiv 预印本、技术报告、教材章节、讲义、学位论文的英译中；正文含公式推导、定理—证明结构、算法伪代码、实验表格；译文要给导师、审稿人、项目组或自己长期查阅。

**不适用**：
- 中译英——本 skill 的对账逻辑假定"源为英文、目标为中文"。
- 人文社科、政治经济学、文学文本——那类文本的重点是语气与概念史，与这里"公式优先"的取舍相反。
- 只要摘要或要点、不要全文——直接摘要，不要走这套流程。
- 纯 LaTeX 源码级的重建与编译校验（把作者原始 `.tex` 工程复刻出来、修编译错误）——那是排版工程，不是翻译。本 skill 只做一件事：把**已经定稿的中文 Markdown** 编成一份版式贴近原文的 PDF（`scripts/md2tex.py`，见 [references/pdf-latex.md](references/pdf-latex.md)）。
- 扫描件且无可提取文字层——先 OCR；提取质量不过关时，逐条对账毫无意义。
</what_this_skill_is_for>

<non_negotiable_rules>
六条硬规则。任何一条被违反，译文就不合格，不管读起来多通顺。

**1. 公式逐字符保真。**
公式内容不译、不改写、不"等价变形"、不重排。上下标、撇号、转置记号、范数记号、希腊字母变体、括号大小、间距命令、`\tag` 编号，全部原样。`x^2-1` 不写成 `(x-1)(x+1)`，`\log` 不写成 `\ln`，`\|x\|_2` 不写成 `|x|`。允许改的只有空白与换行。定界符统一（`\[…\]`→`$$…$$`、`\(…\)`→`$…$`）由 `scripts/normalize_math.py` 机械完成，不靠手改。细则见 [references/accuracy-rules.md](references/accuracy-rules.md) 第 1 节。

**2. 定理类陈述的条件与结论强度保真。**
Theorem／Proposition／Lemma／Corollary／Claim／Definition／Assumption／Remark／Conjecture／Proof 各译其名，不得互换（`Proposition` 译成"定理"就是抬高结论等级）。量词、范围、正则性条件、概率模式（a.s.／依概率／依分布／以至少 $1-\delta$ 的概率）、常数依赖关系（"只依赖于 $d$"）、一致性/均匀性，一样不能少、不能弱化。`if` / `only if` / `iff` 三档不得合并。见 [references/accuracy-rules.md](references/accuracy-rules.md) 第 2 节。

**3. 正文结构保真；浮动对象只许搬位置、不许改内容。**
**正文段落**与源文严格一一对应：不合并两段、不拆一段、不省略"重复"的过渡句。`#` 层数与顺序、列表与层级、`>` 引用深度、脚注标记（MinerU 抽出的 `<sup>` 不算内容，见下面脚注条）、代码块、粗斜体，全部原样。括号引用 `(Smith et al., 2020)`、`[12]`、`\cite{}`、参考文献条目整条，逐字符保留、不译。图表章节引用跟着译文编号走（`Figure 3`→图 3，`Section 4.2`→第 4.2 节）。

**浮动对象**（图片、并排图块、图注、子图说明、表格、表注）是唯一允许改变位置的成分：PDF 为分页与双栏把它们挪到离引用段落很远的地方，Markdown 是线性文档，**应当把它们移到正文首次引用它们的段落之后**（见 `<floats_reflow>`）。移动的只有位置，下面这些一个都不许变：**图片路径、`alt`、面板并排关系、图注文字与编号、表格行列与数值、表注、正文段落的内容与顺序**。**图的内部版式只许恢复、不许重排**：原文并排的面板要并排，原文分开的两张图不许合成一张，也不许裁掉半边。位置重定位与内部重排是两件事，别混为一谈。

**4. 术语与符号全文一致；关键术语保留英文原文。**
动笔前定术语（项目术语表），全文照表；同一英文词不得一处一个中文词，也**不得一处保留英文、另一处译成中文**。**没有通行中文译名的关键术语与概念，保留英文原文、逐字符照抄，不造词**（见 `<english_terms>`）；有权威译名的照表译。同一符号不得"统一"成别的字母，也不得把 `\hat{f}` 简写成 `f`。译文开头必须有「符号一览」与「保留英文术语一览」，两表里的符号串／英文串与正文逐字符一致。
**5. 准确优先于通顺，不做润色。**
不合并句子、不调换从句顺序（若改变条件辖域）、不把被动改主动（若施事是有意模糊的）、不删重复、不改逻辑连接词（thus/hence/therefore 各自对应）。允许翻译腔，允许长句不拆。唯一底线：句子要能读通，不能是病句。

**6. 不增不删，不替作者补步骤，不静默修正原文。**
不添加原文没有的解释、背景、过渡句、译者按语。原文的符号前后不一致、假设与证明对不上、编号跳号——照原样译，写进交付报告的"原文疑点"。两个例外：① **提取错误**（上下标压平、`O(n)` 误识为 `0(n)`、MinerU 把上标抽成 `<sup>n</sup>`）：以 PDF 为准改正，并记下改了几处；② 译文开头的 YAML 元信息、符号一览、保留英文术语一览——它们都用 HTML 注释包住，标准渲染不显示，对账脚本会先剥掉，不算正文增写。

**`keep` 术语的中文简述只能写进「保留英文术语一览」的简述列，不得在正文首次出现处补括注或同位语**。哪怕只有一句、哪怕不带原文没有的信息，那也是正文增写。旧版「首次出现可加一句中文简述」的许可已废止：`fidelity_check.py` 会拿简述列去正文反查，`（简述）` 形态一出现就是硬性失败。
</non_negotiable_rules>

<accuracy_first>
这一节写的是"不要做什么"。它与常见的翻译习惯相反，所以要显式说明。

**不做的事**：

- 不为了顺口把两句话合成一句。原文"条件—结论"两句结构，合成一句后条件常退化成插入语，读者会漏掉。
- 不把 `for all $n \ge n_0$`、"for sufficiently large $n$" 这类范围限定挪到句末或省掉。
- 不把 `with high probability` 译成"大概率"——它是概率模式（以 $1-o(1)$ 的概率），不是口语里的"很可能"。
- 不把 `up to a constant` 译成"近似地"，也不省掉"至多相差"。
- 不"统一"看似重复的符号（见规则 4）。
- 不把 `\text{…}` 里的英文说明改成中文后又不检查（要改就全篇改，`math_fidelity.py` 会把这类差异单独标出）。
- 不在正文里加译者注、不加"需要注意的是"、不加一句总结。
- 不把公式里的中文当成"更易懂"——数学模式里除原文已有的 `\text{}` 外不出现中文。
- **不给没有通行译名的关键术语硬造中文词**。"先验数据拟合网络"这类自造词，读者既查不到原文也没法与英文文献对上；保留 `prior-data fitted networks` 更准确。
- **不把图表留在 PDF 的浮动位置上**。原文图与引用段落隔了三页是排版造成的，不是作者的意思；译文要放到引用段落旁。

**可以做的事**：

- 拆长句、补汉语必需的虚词、把英文的名词化表达还原成动词——只要信息量完全等价，而且不改变条件的辖域与指代。
- 保留原文的重复与啰嗦。作者重复同一句限定是刻意的。
- 读起来略生硬。这是可接受的代价，只要不是病句。
</accuracy_first>

<english_terms>
## 关键术语保留英文原文

**默认动作是"不译"，而且这个默认要走得比过去更远。** 前沿论文里大量概念没有通行中文译名：作者自造的方法名、近两年新出的架构与指标、跨领域借来后含义变了的词。硬造一个中文名，等于替读者做了一次不可逆的术语裁定——他既查不到原词，也没法与英文文献、代码、检索结果对上。**拿不准就保留英文，这比"译得漂亮"重要。**

读者的处境决定取舍：他要拿这份译文去读代码、查文献、跟作者对线，不是只读一遍中文。**凡是他在原文、文档、issue 里只会以英文遇到的词，保留英文都比译成中文有用。** 一篇论文保留 10–30 个英文术语是正常密度；只有两三个反倒说明该保留的也被译掉了。

### 判据：哪些保留，哪些照译

| 保留英文原文（`kind=keep`） | 照表译成中文 |
|---|---|
| 论文自造／首次提出的概念、方法、机制、架构名：`prior-data fitted networks`、`in-context learning`、`amortized inference`、`tabular foundation model`、`post-hoc localization` | 种子表里 `status=已定` 的通用术语：`posterior predictive distribution` → 后验预测分布、`prior` → 先验、`KL divergence` → KL 散度 |
| 缩写与专名：`PFN`、`PFNs`、`PPD`、`ICL`、`TabPFN`、`Transformer`、`Adam`（大小写、单复数照原文） | 有权威依据的定名：《数学名词》、全国科学技术名词审定委员会、中文教材里稳定使用的译法 |
| **技术名词但中文译名在领域内不稳、或与英文代码/文档脱节**：`hidden size`、`layer norm`、`prompt`、`fine-tuning`、`attention head`、`probing`、`moment matrix`——读者查代码时只会看到英文 | 普通叙述词、语法功能词、句子里的动词与形容词 |
| 中文有两种以上并行译法、且选任一种都会误导的词（如 `consistency` 在特定语境、`localization` 在本文指的具体机制） | 参考文献条目、引用标记（本来就逐字保留） |
| 种子表标 `待裁决`、本篇又找不到权威依据的；以及"译成中文虽然说得通、但中文文献里几乎没人这么用"的 | 已在中文里稳定落地、且不会与英文原词脱节的基础词（`gradient descent`、`regression`、`probability`） |

**一句话判据**：查项目表与种子表 → 有 `已定` 译法 **且该译名在中文文献里确实通行** 就译；**其余一律默认 `keep`**。判断"通行"时问自己一句：这个中文词丢进知网/谷歌学术，能不能检索到同一批论文？检索不到就是自造，改回 `keep`。

两种情形仍要译：**术语表已定**，以及**中文读者不看英文也能懂、且译名唯一的基础词**。除此之外不要为了行文顺口而临时意译——那是本规则最常见的失守方式。

### 怎么写

1. **逐字符照抄**：大小写、连字符、单复数、缩写、斜体标记，与原文该处完全一致。原文写 `PFNs` 就写 `PFNs`，写 `prior-data fitted networks (PFNs)` 就整串照写，不要替作者统一。
2. **首次出现照抄，不补中文简述。** 原文写 `prior-data fitted networks (PFNs)` 就写 `prior-data fitted networks (PFNs)`，不要接 `（一种在模拟数据上预训练…）`。中文简述**只**属于开头「保留英文术语一览」的简述列，正文一处都不许出现；全文（含首次出现）一律只用英文。句末若中英相接，补一个半角空格即可，不要借机加解释。
3. **不中英混跳**：同一个术语定了 `keep`，全文就都保留英文；不许第 2 页英文、第 12 页冒出一个自造中文名。`alt` 列记下那些"不许出现"的中文写法，脚本会查。
4. **标题与图注里的保留术语同样照抄**：标题其余部分照译，术语不译；不要为了"看起来像中文标题"把 `Prior-Data Fitted Networks` 改成"先验数据拟合网络"。
5. **术语里带公式或代码的**（`$\Pi$-prior` 之类）公式部分按规则 1 不动，英文部分不动。

### 译文开头必须有「保留英文术语一览」

紧跟在「符号一览」之后，同样用 HTML 注释包住——它是本次翻译新增的元信息，标准渲染不显示，`fidelity_check.py`、`math_fidelity.py`、`notation.py` 会先把它剥掉再对账：

```markdown
<!-- kept-terms:start -->
## 保留英文术语一览

| 英文原文 | 中文简述 | 出现范围 |
|---|---|---|
| prior-data fitted networks (PFNs) | 在模拟数据上预训练、推断时固定的网络 | 全文 |
| in-context learning (ICL) | 不更新参数、由上下文提供训练信号 | 全文 |
| TabPFN | 面向表格数据的 PFN 实现 | 第 1.2 节起 |
| amortized inference | 把推断成本摊到一次预训练里 | 全文 |
<!-- kept-terms:end -->
```

「中文简述」列可以留空，但**英文列必须与正文逐字符一致**；简述列只供读者查词，**不得回填进正文**（包括首次出现处的括注与同位语）——`fidelity_check.py` 会拿它去正文反查 `（简述）` 形态。表只收 `kind=keep` 的条目，通常 10–30 行；超过 35 行再回头看是不是把基础词也收进来了（`gradient descent`、`regression` 这类不该收）。

### 项目术语表怎么登记

`_work/<stem>_术语.csv` 六列不变，新增一种取值：

```csv
src,dst,alt,kind,status,note
prior-data fitted networks,@keep,先验数据拟合网络|先验数据拟合网,keep,已定,作者自造概念，中文文献无通行译名
in-context learning,@keep,上下文学习|语境学习,keep,已定,两种中文译法并存且均易与 ICL 的统计含义混淆
posterior predictive distribution,后验预测分布,,term,已定,种子表已定
```

- `dst=@keep` 是机器可读的"不译"标记，`lookup_term.py` 会显示「保留英文原文（不译）」；
- `kind=keep` 让 `fidelity_check.py` / `review_queue.py` 跳过"疑似未译术语"，改为反向检查；
- `alt` 在这里的语义变成**禁止出现的中文写法**（不是备选译法），用 `|` 分隔；脚本见一个报一个；
- `note` 写清为什么保留——半年后回来看这句就够了。

`fidelity_check.py` 对 `keep` 条目查两件事：该英文串在译文正文里**确实出现**（没出现＝漏了或误译），以及 `alt` 里的中文写法**没有出现**（出现＝偷偷译了）。这两条与"术语一致"是同一条规则的两面。

### 与符号一览的分工

符号一览管记号（$\Pi$ → 先验分布），保留英文术语一览管词（`prior` → 译"先验"，但 `prior-data fitted networks` → 保留英文）。**符号一览「含义」列里出现的中文词，仍要与术语表写法一致**；若某个概念已 `keep`，含义列直接写英文串，不要替它造一个中文名。
</english_terms>

<notation_table>
译文开头必须有「符号一览」。这是硬要求，不是可选装饰：读者读到第 5 页要回查 $C$ 是什么，只有这张表能回答。
**位置与格式**：YAML front matter 之后、正文第一节之前，用 HTML 注释包住，任何标题都可以但建议 `## 符号一览`：

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

**四条硬要求**：

1. 每格符号用 `$…$` 包住，否则上下标会掉。
2. 符号串与正文逐字符一致（`\hat{f}` 不是 `f`，`\mathbb{E}` 不是 `E`）。
3. 表格里的竖线要转义：`\|x\|` 或 `\Vert x\Vert`，不要写成 `|x|`（那会被当列分隔符，且含义也变了）。
4. 按**首次出现顺序**排，不按字母序；同一符号多义时分行并注明适用区间。
5. **只收需要查的**。表的价值取决于它有多短：$\mathbb{R}$、$\mathbb{N}$、$\mathbb{E}$、$\mathbb{P}$、$\nabla$、索引 $i,j,k$ 一律不收（但带上下标的算子要收，$\mathbb{E}_{\Pi}$ 与 $\mathbb{E}$ 不是一回事）。一篇论文 12–20 行是常态，超过 25 行先怀疑自己收宽了。同一对象的几种写法合成一行。

**为什么要用注释包住**：符号表是本次翻译新增的内容，原文里没有。`fidelity_check.py`、`math_fidelity.py`、`notation.py` 都靠这两个标记把表剥出去，否则结构对账会报"多了一个标题和 N 行表格"，公式比对会把表里的 `$n$` 当成"多出的公式"。

**收什么、不收什么、怎么和原文 Notation 节相处**，见 [references/notation.md](references/notation.md)。原文已有 Notation 节时：该节原位照译、不删不挪；开头的表是补全版，表里注明与原文该节的关系。
</notation_table>

<figures>
Markdown 的图像语法是行内元素：没有宽度、没有图注、没有面板。而论文的一张图是复合对象（图像 + 图注 + 子图说明 + 正文里的"图 N"引用），抽取器按阅读顺序输出，四样就散开了。译文里最常见的三种坏相：**拆散**（四面板图变四张图竖排摞下来）、**游离**（图注跑到图上方或隔了三段）、**裸图**（图后面没图注，正文引用指向空气）。另有一种不是结构问题但很致命：**宽图被压小**，图里的刻度读不出来。

处理原则有两句，**分别管两件不同的事**：

- **内部版式**：**图是证据，不是装饰。** 只许把被抽取器打散的原文版式**恢复**回去，不许创意排版——不把并排改竖排、不把两张独立图合到一个块里、不裁掉半边。
- **所在位置**：PDF 的跨页浮动位置不是内容，是排版约束；Markdown 里要把图与表移到**正文首次引用它们的段落之后**（见 `<floats_reflow>`）。搬位置不算重排，改内部版式才算。

四条底线：

1. **一个逻辑图 = 一个图块 + 一段紧跟其后的图注。**
2. **图注紧跟图，中间不插正文。**
3. **图号与正文引用必须对得上。**
4. **图块紧跟首次引用它的段落**，读者读完"如图 3 所示"低头就看到图 3。

判断"一个逻辑图"还是"N 个独立图"，看原文图注：**一条图注里带 `(a)(b)(c)` 的是一个逻辑图**（哪怕被抽成了四张图）；**四条独立图注的，是四个图，不许合并**。

多面板图被拆散时，用无边框 HTML 表格恢复并排，并用标记包住：

```markdown
<!-- figure:start -->
<table>
<tr>
  <td><img src="images/fig2a.png" alt="图 2(a) 输入模块" width="48%"></td>
  <td><img src="images/fig2b.png" alt="图 2(b) 编码器" width="48%"></td>
</tr>
</table>
<!-- figure:end -->

**图 2**　所提框架总览。(a) 输入模块；(b) 编码器。
```

四个技术要点，缺一个就会出问题：

- 用 `<table>` 而不是 `<div style="display:flex">`——GitHub 会剥掉 `style`，flex 失效后图又变回竖排；`table` + `width` 属性各家渲染器都保得住。宽度两个面板用 48%、三个 32%、四个 24%。
- **图注留在块外**，仍是普通段落。塞进 `<figcaption>` 会让对账脚本把它连同图一起折叠，段落数就错位了。
- **`<!-- figure:start -->` / `<!-- figure:end -->` 不能省**：`fidelity_check.py` 靠它把整块折成一"处"（否则一张四面板图会被算成"多出四张图"），`figures.py` 靠它识别已处理过的块。
- **alt 必填**，格式"图 N(子图号) 一句描述"。空 alt 会被 audit 点名。
- **源文与译文都整理成并排图块时**（多面板图被拆散、两边按同一版式恢复），`fidelity_check.py` 会把**两侧**都折叠成「一个逻辑图」再对账，不会一侧按面板张数、一侧按图块数而误报数量不一致；`figures.py audit` 另查块内 `<img>` 的路径与 alt。

两块脚本：

```bash
# 核对图注数、图号连续性、图注是否紧跟图、正文引用是否有对应图注、文件是否存在、alt 是否为空
python scripts/figures.py audit 原文.md 译文_zh.md --csv _work/图目录.csv

# 把连续裸图合成为并排图块（先不带 --apply 看它打算合哪几组）
python scripts/figures.py group 译文_zh.md --apply
```

`group` 只合并"连续、中间没有文字"的裸图，有图注隔开的两张图不会被误合。合并后图号不变（仍是一个"图 2"），正文引用不用改；合成完重跑 `fidelity_check.py`。

**子图说明**：原文是文字（`Figure 2: (a) Input. (b) Encoder.`）就照译，保持 `(a)(b)(c)` 结构，不合并成散文；说明烧在位图里的**不补写**（补写就是"增"），在交付报告里注明"子图标注为位图，未转文字"。

**宽图**：`width` 放大位图只会更糊。像素宽度不足约 1200px 的，回 PDF 用 `pdftoppm -r 300` 按图区域重裁。拆成"总图 + 逐面板放大"属于重排，不做。

**表格**：多级表头、合并单元格用 HTML 表格（Markdown 表格不支持 `colspan`/`rowspan`）；数字列右对齐；表注单独成段紧跟表下；跨页被拆的合并回一个。

**Markdown 是工作稿，不是阅读版。** 要精排就导出 HTML 或 docx（`pandoc -s --embed-resources --css fig.css`），别在 Markdown 里堆 `<br>` 和空行——那会破坏结构对账。但"图放在引用段落旁边"是**阅读顺序**问题，不是精细排版，必须在 Markdown 里就做对。完整规范、HTML/CSS 模板、交付前逐条清单见 [references/figures.md](references/figures.md)。
</figures>

<floats_reflow>
## 浮动对象就近重定位

**问题**：PDF 为了不拆段落、不浪费版面，把图、表、图注当作浮动对象放到页顶、页底、甚至下一页，与正文里"如图 3 所示"可能隔好几页。抽取器按阅读顺序输出，这个距离就被原样带进 Markdown；读者要来回翻才能把图和论述配上。**Markdown 没有页、没有栏、没有浮动体**，这个约束不该保留。

**规则**：把每个浮动对象（图片／并排图块＋图注＋子图说明、表格＋表注）整体移到**正文中第一次引用它的那个段落之后**，图注仍紧跟图块、表注仍紧跟表格。

判据与边界：

| 情形 | 处理 |
|---|---|
| 正文有「图 N」／「Figure N」的首次引用 | 图块移到该段**之后**，与引用段之间不插别的正文段落 |
| 一张图被多处引用 | 以**首次**引用为准，后续引用不动 |
| 正文完全没引用（封面图、附录图、无编号图） | 保持原相对位置，在交付报告的"未就近对象"里列出来，不猜位置 |
| 表 N／Table N | 同理，表注跟着表走 |
| 原本就紧挨着引用段（≤ 3 行） | 不动，脚本会判为"原本就近" |
| 图注里带 `(a)(b)(c)` 的多面板图 | 整个并排图块＋一段图注一起搬，不许拆开 |
| YAML front matter 里写了 `Figure 1` | 元信息不是正文；`relocate` 先跳过 front matter 再找锚点，不会把图搬到文件开头 |

**只搬位置，不搬内容**：图片路径、`alt`、`width`、面板并排关系、图注文字与编号、表格行列与数值、表注、正文段落内容与顺序，一个都不改。搬完图号、交叉引用、公式编号都不变，所以正文引用不用改。

**由脚本执行，不要手工拖拽**（手工搬容易把图注落下、把两块图叠在一起）：

```bash
# 先看它打算搬哪几块（默认只报告，不改文件）
python scripts/figures.py relocate <stem>_zh.md --csv _work/图表重定位.csv

# 确认后写回；可重复运行，已在锚点附近的块不会再动
python scripts/figures.py relocate <stem>_zh.md --apply --csv _work/图表重定位.csv

# 之后重跑校验，--float-reflow 让结构对账按"位置无关"核对浮动对象
python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --float-reflow --strict
python scripts/figures.py audit <stem>_原文.md <stem>_zh.md --csv _work/图目录.csv
```

脚本给每个被搬动的块加一对注释：

```markdown
<!-- float:moved fig=3 anchor=L214 -->
<!-- figure:start -->…<!-- figure:end -->

**图 3**　……（图注照译，紧跟图块）
<!-- float:end -->
```

这对标记有三个作用：`relocate` 靠它判幂等，`figures.py audit` 靠它核对就近性，`fidelity_check.py --float-reflow` 靠它把浮动块从块序列里剥离后单独核对。它们不是正文，`math_fidelity.py`、`notation.py` 都不受影响。

**`--float-reflow` 放宽了什么、没放宽什么**：它只让"浮动对象在块序列中的位置"不参与一一对应，改为按**多重集合**核对（图片路径、图注编号、表格行数）。**正文段落的块序列仍须逐块一致**——删一段、合并两段照样报硬性失败。没加这个参数时，脚本若发现差异只来自浮动对象位置，会提示你补上参数；加了参数仍会把正文结构逐块查一遍。
</floats_reflow>


<workflow>
按顺序执行。每步都有产物，下一步读上一步的产物，不要跳步凭记忆往下写。

## 第 0 步：确认源与交付

确定三件事：源文件是什么、交付成什么、放哪里。

- 源优先级：**出版版 PDF > 作者提供的 tex/docx > MinerU 提取的 Markdown**。三者冲突以 PDF 为准，提取结果只是工作草稿。
- 交付默认是 Markdown（含开头的符号一览与 YAML front matter）。要 Word 再用宿主的 docx 转换（或 pandoc），本流程先出 Markdown。
- **PDF 是可选交付，不是自动步骤**：用户没说格式时只出 Markdown。第 0 步顺口问一句「要不要 PDF」比事后补做省事；要 PDF 走第 6 步的「可选：编译 PDF 版」。
- 输出放源文件同目录，命名 `<stem>_zh.md`；中间产物放 `_work/`。

用户没说清就只问一次，不要为格式细节来回确认。

## 第 1 步：取得可译的正文

**已有 Markdown** —— 直接用，先扫一遍提取缺陷：公式是否被拆成图片、`\begin{align}` 是否塌成一行、表格是否塌成纯文本、脚注是否丢失、上下标是否被压平（`x_i^2` 变成 `xi2`）。

**有 arXiv 版本（首选）** —— 直接取作者源码，别从 PDF 抠：

```bash
python scripts/arxiv_src.py 2207.01848 -o ./_work/arxiv
python scripts/arxiv_src.py https://arxiv.org/abs/2112.10510v2 -o ./_work/arxiv
```

产出 `main.flat.tex`（已展开 `\input`、剥掉注释）、`figures/`、`结构清单.md`、`脚注.csv`。真公式、真定理环境、真 `\cite`/`\bibitem` 都在源码里——省下的不是提取时间，是逐条核对公式的时间。

**先确认版本**：一个包里常有好几个可编译主文件（`main.tex`、`main_neurips_*.tex`…），`main.tex` 未必是手上那篇 PDF 的版本。用章节数、附录范围、图表数与 PDF 比对，对不上就 `--main` 指定。arXiv 版常常比会议版多附录、多脚注，**以哪一版为准要问用户**，别默默挑大的那个。详见 [references/arxiv-source.md](references/arxiv-source.md)。

**没有源码，或版本对不上 PDF** —— 用 `scripts/mineru_extract.py`：

```bash
python scripts/mineru_extract.py paper.pdf -o ./_work/extract --model vlm
```

首次运行会引导录入 token 并保存；`--token-status` 可查 token 来源。参数与排障见 [references/mineru.md](references/mineru.md)。

**脚注必须一条不落，但两条路线来源不同。**

**走 tex 路线时**：脚注不在 `content_list.json` 里，`footnote_recover.py` 那条链路走不通。脚本已产出 `_work/脚注.csv`（`page` 为空、`text` 是源码原文），填 `zh` 列后回填译文；译文照常写 `## 脚注` 节，条数必须与 `结构清单.md` 的「脚注明细」相等；`fidelity_check.py` 加 `--skip-footnote-check`，完整性改由**条数相等**保证。tex 里没有页码概念，这一层校验换成了序号对账，见 [references/arxiv-source.md](references/arxiv-source.md) 第三节。

**走 PDF 路线时**——提取完立刻恢复脚注（硬性，动笔之前）：MinerU 的版面识别**认得出**页底脚注（`content_list.json` 里 `type=page_footnote`，与 `content_list_v2.json`、`layout.json` 条数一致），但服务端生成 `full.md` 时按类型白名单输出，**`page_footnote` 被整类过滤**：正文常常只剩一个 `<sup>n</sup>` 引用标记，脚注正文 100% 丢失。脚注里常有条件、假设、复现链接，漏掉等于改条件。

两个 skill 共用同一份 `footnote_recover.py`，一条链走完「恢复 → 两侧补回 → 中文回填 → 交付与 PDF 验收」：

```bash
# 1) 恢复并自动补回原文与译文两侧（--pdf 可选，做文字层交叉验证）
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

# 2) 填 _work/脚注_待译.csv 的 zh 列，把中文回填译文
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check

# 3) 出 PDF 后连文本层一起验
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --check --pdf-out <stem>_zh.pdf
```

`--apply` 把正文 `<sup>n</sup>` 归一成 `[^n]`、在 REFERENCES 之前给**原文与译文同步**插入 `## 脚注` 节、逐条写 `[^n]: 第 N 页脚注 n：…`，写回前留 `.bak_footnotes` 备份且可重复运行。译文侧未填中文时会留 `<!-- 待译 -->`，**`--check` 因此返回 1**，直到回填完成。作者机构／版权注常与正文脚注同号（都叫 1），不占 `[^n]` 编号，作为引用块说明保留英文；`noise`（如 `40<sup>th</sup>`）不补。

**这一步不可少、不可跳过**：`fidelity_check.py --strict` 会硬查 `_work/脚注.csv` 是否存在、译文是否有 `## 脚注` 节，并**逐条核编号、页码、链接与中文是否齐备**。豁免只有两种：纯 Markdown 输入、没有 MinerU 结果包；或走 arXiv 源码路线（脚注基准来自源码的 `\footnote`，没有页码）。两种情况都要显式加 `--skip-footnote-check`，并在交付报告里写明理由与替代判据。分类、交叉验证与对账规范见 [references/mineru.md](references/mineru.md)「页底脚注」一节；本 skill 与 `political-economy-translation` 的脚注流程完全一致。

**有 docx** —— 用 pandoc 或宿主的 docx 转换能力转 Markdown，转换后同样检查公式与表格。

提取完**必须对照 PDF 抽查三页**：段落数、公式、表格、脚注。数学论文的提取错误集中在三处——多行公式被切碎、正体/斜体被抹平、参考文献的年份被并入正文。提取错了再译，等于把错误洗进译文。

## 第 2 步：定术语与符号（动笔之前）

这一步的目的是消灭"边译边定"——术语不一致的唯一根源。

**2.1 抽候选术语**

```bash
python scripts/extract_terms.py 原文.md -o _work/ --glossary references/glossary --min-count 3
```

输出候选表（含频次、已知/新增标记）。它只找候选，不猜译法。

**2.2 查表定译法**

```bash
python scripts/lookup_term.py "excess risk" "consistency" "kernel" --glossary references/glossary/
```

种子表三份：`math_core.csv`（数学）、`stat_core.csv`（统计）、`ml_dl_core.csv`（机器学习/深度学习），共约 400 条，带 `status`（`已定`／`待裁决`）与 `note`。`待裁决` 的条目要你选一个，记进项目表。学科分流规则（同一个词在统计与深度学习里译法不同）见 [references/terminology.md](references/terminology.md) 第 2 节。

**2.3 抽符号**

```bash
python scripts/notation.py extract 原文.md -o _work/符号候选.csv   # 通用记号默认已滤掉
```

按首次出现顺序列出候选符号、频次、上下文。**先抽再读**：通读四十页找符号既慢又漏。补 `meaning` 列，这份 CSV 就是后面写符号表的底稿。

**2.4 项目表定稿后再动笔**

`_work/<stem>_术语.csv`（列：`src,dst,alt,kind,status,note`）是此后每一块的唯一依据。只收本篇真正用到的 20–40 条；通用词（`data`、`model`、`result`）和描述性短语不要进表——它们译法唯一，进表只会稀释注意力。要进表的是**换一种译法读者会理解成另一个概念**的词。

**2.5 逐条判定"译"还是"保留英文"**

`extract_terms.py` 输出的 `keep_default` 列把"种子表里查不到既有译法"的候选标成 `yes`——这些**默认保留英文**。逐条过一遍：

| 表里有 `已定` 译法 | → 照译，`kind=term` |
|---|---|
| 有权威依据（《数学名词》、中文教材稳定用法） | → 定译名，`kind=term`，`note` 写依据 |
| **其余全部**（自造概念、新架构、缩写、多译法并存、拿不准） | → `dst=@keep`、`kind=keep`、`status=已定`，`alt` 填不许出现的中文写法 |

判完把 `kind=keep` 的条目抄成译文开头的「保留英文术语一览」。**这一步不做，后面就会边译边造词**——第 2 页写"上下文学习"、第 12 页写"语境内学习"，谁也查不回去。种子表标 `待裁决` 又找不到依据的，一律 `keep`，不要为了填满表硬选一个中文词。

## 第 3 步：搭符号表骨架，再分块翻译

**3.1 先把两张表写进译文开头**

读完摘要、引言与"问题设定"节，就能把主记号（$n$、$d$、$x_i$、$\theta$、$\mathcal{D}$、$\mathcal{R}$、$\ell$）与本篇的 `kind=keep` 术语定下来。先写「符号一览」与「保留英文术语一览」再翻译，有两个好处：译到后面不必回头补；表的"含义"列反过来约束你的术语选择，也不会在第 5 页临时给 PFN 造一个中文名。

**3.2 分块**

以 `##` 二级标题为界；单块超过约 3000 字（中文）再按段落切。切口不要落在 `$$` 块、`align` 环境或 `cases` 中间。每块开工前读**上一块末尾三段**，保证代词、术语、符号不断裂。

**3.3 逐块落地的规矩**

1. 读一块，数清它有几个段落、几个列表项、几个行间公式、几个表格、几条定理。
2. 译。
3. 立刻用同样的段落数写回文件——不要整篇译完再拼，对不上账时无法定位。

译的时候守住这些：

- **段落一进一出。** 源文一段，译文一段。英文常把一个论点塞进一个长段，中文读者习惯分开——但不能分，只能在段内调节。
- **标题译，`#` 数量不变。** `1. Introduction` 保留编号；标题里的术语照项目表。
- **行间公式整块不动。** 一个字符都不改；公式后紧跟的 `(3)`、`\tag{3}` 原样。
- **行内公式不改行间。** 原文行内的不要提出来单独成行——会破坏段落结构与行文节奏，也会让公式编号错位。
- **定理环境照标签译。** `**Theorem 2.1.**` → `**定理 2.1.**`，编号不变；环境后的斜体说明（`*Proof.*`）保留标记，内容照译。
- **伪代码：结构不动，注释可译。** 步号、`for`/`while`/`if`、缩进、函数名、超参数取值都不动；`Require`/`Ensure` 一篇之内统一译法。
- **代码块整块不动**，包括注释。
- **表格：表头译，数据不动。** 数字、单位、`±`、星号显著性、括号里的标准误原样；表注照译。
- **图片：`alt` 译（写成「图 N + 一句描述」），路径一字不改。** 多面板图被抽散时按 `<figures>` 节的并排图块处理，图注紧跟图块、留在块外。
- **脚注：内容照译，引用标记用 `[^n]`；`<sup>` 是提取产物，不是内容。** 脚注里常有条件（"此处假设 $X$ 与 $Y$ 独立"）与复现链接，漏译等于改条件。第 1 步的 `footnote_recover.py --apply` 已从 `content_list.json` 恢复脚注并**自动**给原文与译文两侧补好 `## 脚注` 节（放在 REFERENCES 之前），条目形如 `[^n]: 第 N 页脚注 n：…`；这里只需把 `_work/脚注_待译.csv` 的 `zh` 列填成中文，再用 `--translations` 回填。页码、编号、链接一字不改。
  ① 正文引用标记统一写 `[^n]`，**不要写 `<sup>n</sup>`**；交付稿与 PDF 里都不许出现字面 `<sup>`（`fidelity_check.py` 硬校验）。
  ② 作者/机构角标、版权与会议声明不占 `[^n]` 编号：它们常与正文脚注同号，脚本会作为引用块说明保留英文；版面误标（如标题里的 `40<sup>th</sup>`）直接忽略。
  ③ `noise` 不补；断词（如 `classifica tion`）、URL 被插入的空格，按第 1 步「以 PDF 为准修正提取缺陷」处理并记账，不要静默改。
  ④ **四层门禁**：`footnote_recover.py --check`（逐条内容级）、`fidelity_check.py --strict`（清单 + 译文节 + 编号/页码/链接/中文）、`md2tex.py`（`[^n]` 默认渲染成页底 `\footnote{}`）、`verify_pdf.py`（逐条核脚注是否进 PDF 文本层）。任何一层不过都别交付。
- **引用块 `>`：层级保留，内容译。**
- **术语照表，符号照抽；`keep` 条目照抄英文。** 译到某个符号时不确定它指什么，回 `_work/符号候选.csv` 与正文第一次定义它的句子核对，不要凭印象；译到 `kind=keep` 的术语时，大小写、单复数、连字符与原文该处完全一致，不要"顺手"译成中文。
- **图片与表格先按原位译完，位置最后统一搬。** 逐块翻译时不要边译边搬图——那会让段落编号与进度记录对不上；第 3.4 步用脚本一次性重定位。
- **不写译者注。** 需要说明的写进交付报告的"原文疑点"，不塞进正文。
- **语体是学术书面语，但以准确为先。** 不口语化（`说白了`／`一大堆`／`别忘了` 一律改掉），也不为了顺口改写逻辑关系。判据见 [references/accuracy-rules.md](references/accuracy-rules.md) 第 7 节。

**3.4 全文译完后，把浮动对象移到引用段落附近**

```bash
python scripts/figures.py relocate <stem>_zh.md            # 先看计划
python scripts/figures.py relocate <stem>_zh.md --apply --csv _work/图表重定位.csv
```

看一眼 CSV：每个图／表从哪一行搬到哪个锚段落，有没有"无正文引用"的块。无引用的块保持原位，写进交付报告；有引用的块搬完应距锚段落 ≤ 3 行。搬完再进第 4 步。

## 第 4 步：机械校验

译完（且跑完 3.4 的重定位）不算完。五个脚本，把机械错误挡在人工校对之前。

```bash
# 1) 公式定界符统一（幂等）
python scripts/normalize_math.py <stem>_zh.md --inplace

# 2) 公式逐条比对：数量、内容、编号、label、$ 是否成对
python scripts/math_fidelity.py <stem>_原文.md <stem>_zh.md --csv _work/公式差异.csv --strict

# 3) 结构对账：正文块、标题、列表、引用块、引用原样、定理环境条数、术语一致性；
#    --float-reflow 让浮动对象按"位置无关"核对，并单独查保留英文术语
python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --float-reflow --strict

# 4) 符号表核对：正文有表里没有、表里有正文没有、格子没包 $
python scripts/notation.py check <stem>_原文.md <stem>_zh.md --csv _work/符号缺漏.csv

# 5) 图的审计：图注数、图号连续性、图注是否紧跟图、是否就近首次引用、
#    正文引用、文件存在、alt
python scripts/figures.py audit <stem>_原文.md <stem>_zh.md --csv _work/图目录.csv
```

**`--float-reflow` 是重定位之后必带的参数**：不带它，搬动过的表格行／图注块会让块序列对账报"结构不一致"；带了它，脚本把双方浮动对象剥离后逐块比对正文，再按多重集合核对图片路径、图注编号与表格行数。它同时检查 `kind=keep` 的术语：英文串在正文出现、`alt` 里禁止的中文写法没有出现。

`figures.py audit` 报"图注数一致、图号无缺号、引用都能对上、全都就近"之后，剩下的只有**宽图会不会被压小**这一项——脚本判断不了，只能看图。

**`math_fidelity.py` 是本流程的核心检查，不是可选项。** 它把原文与译文的每一处公式抽出来，按顺序对齐、逐字比较，差异分四类：

| 类型 | 含义 | 处理 |
|---|---|---|
| 缺失／多出 | 原文有译文没有，或反之 | 必须补/删 |
| 内容不同 | 公式主体被改写 | 必须改回 |
| 微差 | 只差一两个字符（上下标、重音、不等号方向） | 必须逐字核对，这类最危险 |
| 文内文字不同 | 只有 `\text{}` 里的说明文字不同 | 一篇之内统一即可，`--allow-text-only` 放行 |

它还核对 `\tag` 序列、`\label`/`\ref` 集合、`$` 是否成对。**差异清零才算过。**

**同一句里挪动公式位置不算差异。** 中文常把条件前置、把"随 n 增大"挪到句尾，同一个式子因此换了位置；脚本会把双方都落单、内容又完全相同的公式配回来，单独报一句"其中 N 处仅位置调整"。若这个数字很大（十几处），那不是翻译，是重排，回原文看。

**`fidelity_check.py` 的边界**：块级结构能发现"整段没了"，发现不了段内的增删——那由段落长度启发式兜底，而启发式会误报（表格段、公式密集段天生比例异常），每条都要回原文确认。定理环境条数不一致时，回去找是哪一条被改了标签（Proposition 译成定理是最常见的一种）。它也不能判断译文对不对、术语准不准——那只能靠人读。

**口径要分清**：块结构、引用、公式、正文卫生、脚注门禁是真硬校验（`--strict` 返回 1）；疑似未译段、段长异常、术语一致、`notation check` / `figures audit` 是**建议性发现**，只打印不拦，因为误报多。要零容忍时给 `fidelity_check.py` 加 `--strict-soft`（或给 `notation.py` / `figures.py` 加各自的 `--strict`）。`review_apply.py` 回填后重跑的结构对账已带 `--strict`，失败直接影响退出码。

**脚本判不了的事情，人工过一遍**，清单见 [references/review-checklist.md](references/review-checklist.md)：公式里每个符号指的事对不对、定理条件有没有少、数值与表格有没有被"简化"、中文能不能读通。

## 第 5 步：审校清单与回填

有些判断不能替用户做，也不该悄悄做掉：**语义歧义**、**术语多译法**、**原文疑误**、**公式确认**。这一步把它们交出去，并把人的意见收回来。

**翻译时就记，不要等到最后补。** 开始第 3 步之前先建一份人工待校表：

```bash
python scripts/review_queue.py --init-manual _work/<stem>_人工待校.csv
```

遇到下面几类情况随手写一行（列：`位置,类型,原文,译法A,译法B,建议,理由`）：

| 类型 | 什么情况 | 例子 |
|---|---|---|
| `多译法` | 项目表没有，或表里并存两种 | `sharp bound` 最优界／尖锐界 |
| `歧义` | 原文两种读法都成立，中文必须选一个 | `for any $x$` 任意／存在 |
| `学科分流` | 同一个词在两个领域译法不同 | `consistency` 相合性（统计）／一致性（ML） |
| `原文疑误` | 符号前后不一致、假设与证明对不上、编号跳号 | 前文 $n=3$，后文按 $n=4$ 算 |
| `符号冲突` | 同一字母在不同节指不同对象 | $T$ 步数／转置 |

**生成清单：**

```bash
python scripts/review_queue.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --manual _work/<stem>_人工待校.csv \
    --math _work/公式差异.csv --notation _work/符号缺漏.csv \
    --suggest _work/<stem>_候选术语_建议.csv \
    --resolved _work/<stem>_已决定.csv -o _work/<stem>_待校对.md
```

清单分五节，一条一个问题，每条下面留一行「你的意见：」：

1. **要你定的**——语义歧义、多译法、原文疑误、符号冲突，附备选、我的建议、理由。
2. **公式差异**——脚本比对出的每一处不一致，附原文式、译文式、字符级差异、原文位置。
3. **符号一览**——正文有表里没有的、表里有正文没有的、没包 `$` 的。
4. **术语不一致**——术语表定了译法但译文没用上，一行一条，没意见不用回复。
5. **候选术语**——每条带一次出现的上下文与建议译法；`dst` 填 `不收` 表示不值得进表。

**人回完意见，一条命令收口：**

```bash
python scripts/review_apply.py --target <stem>_zh.md --glossary _work/<stem>_术语.csv \
    --decisions _work/<stem>_决定.csv --resolved _work/<stem>_已决定.csv \
    --source <stem>_原文.md --manifest _work/<stem>_待校对.md \
    --manual _work/<stem>_人工待校.csv --suggest _work/<stem>_候选术语_建议.csv \
    --math _work/公式差异.csv --notation _work/符号缺漏.csv
```

决定表是 agent 读人的意见后写的，列 `键,动作,旧,新,说明`：

| 键 | 动作 | 效果 |
|---|---|---|
| `term:<原文>` | `term` | 改术语表译法；`旧` 非空时顺带把译文里的旧写法换掉 |
| `text:<任意>` | `text` | 只替换译文（`旧` → `新`）；改公式也用它，`旧`/`新` 写整段 LaTeX |
| `candidate:<原文>` | `accept` / `drop` | 候选术语收进表或标记不收 |
| `manual:<原文>`、`math:<序号>`、`notation:<符号>` | `keep` | 维持现状，仅登记 |

脚本一条龙做完：改术语表 → 改译文 → 重跑公式归一、公式比对、结构对账 → 已决条目记进 `已决定.csv` → 重生成清单。**任何一条改不动都停下来报出来，不静默跳过。**

**交付时按这个顺序说**：必须你定的（给两种译法和各自后果，不要只说"请确认"）→ 建议确认的（术语表里证据薄的条目）→ 已按约定处理的（一句话带过）。

**清单是空的也要说清空的是哪一层**："机械检查零发现"只等于"结构、公式、引用、术语一致性都对得上"，不等于"译文没有问题"。

## 第 6 步：交付与归档

产出：

| 文件 | 内容 |
|---|---|
| `<stem>_zh.md` | 译文，开头带 YAML front matter、符号一览、保留英文术语一览；**含 `## 脚注` 节**（在 REFERENCES 之前，与原文侧同步）；浮动对象已就近重定位；`normalize_math.py`、`math_fidelity.py`、`fidelity_check.py --float-reflow --strict` 全通过 |
| `_work/<stem>_术语.csv` | 本项目定下的术语、专名与 `kind=keep` 的保留英文条目 |
| `_work/图表重定位.csv` | 每个浮动对象的原行号、锚段落、动作与说明 |
| `_work/符号候选.csv` | 符号抽取结果（含含义列） |
| `_work/公式差异.csv` | 公式比对结果（清零后保留，作为交付证据） |
| `_work/符号缺漏.csv` | 符号表核对结果 |
| `_work/图目录.csv` | 图的审计结果（图注、图号、引用） |
| `_work/<stem>_待校对.md` | 审校清单 |
| `<stem>_校对报告.txt` | 三个校验脚本的原始输出 |
| `_work/脚注.csv`、`_work/脚注_原文.md` | 第 1 步 `footnote_recover.py` 的恢复清单，**交付证据**；缺失即被 `fidelity_check.py --strict` 判为硬性失败 |
| `<stem>.pdf`（可选） | 由译文 Markdown 编译的中文排版 PDF；只在用户要 PDF 时产出，做法见下节 |

### 译文的元信息

```bash
python scripts/paper_meta.py --init 原文.md -o _work/meta.yaml   # 生成草稿
# 补齐 title_zh、authors、venue 等字段，draft 改 false
python scripts/paper_meta.py --inject <stem>_zh.md --meta _work/meta.yaml
python scripts/paper_meta.py --check <stem>_zh.md                # 查漏字段
```

**`title` 常常要手改**：MinerU 的 H1 有一半时候是期刊名或 "Preprint"，不是论文标题。`authors` 也人工填——脚本不猜，猜错比空着麻烦。

**front matter、符号一览、保留英文术语一览都不算"增"。** 规则 3 约束的是正文段落；这三块是文件属性／术语清点，标准渲染不显示，所有对账脚本都会先剥掉它们再比对。但边界要守住：front matter 只放元信息，符号表只放符号与含义，保留英文术语表只放英文串与简述，不许塞内容摘要、译者按语。

**交付时对话里只回复**：译文绝对路径；校验结论（公式多少处逐字一致、正文结构是否通过、定理环境几条一致、符号表缺几条、`keep` 术语几条且是否全部保住、浮动对象重定位几处／几处无引用）；原文中有无疑点或提取缺陷；没做的部分（没有附录、公式是图片无法提取）；**Zotero 挂载状态**（`attached`／`updated`／`unchanged`／`pending（需你点授权）`）。**不复述译文内容。**

### 可选：编译 PDF 版（版式贴着原文）

用户要 PDF 时走这一条，不要临时手搓模板——所有坑都已经写进脚本和 [references/pdf-latex.md](references/pdf-latex.md)。

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex --source-pdf 原文.pdf --pdf
# 元信息缺的用 --title-en --authors --venue --doi --arxiv --citekey 补
```

**脚本已内置以下适配（2026-11-14 起），不要再手搓排版副本**：

- 图片：`<img>` 属性顺序任意（MinerU 常写 `src="…" width="32%" alt="…"`），也认裸 Markdown 图 `![alt](path)` 与块内的 `![](path)`；图注两种写法都认（`**图 N**　…` 与 `图 N. …`）。解析不到图片时不排「只有 caption、没有图」的空 `figure`。
- 表格：Markdown 表格按 `|` 切列时保护 `$…$` 内的 `\|` / `\vert` / `\Vert`；HTML `<table>` 转出的 `tabular` 超页宽时自动缩放；`&#x27;` 这类数字实体自动解码。
- 公式：`\tag` 留在 `\resizebox` 外；`\tag{□}` 这类非数字编号的组整组降一号字，免得末行撑出页宽；`\text{}` 里被抽取器放大的词间空格自动压回一个。
- 编译：`--pdf` 用跨进程锁串行化 xelatex。**两个 xelatex 并行会让其中一个在第 2 页附近静默中断，留下 0 字节 PDF 而日志里一个 `!` 错误都没有**；批量出多篇直接各自调用即可，锁会排队。

七条不能违反的约定（摘要，细则见 reference）：

1. 编号用 `\tag{n}` 右对齐，md 里为兼容预览器退化的 `\qquad (n)` 在出 PDF 时换回来；
2. 同组多行公式合并成 `align*`（能等号对齐）或 `gather*`（含矩阵/超宽行），**不要每行一个 `equation*`**；
3. 公式不另起段落（段首公式会多垫一个 `\baselineskip`，段前空白立刻偏大）；
4. 数学里不写裸 `|`，一律 `\vert` / `\Vert`；
5. 书签只用 `\pdfbookmark`，配 `\addcontentsline` 会让每个标题出现两条；
6. 引文/符号表的锚点不能落进 `\caption`；
7. **不开 `\XeTeXgenerateactualtext`**（每个词一个 `/ActualText`，阅读器按它的宽度算高亮框，结果是"能复制、框选只亮几个字母"），改用 `Ligatures={TeX,NoCommon}` 保证 `ffi` 不被压成一个连字符。

**默认 `--footnotes footnote`**：正文 `[^n]` 渲染成页底 `\footnote{}`，**脚注格式保留在 PDF 里**；要尾注形式用 `--footnotes endnote`，文字集中排在文末 `## 脚注` 节。URL 走 `\url{}`（已加载 `xurl`），否则长链接在页底脚注里必然撑出 `Overfull \hbox`。

验收先跑脚本，有问题返回 1：

```bash
python scripts/verify_pdf.py _work/pdf/paper.pdf --tex _work/pdf/paper.tex \
    --md <stem>_zh.md --footnotes _work/脚注.csv
```

它查编译 `!` 错误、`Overfull \vbox`、`\hbox>1pt`、`includegraphics` 数、书签重复、文本层汉字与连字，并**逐条核 `脚注.csv` 的内容是否进了 PDF 文本层**。剩下的手工项：`pdftotext` 抽页看中文连续与 `ﬀﬁﬂ`、每页 `BT` 二十来个、`PyPDF2` 打印书签、`/Link` 落点、剥离链接后无漏链引文。

**不要**在正文末尾追加"译者说明""术语对照表""译后记"——除非用户明确要求。
## 第 7 步：回挂 Zotero（有 PDF 时）

文献多半是从 Zotero 文献库里拖来的，译文 PDF 出完、`verify_pdf.py` 通过之后必须挂回原条目——产物散在工作区里，过三个月没人知道它对应哪一条。这一步**向外部系统写数据**，所以有独立的状态、退出码和账本，不是"顺手做一下"。

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md   # 单篇
python scripts/zotero_attach.py --batch . --strict                # 一次交付多篇
```

走 **Zotero 本地 API**（`127.0.0.1:23119`），不碰 `zotero.sqlite`，不需要 zotero.org 账号，也不需要 `pyzotero`：

- **读**（锚定、判重）不需要任何授权；
- **写**（建附件、传文件）第一次会弹窗，点 **Always Allow**，key 存 `~/.workbuddy/zotero.json`（换位置用 `--config` 或 `ZOTERO_CONFIG`），以后零弹窗；
- Zotero < 10 没有本地写入能力，脚本自动降到下面说的「一键挂」。

锚定按可靠性从高到低：`--parent-key` → DOI／arXiv（front matter 的 `doi`／`arxiv`）→ front matter 的 `source_pdf` 与库里附件文件名精确匹配 → 英文标题相似度（≥0.85 且唯一）。**中文标题不参与匹配**——库里存的是英文原题，拿译文标题去搜只会命中噪声。

状态六种：`attached`（新建）、`updated`（覆盖旧版）、`unchanged`（已是当前版本）、`ambiguous`（多个候选，用 `--parent-key` 重跑）、`pending`（没锚定或写不了）、`error`（硬错，空壳附件已回滚）。退出码 0／1／2／3 = 全挂上／硬错／有待挂／需人选；**`--strict` 把任何没挂上的都算失败**，交付门禁用这个。

写不进去时（Zotero 没开、版本太低、用户拒绝授权）不要手工复制副本，脚本在 `_zotero/` 下产出两样东西：

- `pending.md`——一次交付一张汇总表，带父条目 key 与标题；
- `attach.js`——整段粘进 Zotero「工具 → 开发者 → 运行 JavaScript」，Run 一次挂完全部已锚定的。

| 产出 | 内容 |
|---|---|
| `_work/zotero_attach.json` | 单篇结果：父条目 key、附件 key、md5、走的哪条线索、状态 |
| `_zotero/attached.csv` | 总账，按 `<stem>` 一行，记当前挂的是哪一版（看 `md5`） |

判重用 **filename + md5**：同名同 md5 跳过，同名不同 md5 原地覆盖那个附件（附件数不变，不会多出第二个"中译"）。改稿重出 PDF 直接重跑，不要手工去 Zotero 里删。

附件按 `zh - <原文附件名>.pdf` 命名，**标题与文件名一致**——title 留空的话 Zotero 里那片就是空白，不会自动回退显示文件名。旧命名 `<stem>_zh.pdf` 的附件会在下次运行时自动清掉。

详见 [references/zotero.md](references/zotero.md)。

</workflow>

<scripts>
| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `scripts/arxiv_src.py` | 取 arXiv e-print 源码：解包、找主文件、展开 `\input`、收图、出结构清单与脚注清单 | `<id|url>`、`-o`、`--from`、`--main`、`--md`、`--no-flat`、`--refresh` |
| `scripts/mineru_extract.py` | PDF/图片/Office → Markdown，token 只需设置一次；**没有 arXiv 源码时才用** | `--set-token`、`--token-status`、`--pages`、`--ocr`、`--model` |
| `scripts/footnote_recover.py` | 从 `content_list.json` 恢复 `page_footnote`；`--apply` 两侧同步补 `## 脚注` 节、中文回填、PDF 文字层交叉验证、`--check` 内容级门禁（与 `political-economy-translation` 同一实现） | `-o`、`--source`、`--target`、`--apply`、`--translations`、`--check`、`--pdf`、`--pdf-out`、`--skip-footnote-check` |
| `scripts/mathscan.py` | 内部模块：定位全部公式片段（行间/行内），供其余脚本共用 | 不作为命令调用 |
| `scripts/normalize_math.py` | 统一 `\[…\]`→`$$…$$`、`\(…\)`→`$…$`，跳过代码块与 `\\[2pt]` | `--inplace`、`-o`、`--check` |
| `scripts/math_fidelity.py` | 公式逐条比对：数量、逐字一致、`\tag`、`\label`、`$` 成对 | `--csv`、`--max`、`--near`、`--allow-text-only`、`--strict` |
| `scripts/notation.py` | `extract` 抽符号生成骨架（默认略去通用记号）；`check` 核对符号表与正文；`prune` 删掉只含通用记号的行 | `extract -o --keep-common`｜`check --csv --strict`｜`prune --apply` |
| `scripts/fidelity_check.py` | 结构对账：正文块、标题、列表、引用块、浮动对象集合、图片路径、引用原样、定理环境、未译段、术语一致性（含 `keep` 反向检查）；**硬校验**：正文卫生（`<sup>` 残留、术语简述回填）、**脚注逐条核对**（清单存在、`## 脚注` 节、编号/页码/链接/中文齐备） | `--glossary`、`--strict`、`--strict-soft`、`--float-reflow`、`--allow-block-drift`、`--skip-footnote-check` |
| `scripts/figures.py` | `audit` 核对图注数/图号/图注位置/就近性/正文引用/文件/alt；`group` 合成并排图块；`relocate` 把浮动对象移到首次引用段落之后 | `audit --csv --strict --tol`｜`group --apply`｜`relocate --apply --csv --tol` |
| `scripts/extract_terms.py` | 从原文挖候选术语，标注已收录/新增，并用 `keep_default` 标出默认保留英文的候选 | `--glossary`、`--min-count`、`--top`、`--write-project` |
| `scripts/lookup_term.py` | 按词查项目术语表与种子表；`dst=@keep` 显示「保留英文原文（不译）」 | `--glossary`、`--exact`、`--max` |
| `scripts/review_queue.py` | 生成审校清单：要你定的、公式差异、符号表、术语不一致、候选术语 | `--manual`、`--init-manual`、`--math`、`--notation`、`--resolved` |
| `scripts/md2tex.py` | 译文 Markdown → XeLaTeX（`--pdf` 顺带编译两遍出 PDF）：`[^n]` 默认排成页底 `\footnote{}`、URL 走 `\url{}`、公式分组对齐、编号右对齐、引文跳转、符号表锚点、书签与元信息；内置图片/裸图适配、数学竖线保护、超宽表格自适应、跨进程编译锁 | `--source-pdf`、`--pdf`、`--footnotes`、`--title-en`、`--authors`、`--venue`、`--doi`、`--arxiv`、`--citekey` |
| `scripts/verify_pdf.py` | PDF 验收：编译 `!` 错误、`Overfull \vbox`/`\hbox`、`includegraphics` 数、书签重复、文本层汉字与连字、**逐条核脚注是否进 PDF 文本层** | `<PDF>`、`--tex`、`--md`、`--footnotes` |
| `scripts/review_apply.py` | 执行人的意见：改术语表与译文、重跑四步校验（结构对账带 `--strict`，失败影响退出码）、登记已决、重生成清单 | `--decisions`、`--resolved`、`--manifest`、`--math`、`--notation` |
| `scripts/zotero_attach.py` | 把已验收的译文 PDF 挂回 Zotero 父条目（本地 API 读写，Zotero 10+ 可自动上传；filename+md5 判重，改稿原地覆盖；不碰 sqlite） | `<PDF>`、`--md`、`--batch`、`--strict`、`--parent-key`、`--title`、`--doi`、`--attach-title`、`--prepare-only`、`--dry-run`、`--stage` |
| `scripts/paper_meta.py` | 生成、写入、检查译文顶部的 YAML 元信息 | `--init`、`--inject`、`--check` |

全部只用 Python 标准库，无需安装依赖。唯一外部依赖是 MinerU 的 token（仅提取 PDF 时需要）。
</scripts>

<glossary_resources>
`references/glossary/` 下三份种子表，六列（`src,dst,alt,kind,status,note`）：

| 文件 | 规模 | 内容 |
|---|---|---|
| `math_core.csv` | 130 条 | 数学：定理环境标签、收敛模式、正则性、范数与算子、渐近记号、缩写（a.e.／a.s.／w.l.o.g.） |
| `stat_core.csv` | 135 条 | 统计：估计量、渐近理论、假设检验、非参数与高维、因果推断常用词 |
| `ml_dl_core.csv` | 135 条 | 机器学习/深度学习：训练与优化、架构与注意力、生成模型、评测与工程指标 |

用法：

- `status=已定` 直接用；`status=待裁决` 表示两种译法都通行——**本篇若找不到权威依据，不要硬选，改记 `kind=keep` 保留英文**。
- `alt` 列是备选译法，`fidelity_check.py` 用它查"同一术语出现两种写法"；**`kind=keep` 的条目里，`alt` 改成"禁止出现的中文写法"**，脚本见一个报一个。
- `note` 列记着为什么这么定，以及易错点（例如 `power` 在假设检验里是"功效"，写成"能力"即错）；`keep` 条目在 `note` 里写清"中文文献无通行译名"。
- `kind=name` 的条目（Transformer、ImageNet 等）在一致性检查里跳过——专名不该被译成中文；`kind=keep` 的条目走独立的反向检查（英文串必须在、中文写法必须不在）。种子表 `ml_dl_core.csv` 里的 `in-context learning` 已标成 `@keep`，可作模板。

**种子表只覆盖通用词，覆盖不了具体论文的自造术语。** 每篇的项目表才是权威；种子表是起点，不是标准答案。同一个词在不同学科译法不同时（`consistency`、`robust`、`kernel`、`inference`），按上下文分流，不要把两个领域的译法硬统一——分流表见 [references/terminology.md](references/terminology.md) 第 2 节。
</glossary_resources>

<fidelity_notes>
几条容易做错、且对账脚本抓不到的判断：

**原文错误不许静默修正。** 公式漏下标、符号前后不一致、假设与证明对不上、引用年份与文献表不符——照原样译，然后在报告里写明位置与判断。改了就变成"你的版本"而不是"译作"。

**提取缺陷不算原文。** MinerU 常把上下标压平、把 `O(n)` 读成 `0(n)`、把 `\mathcal{L}` 读成 `L`、把连字符断词接错。凡与 PDF 目视不符，以 PDF 为准改正，并在报告里记下改了哪几处。

**"显然"不是可以跳过的地方。** 作者写 `clearly`、`it is easy to see`、`trivially` 时，后面跟的往往正是关键一步。照译，不要因为"看不懂所以略过"。

**否定与量的范围。** `not all` 不是 `none`；`few` 不是 `some`；`at most` 不是 `less than`；`tends to` 不是 `does`；`with high probability` 不是"可能"。数学论文的论证常建立在这类量的差别上。

**概率模式是条件的一部分。** `almost surely`（几乎必然）、`in expectation`（在期望意义下）、`with probability at least $1-\delta$`（以至少 $1-\delta$ 的概率）、`in probability`（依概率）——四者强度不同，不能都译成"大概率成立"。

**渐近记号不可混。** $\mathcal{O}$（上界）、$\Omega$（下界）、$\Theta$（同阶）、$o$（低阶）、$\tilde{\mathcal{O}}$（忽略对数因子）、$O_p$（依概率有界）。`big-O` 译"同阶记号"或直接写"$\mathcal{O}$ 记号"，不要译成"复杂度"。

**定理编号与引用编号是同一套。** 删掉一个公式或合并两条定理，后面所有 `(3)`、`by Lemma 2.3` 都会错位。要动编号就在报告里说清楚。

**符号表不是"翻译"，是"清点"。** 表里每个符号都必须能在正文找到同一个串；抄错一个下标，表就从帮助变成误导。`notation.py check` 的"多余"一栏专门抓这类错误。

**"保留英文"也不是"没译完"，是一种裁定。** 别在通读时顺手把 `keep` 术语改成中文——那会把已经定好的一致性破坏掉，而且多半造出一个查不到的词。要改就回项目术语表改 `dst`，把整篇一起改，并重跑 `fidelity_check.py`。

**搬动图表最容易丢的是图注和表注。** 它们是独立段落，手工拖拽时常常留在原地。`figures.py relocate` 会把图块、图注、子图说明、表格、表注作为一个整体搬运，并写进 `_work/图表重定位.csv`；交付前对着这份 CSV 数一遍"搬了几块、有没有无引用的块"。
</fidelity_notes>

<reference_files>
| 文件 | 何时读 |
|---|---|
| [references/accuracy-rules.md](references/accuracy-rules.md) | 动笔前必读；拿不准某处算不算改写、条件有没有少、语体怎么把握时 |
| [references/notation.md](references/notation.md) | 搭符号表时；原文有 Notation 节、符号多义、表格竖线转义出问题时 |
| [references/figures.md](references/figures.md) | 处理图与实验表格时；多面板图被拆散、图注游离、宽图读不清、要导出 HTML/docx 时 |
| [references/terminology.md](references/terminology.md) | 定译法、判断学科分流、缩写处理、维护术语表时 |
| [references/workflow.md](references/workflow.md) | 长文（>1.5 万词）、断点续译、原文更新、批量多篇时 |
| [references/arxiv-source.md](references/arxiv-source.md) | 论文有 arXiv 版本、要取源码而不是从 PDF 提取时；多版本主文件、宏、脚注怎么处理 |
| [references/mineru.md](references/mineru.md) | 没有源码、只能从 PDF 提取时；token 配置、提取质量、脚注分类与交叉验证判据 |
| [references/pdf-latex.md](references/pdf-latex.md) | 用户要 PDF 时；页底脚注模式、验收清单与已知排版坑 |
| [references/review-checklist.md](references/review-checklist.md) | 交付前；人工过一遍时 |
| [references/zotero.md](references/zotero.md) | 文献来自 Zotero、要把译文 PDF 挂回条目时 |
</reference_files>
