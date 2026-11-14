---
name: political-economy-translation
description: 将英文政治经济学文献（马克思主义价值理论、斯拉法/剩余方法、劳动过程理论、金融化、全球价值链、平台劳动等）翻译为中文 Markdown，并做机械对账。输入可为 PDF、已提取的 Markdown、docx；输出段落与源文一一对应、Markdown 结构不变、引用原样、公式统一为 $$…$$ 与 $…$ 的译文。This skill should be used when translating political-economy papers, book chapters, review essays, or lecture notes into Chinese under strict fidelity constraints, when a MinerU extraction step is needed first, and when a batch of accumulated glossary CSVs has to be consolidated before translating.
agent_created: true
version: 2026-11-07.2
---

# 政治经济学文献翻译

把一篇英文政治经济学文献变成可直接投稿或发布的中文 Markdown，并且**能证明**没有漏段、没有多加话、引用没被改、公式格式统一。

这类文本的难点不在英文，在四件事：术语必须前后一致（同一篇文章里 `labour power` 不能一处"劳动力"一处"劳动能力"），人名音译必须统一（`Shaikh` 是"谢赫"还是"沙伊赫"不能随机），公式与引用是硬约束（错一个符号、改一条文献，审稿人立刻发现），以及中文要读起来像中文写的而不是英文的倒影。

<what_this_skill_is_for>
**适用**：期刊论文、书章、书评、会议论文、讲义、工作论文的英译中；正文含大量公式与文献引用；译文要交给编辑、导师或期刊。

**不适用**：
- 中译英 —— 本 skill 的所有对账逻辑都假定"源为英文、目标为中文"。
- 纯数学教材或数学论文 —— 用 `mathtranslations`，它的 LaTeX 重建与编译校验更完整。
- 只要摘要或要点、不要全文 —— 直接摘要，不要走这套流程。
- 原文是扫描件且无可提取文字 —— 先 OCR；提取质量不过关时，对账毫无意义。
- 整本书的翻译与统稿 —— 本 skill 按单篇处理：一篇一个术语表、一篇一次对账。多章之间的术语统一、索引、全书结构不在范围内。书里单独一章当论文译，适用。
</what_this_skill_is_for>

<non_negotiable_rules>
五条硬规则。任何一条被违反，译文就不合格，不管读起来多通顺。

**1. 忠实原文，不增不删。**
段落与源文严格一一对应。不合并两段，不把一段拆成两段，不省略"重复"的过渡句，不添加原文没有的解释、背景、评价。译者想补充的内容一律不进正文。

**2. 保留 Markdown 结构。**
`#` 的层数与顺序、有序/无序列表及其层级、`>` 引用深度、表格行列、图片路径、脚注标记、代码块、`**粗体**` `*斜体*` `~~删除线~~` `` `代码` `` 全部原样保留。只译文字，不动标记。

**3. 在忠实的前提下做到信达雅。**
调整语序、拆长句、补足汉语必需的虚词与量词、把英文的名词化表达还原成动词、把被动改主动，这些都属于"润色"而非"增删"。判断标准：改写后信息量完全等价，且中文读者不需要回看英文就能懂。禁止为了通顺而模糊掉原文的限定词（`only`、`merely`、`tendentially`、`in the long run`）——这些词在政治经济学里是承重的。

**4. 文献引用保持原样，不翻译。**
括号引用 `(Shaikh, 2016, p. 42)`、叙述式 `Marx (1867)`、数字引用 `[12]`、`ibid.`、`op. cit.`、参考文献条目整条、引文中的书名与篇名，全部逐字符保留。边界说明见 [references/translation-rules.md](references/translation-rules.md)：正文叙述里的学者姓名音译、括号内引用原样，这条分界必须守住。

**5. 公式定界符统一。**
行间公式一律 `$$…$$`，行内公式一律 `$…$`。原文的 `\[…\]` 改成 `$$…$$`，`\(…\)` 改成 `$…$`。公式内容本身不译、不改写、不重排；`\text{…}` 内的英文保留。由 `scripts/normalize_math.py` 机械完成，不靠手工。
</non_negotiable_rules>

<workflow>
按顺序执行。每一步都有产物，下一步读上一步的产物，不要跳步凭记忆往下写。

## 第 0 步：确认源与交付

确定三件事：源文件是什么、交付成什么、译文放哪里。

- 源文件优先级：**出版版 PDF > 作者提供的 docx/tex > MinerU 提取的 Markdown**。三者冲突时以 PDF 为准，提取结果只是工作草稿。
- 交付默认是 Markdown；**第 0 步顺口问一句要不要 PDF**（可选分支在第 6 步，`md2tex.py` + `verify_pdf.py`）。公众号排版稿也是可选分支，两条发布线都以同一份 `[^n]` 译稿为源，互不干扰。
- 输出放在源文件同目录，命名 `<原文名>_zh.md`；中间产物放 `_work/`。

用户没说清就只问一次，不要为格式细节来回确认。

## 第 1 步：取得可译的正文

三种情况：

**已有 Markdown** —— 直接用。先扫一眼有没有提取缺陷：公式是否被拆成图片、表格是否塌成纯文本、脚注是否丢失。

**有 PDF 需要提取** —— 用 `scripts/mineru_extract.py`：

```bash
python scripts/mineru_extract.py paper.pdf -o ./_work/extract --model vlm
```

第一次运行会引导录入 token 并保存，之后不用再输；`--token-status` 可查看 token 从哪来。参数取舍、故障排查见 [references/mineru.md](references/mineru.md)。

**有 docx** —— 用 `workbuddy-docx` 或 pandoc 转 Markdown，转换后同样要检查公式与表格。

提取完成后**必须对照 PDF 抽查**：随机翻三页，比对段落数、公式、脚注。提取错了再译，等于把错误洗进译文。

### 脚注恢复：提取后、动笔前的硬门槛

MinerU 的版面识别**认得出**页底脚注（`content_list.json` 里 `type=page_footnote`），但生成 `full.md` 时按类型白名单把它们**整类过滤**：正文常只剩 `<sup>n</sup>` 标记，脚注正文一条也没有。块级对账对此完全免疫——原文与译文一起缺，块数照样对得上。实测一篇 45 页期刊论文 17 条脚注全丢、4 个标记变形，而对账全绿。

两个翻译 skill 现在共用同一套脚本，以 MinerU 提取包为主源，PDF 文字层只作交叉验证：

```bash
# 1) 恢复并自动补回原文与译文两侧（--pdf 可选，做文字层交叉验证）
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

# 2) 填 _work/脚注_待译.csv 的 zh 列（中文脚注译文），再回填
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check

# 3) 出 PDF 后连文本层一起验
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --check --pdf-out <stem>_zh.pdf
```

`--apply` 做三件事：把正文 `<sup>n</sup>` 归一成 `[^n]`、在 REFERENCES 之前给**原文与译文同步**插入 `## 脚注` 节、逐条写 `[^n]: 第 N 页脚注 n：…`；写回前自动留 `.bak_footnotes` 备份，重复运行幂等。译文侧先放英文原文加 `<!-- 待译 -->` 标记，**`--check` 会因此返回 1**，直到填入中文并重跑。作者机构／版权注常与正文脚注同号（都叫 1），不占 `[^n]` 编号，作为引用块说明保留英文；版面噪声（`40<sup>th</sup>`）不补。

**`[^n]` 是唯一交付形态**：公众号版 `build_wechat.py` 认它（内部归一成 `<sup>` 渲染），PDF 版 `md2tex.py` 默认把它排成页底 `\footnote{}`。不许在交付稿里留字面 `<sup>n</sup>`；`fidelity_check.py --strict`、`build_wechat.py` 的 `audit_notes()`、`verify_pdf.py` 三层都会拦。

`--pdf` 的交叉验证只用来发现提取包被污染或跨页续文被截断：**双栏期刊的脚注在栏底不在页底**，`pdftotext -layout` 的缩进特征会失效，未确认不等于提取包有错，详见 `_work/脚注_交叉验证.md`。判据、编号规则与真实案例见 [references/footnotes.md](references/footnotes.md)；旧命令 `scripts/footnotes.py` 保留为兼容入口，不再作为主流程。

无脚注的文献不会被卡住：清单 0 条即 PASS，但仍要翻两页页底确认。纯 Markdown 输入、没有 MinerU 结果包时，`fidelity_check.py` 可显式加 `--skip-footnote-check` 并在交付报告写明理由。

**参考文献先切出去，不进翻译上下文。** 书目整条保持英文原样（规则 4），让模型读它没有任何收益，代价却实在：一篇论文的书目常占 15–20% 的篇幅，一百条英文著录过一遍，总有一条被"顺手"译掉书名、调换姓序，或把破折号改成短横。

```bash
python scripts/split_refs.py paper_原文.md --check          # 只看切点，不写文件
python scripts/split_refs.py paper_原文.md -o _work/         # 切分
```

切分后翻译只读 `_work/paper_原文_正文.md`，**不要打开 `_work/paper_原文_参考文献.md`**。书目区被换成一行标记：

```
<!-- REFS-ORIGINAL lines=74 -->
```

这一行就是原书目的位置，译文里必须原样留着（见第 3 步）。**附录、作者简介、致谢若排在书目之后，不动**——它们留在翻译用稿里照常译，这正是不能"一刀切到文末"的原因。

脚本只在三件事都成立时才切：找到书目标题、切出的区块像书目（四分之一以上的行含四位年份）、拼接能逐行还原原文。任一条不成立就报原因、不写文件——宁可留着书目，也不切错位置。`--check` 先看一眼切点，值这十秒钟。

**没有书目、或判定不切时，跳过这一步**，后面各步直接用原文和 `<stem>_zh.md`，不要为了走流程而造一个空切分。

### 图表跑到很远的地方：按"首次提及"归位

期刊的排版逻辑是先排满正文、再找地方放图表。出版社为了让版面不留白，会把表格挪到两三页之后，把图挪到章末，MinerU 忠实地按**版面位置**提取，于是提取稿里常常出现"这里写 Table 1 summarizes…，表却在三百字开外"的情形。译成中文后段落一长，读者滚动两屏才看到表，已经忘了表说的是什么。

**规则：图表跟着"第一次提到它的那一段"走，就近落位。**

1. **先找提及句，不要找图表块。** 搜 `表 N`／`图 N`／`Table N`／`Figure N`，找出正文里第一次提到它的那段。图表应当落在这段之后（同一节内、紧跟该段），而不是留在提取稿原来的位置。
2. **连同引出句一起搬。** 表前那句"表 1 按各位作者概括了…"属于表的引入语，和表是同一块内容；只搬表、留下引出句，等于让这句话悬空。
3. **跨节搬要连标题一起搬。** 图表的自然归属可能落在下一节（如"表 1 概括本节三种类型"而表被排到了下一节标题之后）。这时把表的标题、表体、引出句一起移到合适位置，**不要留下一个空的节标题**。
4. **一处也不能丢，顺序不能乱。** 搬完重跑 `fidelity_check.py`：表格行数必须不变，块序列必须仍然对得上（对不上说明搬的时候连正文段落一起动了）。

**改了位置，对账基准也要改。** `fidelity_check.py` 比的是块序列，源文件里表在 A 处、译文里表在 B 处，必然报"块级结构不一致"。做法：生成一份**按发布版式重排过的源文基准**（`_work/<stem>_原文_发布口径.md`），在这份副本里把图表挪到与译文相同的位置，然后用它做基准。基准只服务于校验，不改原文文件本身——原文是证据，不能为了"过校验"去动它。

### 人名表缺失时：补进权威层，不要只在正文里音译

取名人名走三层（`references/glossary/pick_name.py`）：`names_override.csv` 学界惯用 → `verified_names.csv` 权威译名 → `glossary_core.csv` → 新华社标准。查不到时脚本退 1，提示按音译规则自定——**这时不要就地音译了事**，那个人名会在下一篇里再被音译成另一个样子。

做法是补进 `verified_names.csv`（`src,dst,form,confidence,basis,alias` 六列）：

```
zuboff s.,祖博夫,surname,high,《监视资本主义时代》中译本,Zuboff, S.|S. Zuboff|zuboff
Shoshana Zuboff,肖莎娜·祖博夫,full,high,《监视资本主义时代》中译本,
```

两条一起写：`surname` 那条管正文里"Zuboff 把这类权力…"的姓氏单用，`full` 那条管首次出现时的"肖莎娜·祖博夫（Shoshana Zuboff）"。`basis` 写清依据（哪个中译本、哪本工具书），三个月后能判断这条能不能信。

如果 `glossary_conflicts.csv` 里这个人名正挂着"待裁决"，顺手把它标成已裁决：

```
zuboff,祖博夫,resolved,2,4,祖博夫×3 | 朱波夫×1｜已定：祖博夫（《监视资本主义时代》中译本）
```

## 第 2 步：锁定术语与专名

在动笔之前把译法定下来，不要边译边决定——这是同一篇文章内部不一致的唯一根源。

1. **先跑提取，不要靠读。** 通读四十页找术语既慢又漏，数词频不会漏：

```bash
python scripts/extract_terms.py paper_原文.md -o _work/ \
    --glossary references/glossary --min-count 3 --write-project _work/paper_术语.csv
```

脚本输出 `_work/paper_原文_候选术语.csv`，字段含 `count`、`score`、`signals`（`quoted`/`italic`/`suffix`/`the_of`）、`status`（`known` 已收录 / `new` 待定），并可直接生成 `dst` 留空的项目表模板。它只找候选，不猜译法。

2. **给 `new` 的条目填 `dst`。** 查已有资源定译法——`references/glossary/empirical_terms.csv`（183 条从你已译文献中反推的实证译法）、`core_terms_draft.csv`（134 条政经核心概念）、`glossary_core.csv`（1170 条常用专名）、`verified_names.csv`（240 条权威译名）。**用脚本查，不要整份读进上下文**：

```bash
python scripts/lookup_term.py "surplus value" "Shaikh" --glossary references/glossary/
```

`empirical_terms.csv` 是唯一有"你自己怎么译"证据的一档：每条都带出现次数与覆盖文献数，译法是从已完成的译稿里反推的，不是模型推荐的。它只收了有分歧风险的词，`worker`、`price`、`data`、`management`、`technology` 这类通用词不在表内——它们译法唯一，进表只会稀释注意力。

查不到的按 [references/terminology.md](references/terminology.md) 的裁决顺序定：本领域通行译法 > 马恩全集/《资本论》既有译名 > 学界近年论文 > 音译规则。

3. **项目表定稿后再动笔。** `_work/<stem>_术语.csv` 是此后每一段翻译的唯一依据。**不要边译边定**——译到第三页时你已经忘了第一页怎么定的，这正是术语不一致的唯一根源。

术语表是**项目级**的：这本书定"剩余价值"，那本书可能定"剩余价值额"，不要跨项目套用。项目表只收本篇真正用到的 20–40 条，不要复制总表。

**若已有以前的译稿**（同一批文献的旧译文），优先从平行语料反推，而不是靠模型重新定译：

```bash
python scripts/mine_terms_from_pairs.py --auto -o _work/pairs --min-count 4
```

它以数字为锚点做句级对齐，输出每条术语的译法与一条中英对照证据句。挖出的是「你当时怎么译的」，比任何推荐都可靠。字符 n-gram 定不住中文边界（`劳动过程理论` 会切出 `程理论`），所以输出是候选＋证据，必须人读一遍再用。

4. **候选表先瘦身再定稿。** 挖出来的名单里七成是通用词汇和共现噪声，直接拿来定译法会淹没真正的术语：

```bash
python scripts/filter_terms.py _work/<stem>_候选术语.csv -o _work/filtered \
    --names references/glossary/verified_names.csv --min-docs 1
```

单篇翻译必须加 `--min-docs 1`：`extract_terms.py` 的候选表只有一篇文献，默认 `--min-docs 3` 会把整张表判成"证据不足"塞进待核区。挖矿表（`mine_terms_from_pairs.py` 的产物，带 `dst` 列）才用默认值——它跨十几篇文献，篇数才有区分度。

输出 `术语表.csv`（主表）、`待核候选.csv`（证据不足）、`剔除清单.csv`（可审计）。判定原则只有一条：**换一种译法会不会改变论证，或会不会让读者误解成另一个概念**。

据此剔除三类：

| 类型 | 例子 | 为什么删 |
|---|---|---|
| 通用词 | `worker`、`price`、`data`、`management`、`technology` | 译法唯一，无分歧空间 |
| 描述性短语 | `process oriented`、`agrarian change`、`problem debate`、`across sector`、`produced goods` | 不是固定术语，逐句看上下文译即可，硬定一个反而僵化 |
| 噪声 | `mathbf v`、`harriss-white`、`economic outcome` | 提取残片或日常词拼成 |

保留的是 `agent`（主体／代理人）、`tension`（张力／紧张）、`realization`（实现／兑现）、`problematic`（问题式／有问题）这一类——换种写法读者会理解成另一个概念。

**描述性短语不要硬译。** 挖矿脚本会给每个候选配一个译法，但 `process oriented → 流程导` 这种是算法截断的产物，不是译法。表里出现一个不通的条目，比表里缺一条危害大：下次翻译会照着它抄。

## 第 3 步：通读全文，逐段输出

**上下文和输出是两件事，别捆在一起切。** 一篇文章全文放进窗口毫无压力——一万五千词的论文约两万 tokens，在 1M 窗口里占 2%。真正有限的是"一次能写多长"。旧做法把两者一起切，切出来的每一块模型都看不见全文：一致性问题出在这里，不在块大块小。

所以：

- **原文整篇读入，不切。** 只有真的超出窗口才切——那通常意味着这不是一篇论文，按 [references/workflow.md](references/workflow.md) 的断点续译处理。
- **输出按段推进**，一段 2000–4000 汉字，对应源文约 7000–14000 字符（1100–2200 英文词）。
- **段界落在 `##` 或自然段落处**，不在句子中间停。
- **每段写完立刻追加落盘。** 落盘不是为了省上下文，是为了出错能定位：整篇写完才发现第 40 段丢了，得通读全文去找；逐段落盘，对账脚本直接指到段。

模型始终看着全文，"每段重读上一段末三段"这类补丁就不需要了——代词、术语、语气它自己接得住。真正需要外部约束的只有一样：**行文风格**。

### 全篇风格锚：一次定，段段照

上下文解决不了风格漂移。模型看得见前文，但它每一段都在重新做**词的选择**，而选择本身没有记忆：第 2 段写"本文主张"，第 9 段变成"文章认为"；同一个 `argue`，一处"论证"一处"辩称"；前面句子层层嵌套，后面突然短句连发。

所以风格要落到文件上，跟术语表一样分两层：

| 层 | 文件 | 内容 |
|---|---|---|
| 总表 | `references/style/default.md` | 跨篇稳定的偏好，已按你 28 篇译稿的实测填好 |
| 项目表 | `_work/<stem>_风格.md` | 复制总表，改本篇差异项，加本篇特有说法与样板段 |

```bash
cp references/style/default.md _work/<stem>_风格.md
```

每段翻译时带**项目表 + 样板段**这两样。**样板段比形容词管用**：第一段译完后挑你认可的两三百字回填进去，之后每段都带着它。写"学术、克制、准确"对模型没有约束力，一段真实译文有——风格靠模仿，不靠描述。

约定一旦定下就别中途改。要改，是回头统一改已译部分，不是在后面几段悄悄漂过去。细则、判据、什么时候该并回总表，见 [references/style-sheet.md](references/style-sheet.md)。

每一段按这个顺序走：

1. 读这一段对应的原文，数清它有几个段落、几个列表项、几个公式块、几个表格。
2. 译。
3. 立刻用同样的段落数追加进译文文件——不要攒着最后一次性写，那样对不上账时无法定位到段。

译的时候守住这几条：

- **段落一进一出。** 源文一段，译文一段，中间不合并。英文常把两个论点塞进一个长段里，中文读者更习惯分开——但不能分，只能在段内调节节奏；段内怎么断、哪几句并作一句，见下一条。
- **标题译，`#` 数量不变。** 标题里的术语按项目术语表；`1. Introduction` 保留编号。
- **列表项一进一出。** 源文三个 `-`，译文必须三个 `-`；嵌套层级不变。
- **表格：表头译，数据不动。** 数字、单位、显著性星号、括号里的标准误一律原样；表注照译。
- **图片：`alt` 译，路径一字不改。** 路径改了图就断了。
- **脚注：标记不动，内容照译。** 正文引用标记统一写 `[^n]`（不许写 `<sup>n</sup>`），脚注文字写在 REFERENCES 之前的 `## 脚注` 节里，条目形如 `[^n]: 第 N 页脚注 n：…`；原文侧英文、译文侧中文，两侧同步增删才能保持块级对账。第 1 步的 `footnote_recover.py --apply` 已把结构与英文原文补好，这里只需把 `脚注_待译.csv` 的 `zh` 列填成中文再回填。页码、编号、链接一字不改。
- **引用块 `>`：层级保留，内容译。** 编者按、长引文都用这个。
- **代码块与公式块：整块不动。** 一个字符都不改。
- **参考文献标记：一行不动。** `<!-- REFS-ORIGINAL … -->` 原样留在原位置——不译、不删、不挪、不缩进、不在它前后添加空行。它不是正文，是"此处原样嵌入书目"的指令，交付前由脚本替换。改写它，`fidelity_check.py` 会报结构块数不一致，`split_refs.py --restore` 也会直接拒绝拼回。
- **不写译者注。** 需要解释的地方写进交付报告的"原文疑点"一节，不塞进正文——那属于增，违反规则 1。
- **语体是学术书面语，不是随笔。** 读者是研究者，载体是论文。词汇、句式、语气三层都要守住：`东西`／`玩意儿`／`大把`／`满手`、`要……的东西不少`／`还得说几句`、调侃和亲切的插入语（`别忘了`／`说白了`／`所幸`），一律改掉。判断标准：这句话能不能出现在《资本论》中译本的注释里。宁可略生硬，不可口语化；但生硬不等于病句，照搬英文的框架（`是……加以……的`）仍要改。译完跑一次 `python scripts/style_check.py <stem>_zh.md --style _work/<stem>_风格.md`：内置词表查通用口语腔，`--style` 再并上本篇自己定的禁用词与句式，按句列出可疑处，逐句定去留。判据与对照表见 [references/translation-rules.md](references/translation-rules.md) 规则 3「语体」一节。
- **句读、语序、主从由你定。** 句子在哪儿断、哪几句并作一句、哪个分句提到前面，看中文的论述单位，不看英文的句号——长句该拆，散句该合，两者都不算增删。同一段切三次可能三次都通，选读起来最顺的那次。**只有一处不能动**：段落、列表、表格、公式的块结构，那是第 4 步对账的依据。判据与正反例见 [references/translation-rules.md](references/translation-rules.md) 规则 1、规则 3。

## 第 4 步：机械校验

译完不算完。跑三个脚本，把机械性错误挡在人工校对之前。**对账用切分后的那一对文件**（`_work/<stem>_正文.md` 对 `_work/<stem>_正文_zh.md`），书目区不在账内——它由脚本原样拼回，本来就不该出现在译文里。拿含书目的原文去对，会对出一串假差异。没做切分的稿子，照旧用原文对 `<stem>_zh.md`。

```bash
# 1) 公式定界符统一（可重复运行，幂等）
python scripts/normalize_math.py <stem>_zh.md --inplace

# 2) 引号统一为中文引号（幂等；参考文献与公式不动）
python scripts/zh_quotes.py <stem>_zh.md --inplace

# 3) 与原文对账
python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --strict
```

**中文引号是体例，不是可选项。** 英文原文的 `"..."`、`'...'` 一律转成 `“...”`、`‘...’`；嵌套沿用 `“……‘……’……”`。`zh_quotes.py` 只动正文：YAML front matter、参考文献、公式、代码、图片语法都跳过，英文所有格撇号（`Dymski's`）也不碰。引号数不成对时它会提示——那说明原文或译文有一处落单，要回去找。

`fidelity_check.py` 检查：块级结构是否一一对应、标题层级、列表项、引用块、表格行、图片路径、引用是否原样保留、`\[` `\(` 是否清零、是否有整段未译、段落长度是否异常（用于捕捉段内漏译）、术语是否混用异译。硬性失败必须修到清零；`--strict` 会让它返回非零退出码。

**引文是不是马恩的原话，交给 `_marx_ref` 对一遍。** 文本里有马克思、恩格斯的直接引语时，跑一次匹配，把英文引文对到《马克思恩格斯文集》的中文译文——既省得另译一遍，也避免与刊物"引文照抄文集"的要求相抵：

```bash
python scripts/marx_quotes.py --source <stem>_原文.md --target <stem>_zh.md \
    --marxref "$MARX_REF" -o _work/<stem>_马恩引文.csv
```

它同时抓两种形态：带引号的串，以及**没有引号、末尾只缀着 `(1978: 357)` 的裸段落**——后者是长引文在提取稿里的常态，只认引号会漏掉最要紧的几条。匹配前先按引用年份把范围收到对应那一卷（`--anchor vol`，默认），这一步最能纠错：全库搜时 `(1978: 351)` 会配到第 5 卷第 24 章，收到第 6 卷才落在本卷。结果分高／中／低三档，判据不是分数高低（作者引 Penguin 版，文集底本是 MECW，对得上也常只得 0.2—0.5），而是**卷次是否与引用年份相符、同篇引文的章是否集中、前两名候选分不分得开、引文里的数字对不对得上**。低档进待校对清单，见 [references/marx-ref.md](references/marx-ref.md)。

**只产 CSV，不要产双语对照 md，也不要用 `_marx_ref` 的 annotate 回填。** 那个模式会把英文原文和中文并列塞进正文；本流程的成果是纯中文译文，引文比对只在待校对清单里发生。

**引擎给的译文要裁。** 引擎为了对上长句，会把命中的句子与前后句拼起来打分，返回的「文集译文」因此常比引文本身长得多：引文只是一个从句，返回的却是两三句。CSV 的 `裁句提示` 会按字数比标出这种情形（英译中正常在 1.6—2.0 倍，超过 2.6 倍就是带了引文之外的上下文），但**哪几句才算引文覆盖的范围，脚本判不了**——要读英文引文和中文候选，判断「这句是不是在讲同一件事」。这一步由 agent 逐条裁定，写进采用表：

```bash
# 采用表：序号,引用串,采用,原文句,说明
python scripts/marx_adopt.py --quotes _work/<stem>_马恩引文.csv \
    --adopt _work/<stem>_引文采用.csv --target <stem>_zh.md \
    -o _work/<stem>_引文决定.csv
```

**引文默认直接用文集译文**，不再另译——这是刊物的要求，也省得同一段话出现两种译法。采用表里的 `采用` 是裁好的那几句，`原文句` 是译文里要被换掉的整句（留空则用 CSV 的「本译文段」，但那常常只是引号内的一小截，定位不准），`说明` 记为什么这么裁：引文是半句、文集此处中文残缺、文集根本没有这句。`marx_adopt.py` 只把采用表转成 `review_apply.py` 的决定表，改译文与重跑校验都交给它，校验链只有一条。

三种情况不要硬套文集：**文集里没有这一句**（多半是作者的转述，加了引号但非逐字，按本义译即可）、**文集这一句的中文本身残缺**（库里确有断在分号上的段，后半句据英文补译并注明）、**文集译文在这个语境里读不通**。这三种都写进 `说明`，清单里会标出来。

### 承重细节：数字交给脚本，其余只能读

结构对账管得住"有没有少"，管不住"意思有没有偏"。整篇读入不等于每个细节都被准确处理，长文翻译错得最多的不是整段，是**只差一个词、整句判断就反了**的地方。

**数值可以机械查**——错就是错，不受语言习惯干扰：

```bash
python scripts/semantic_audit.py <stem>_正文.md <stem>_正文_zh.md -o _work/<stem>_数字核对.md
```

它按段配对（用与对账相同的块定义），只比数字：年份、小数、百分比、千分位、页码区间。`10,000`／`10 000`／`10000`、`5 per cent`／`5%` 归一化后算同一个值，不因中文排版误报。数字没错时它就安静地报 0 处，这是正确结果，不是失灵。

**其余三类不要交给脚本。** 试过：让它查否定、限定、逻辑，Saros2014 报 11 处，逐条核完 6–8 处是误报——`thus far`（至此）被当成因果 `thus`、"自从"义的 `since` 被当成因果、`must` 译成"还须"被判漏译、`10,000` 写成 `10000` 被判丢失。补词表修不掉前两条：同一个词在不同位置承担不同语义功能，字符串匹配看不见。

所以语义偏离只能读，方法见 [references/semantic-review.md](references/semantic-review.md)：逐段读、只给"通过／偏离／疑点"三种结论、偏离必须贴原文与译文两段。该查的十二类（量的范围、否定辖域、情态强度、比较方向、时态、条件范围、连接词的具体义、修饰语归属、指代、术语在句中的意思、引文逐字、段间论证）在那份文档里。

**更好的做法是换个执行者。** 当前环境支持开独立上下文的子任务时，把原文与译文交给它，不要给它翻译过程、术语决策、刚才为什么这么译——它看不到这些，正是要的。让它先读 `references/semantic-review.md`，按三态结论与举证格式执行，逐段列出段号（方便看它有没有偷懒），结果写成文件，不接受"整体准确"这种结论。

实测：Passarella2015 §20–40（21 段）交给独立子任务，报 0 偏离、1 疑点，疑点是真的——`given the organic composition of capital` 译作"就资本有机构成而言"，丢了"在 q 既定时"这层限定，而 q 在式 (5)/(5bis) 里是参数。这种问题没有词表能查出来。

**子任务不等于换了个脑子**：底层还是同一个模型，系统性理解偏差照样在。它消除的是"我刚译完所以我觉得对"这条路径，不是模型的能力边界，所以仍要搭配抽样回译。

**知道它能查什么、不能查什么。** 块级结构能发现"整段没了"或"多出一段"，但发现不了段内的增删——那由段落长度启发式兜底，而启发式会误报（表格段、人名罗列段天生比例异常），每一条都要回原文确认。它也不能判断译文对不对、术语准不准、中文通不通——这三件事只能靠人读。**脚本通过不等于译文合格**，它只是把机械错误挡在人工校对之前。

**口径要分清**：块结构、引用、公式残留、正文卫生、脚注门禁是真硬校验（`--strict` 返回 1）；疑似未译段、段长异常、术语一致、语体这些是**建议性发现**，只打印不拦，因为误报多。要零容忍时加 `--strict-soft` 把它们一并升级为硬性失败。`review_apply.py` 回填后重跑的结构对账已带 `--strict`，失败直接影响退出码。

脚本判不了的事情，人工过一遍（详细版见 [references/review-checklist.md](references/review-checklist.md)）：

- 每一段都译了吗，有没有"看着像重复就跳过"的段落
- 限定词保住了吗（`only`、`merely`、`tendentially`、`in the long run`、`as such`）
- 术语与第 2 步定的表一致吗，包括同一术语的复数、所有格、缩写形式
- 中文读起来像中文吗，有没有成串的"的"、连续的"被"、翻译腔的名词堆叠
- 数字、年份、页码、引文页码逐个核对过吗
- 原文含糊或疑似错误的地方记进报告了吗（**不要替作者圆场**）

## 第 5 步：审校清单与回填

有三类判断不能替用户做，也不该悄悄做掉：**语义歧义**、**学派立场**、**原文疑误**。这一步把它们交出去，并且把人写的意见收回来的活也一并自动化。

**翻译时就记，不要等到最后补。** 开始翻第 3 步之前先建一份人工待校表：

```bash
python scripts/review_queue.py --init-manual _work/<stem>_人工待校.csv
```

遇到下面几类情况随手写一行（列：`位置,类型,原文,译法A,译法B,建议,理由`）：

| 类型 | 什么情况 | 例子 |
|---|---|---|
| `多译法` | 项目表里没有，或表里并存两种 | `surplus approach` 剩余方法／剩余进路 |
| `歧义` | 原文两种读法都成立，中文必须选一个 | `determination` 决定／规定 |
| `学派立场` | 选词即表态 | `regulation` 调节（调节学派）／规制 |
| `原文疑误` | 指代不明、公式符号前后不一、疑似笔误 | 前文说 $n=3$，后文按 $n=4$ 算 |
| `文风` | 语体统一问题（引文是否译、是否保留原文） | 直接引语全部译成中文，还是留英文 |

**生成清单：**

```bash
python scripts/review_queue.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --manual _work/<stem>_人工待校.csv \
    --suggest _work/<stem>_候选术语_建议.csv \
    --resolved _work/<stem>_已决定.csv \
    --marx _work/<stem>_马恩引文.csv --marx-note _work/<stem>_引文备注.csv \
    --marx-adopt _work/<stem>_引文采用.csv -o _work/<stem>_待校对.md
```

清单是给人读的，不是给机器读的：一条一个问题，每条下面留一行「你的意见：」，写「按建议」「用 A」就够，不必写完整句子。分五节：

1. **要你定的**——上面那张表里的条目，一条一块，附备选、我的建议、理由。
2. **我可以直接改的**——术语表定了译法但译文没用上。列成一行一条，没意见不用回复。
3. **只在括号引用里出现、不需要处理**——一句话交代数量即可。按规则 4 这些词本来就保持英文，**不要把它们混进第 2 节**，那是纯噪声，会让人以为出了问题。
4. **候选术语**——每条必须带两样东西：一次出现的**上下文**，和**建议译法**。只给词不给译法，人不知道你在问什么。建议写成 `src,dst,note` 三列喂给 `--suggest`；`dst` 填 `不收` 表示不值得进表，`note` 写理由（"句子片段"／"通用搭配"／"与 X 配套"）。
5. **马恩引文**——`5.1` 把能对上的几条并排给"文集原话／现译"，让人一次定"要不要改用文集译法"；`5.2` 只摊开「低/无匹配」，每条附原文、我们的译文、引擎给的位置与备选、文集译文、判定理由。**跑完匹配要逐条核查 5.2**，把结论写进 `_work/<stem>_引文备注.csv`（`引用串,备注`），用 `--marx-note` 传进去——核查常常发现"库里根本没有这一句"，那多半是作者转述、加了引号但非逐字，按本义译即可。

**人回完意见，一条命令收口：**

```bash
python scripts/review_apply.py --target <stem>_zh.md --glossary _work/<stem>_术语.csv     --decisions _work/<stem>_决定.csv --resolved _work/<stem>_已决定.csv     --source <stem>_原文.md --manifest _work/<stem>_待校对.md     --manual _work/<stem>_人工待校.csv --suggest _work/<stem>_候选术语_建议.csv
```

决定表是 agent 读人的意见后写的，列 `键,动作,旧,新,说明`：

| 键 | 动作 | 效果 |
|---|---|---|
| `term:<原文>` | `term` | 改术语表译法；`旧` 非空时顺带把译文里的旧写法换掉 |
| `text:<任意>` | `text` | 只替换译文（`旧` → `新`），用于改句子 |
| `candidate:<原文>` | `accept` / `drop` | 候选术语收进表或标记不收 |
| `manual:<原文>` | `keep` | 维持现状，仅登记 |

脚本一条龙做完：改术语表 → 改译文 → 重跑公式归一与结构对账 → 已决条目记进 `已决定.csv` → 重生成清单（已决的不再出现）。**任何一条改不动都停下来报出来，不静默跳过。** 人只留意见，合并这一步不该由人做。

**交付时按这个顺序说：**

1. 必须你定的：语义歧义处、学派立场处、原文疑误处。附两种译法和各自后果，不要只说"请确认"。
2. 建议你确认的：新术语候选里我建议收的那几条，以及术语表里证据薄的条目。
3. 已按约定处理的：术语不一致若只有个别几处，说明改成了什么，不用逐条列。

**如果清单是空的，也要说清楚空的是哪一层**——"机械检查零发现"不等于"译文没有问题"，只等于"结构、引用、公式、术语一致性都对得上"。语义判断那部分仍然只做过一遍，是译者自己过的。

## 第 6 步：交付与归档

**先把书目拼回去。** 译文里那行标记只是占位，交付前必须换成原文著录：

```bash
python scripts/split_refs.py --restore _work/<stem>_正文_zh.md -o <stem>_zh.md
```

拼回时会核对参考文献文件与切分时是不是同一份（sha256 对不上就停），并检查标记在不在、是否只剩一处。标记丢了，它报出"应在原第几行插入"，手工补回再跑——不要凭记忆把书目贴到别处。标题想用中文加 `--heading 参考文献`：标题属于结构，可以译；条目是原文，一字不动。

产出这几样东西（最后一行为归档动作，不属于本步）：

| 文件 | 内容 |
|---|---|
| `<stem>_zh.md` | 译文（书目已原样拼回），顶部带 YAML front matter，`normalize_math.py` 与 `fidelity_check.py` 都通过 |
| `_work/<stem>_切分.json` | 切点、书目行数与 sha256，`--restore` 靠它核对 |
| `_work/<stem>_风格.md` | 全篇语体约定与样板段，续译与改稿的基准 |
| `_work/<stem>_术语.csv` | 本项目定下的术语与专名 |
| `_work/<stem>_引文采用.csv` | 马恩引文的裁定结果：哪几句用文集译文、为什么（有引文时才有） |
| `_work/<stem>_待校对.md` | 审校清单：机械发现 + 人工判断项（含马恩引文核对） |
| `_work/<stem>_数字核对.md` | 数值比对结果（脚本产出，通常 0 处） |
| `_work/脚注.csv` / `脚注_原文.md` / `脚注_待译.csv` | 第 1 步从 `content_list.json` 恢复的脚注清单、英文原文与中文待译表；证明脚注没有被整批丢掉 |
| `_work/脚注_交叉验证.md` | PDF 文字层交叉验证结果（给 `--pdf` 时产出） |
| `<stem>_校对报告.txt` | `fidelity_check.py` 的原始输出 |
| `_work/<stem>_原文_发布口径.md` | 按发布版式重排过的源文基准（图表归位、元信息剔除后），供校验用；**不改原文文件** |
| `<stem>_zh.pdf` / `_work/pdf/paper.tex` | 可选 PDF 版（用户要时产出）：页底真脚注，编译后必须跑 `verify_pdf.py` |
| `<stem>_公众号版.html` / `.md` | 可直接粘贴进公众号的排版稿（用户要公众号版时才出） |
| 归档后的总表 | 下一节的合并结果 |

### 译文顶部的元信息

译文开头写一段 YAML front matter，记录这篇文献的身份与翻译过程：

```bash
# 1) 从原文生成草稿（标题、年份、DOI、关键词能自动取，其余留空）
python scripts/paper_meta.py --init paper_原文.md -o _work/meta.yaml

# 2) 补齐 title_zh、authors、journal、school 等字段，把 draft 改成 false
# 3) 写进译文（幂等，重复运行只替换 front matter）
python scripts/paper_meta.py --inject <stem>_zh.md --meta _work/meta.yaml

# 4) 检查有没有漏字段
python scripts/paper_meta.py --check <stem>_zh.md
```

字段分四组，各有各的用途：

| 组 | 字段 | 之后能用来做什么 |
|---|---|---|
| 身份 | `title`、`title_zh`、`authors`、`year`、`journal`、`volume/issue/pages`、`doi`、`type`、`school` | 建文献库、生成引用、按学派筛选 |
| 溯源 | `source_file`、`source_sha256`、`extraction` | 判断原文有没有换过版本；查找提取缺陷 |
| 过程 | `translated_at`、`translator`、`glossary`、`terms_used`、`review_open` | 知道这份译文处于什么状态、用了哪份术语表 |
| 质量 | `fidelity`（块数、段落数、引用数、公式数、`status`） | 按"真正通过校验"筛语料，而不是靠文件名 |

**`title` 常常要手改**：MinerU 的 H1 有一半时候是期刊名或文章类型（"Research Article"），不是论文标题。`authors` 也要人工填——脚本不去猜，猜错了比空着更麻烦。

**front matter 不算增删。** 规则 1 约束的是正文：段落与源文一一对应，不添加原文没有的内容。元信息是文件属性，标准 Markdown 渲染时不显示，所有对账脚本都会先剥掉它再比对（`fidelity_check.py`、`normalize_math.py`、`review_queue.py` 都实现了 `strip_frontmatter`）。但边界要守住：**front matter 只放元信息**，不许塞译者按语、内容摘要、术语对照表——那些放进 `_work/` 下的独立文件。

`draft: true` 表示元信息还没人工核过。归档时把 `draft` 改 `false`，否则三个月后分不清哪条是抄的、哪条是猜的。

**每篇译完做归档，这是"随翻译积累"的全部动作**：

```bash
# 把本篇项目表并回总表，看新增冲突
python scripts/merge_glossary.py _work/<stem>_术语.csv -o _work/merge
```

术语有脚本，风格没有——**风格总表靠你一分钟的判断**。译完翻一遍 `_work/<stem>_风格.md` 里改过的项，问一句：这条是这篇的特例，还是我的偏好变了？

- 只有这篇因为作者用法特殊 → 留在项目文件，不上抬
- 连续两三篇都这么改 → 并回 `references/style/default.md`，下次开篇复制到的就是新基线

不并回，总表就永远停在旧值，每篇都得重改一遍；单篇特例上抬，下一篇会被莫名其妙地约束。分寸在"连续两三篇"这个尺度上，不在单次。

只看报告里"待裁决"涨了多少：涨得多说明这个分支的译法还没收敛，该停下来定一次内部标准，而不是继续逐篇临时决定。若确认没有新冲突，把 `_work/merge/glossary_master.csv` 的条目并回 `references/glossary/glossary_core.csv`，下次翻译即可查到。

对话里只回复：译文绝对路径；校验结论（哪些通过、哪些需人工判断）；原文中有无疑点或提取缺陷；以及没做的部分（没有附录、公式是图片无法提取）；**Zotero 挂载状态**（`attached`／`updated`／`unchanged`／`pending（需你点授权）`）。不复述译文内容。

**不要**在正文末尾追加"译者说明""术语对照表""译后记"——除非用户明确要求。它们会让译文与原文结构不再一一对应。
### 发布稿口径：把元信息从正文里清掉

期刊 PDF 的正文前后有一批**只属于原刊、不属于译文**的内容。用户要的是"拿得出去的文章"，这些一律不进发布稿：

| 要删的 | 为什么 |
|---|---|
| 标题下的作者名与单位（含 `<sup>1</sup>` 单位角标） | 属于原刊署名；译者是另一个人，留着会误认 |
| `作者说明`／`Author's Note` | 刊物栏目话术 |
| `致谢`／`Acknowledgments` | 同上 |
| `ORCID iD` | 同上 |
| `资助`／`Funding` | 同上 |
| `利益冲突声明`／`Declaration of Conflicting Interests` | 同上 |
| 参考文献前的"按体例保留原文，不译。共 N 条。" | 这是流程备注，不是文章的一部分 |

删完后**脚注要重编号**——原稿第一条脚注常是"作者单位"，删掉它之后第二条得喊 1。

**删了正文，对账基准也得跟着删。** 做法同上：复制一份 `_work/<stem>_原文_发布口径.md`，把这几节与作者行一并去掉，用它做 `fidelity_check.py` 的源文件。**不要**直接改原文来迁就校验。

标题本身怎么处理，看分发渠道：Markdown 交付稿可以留 H1；**公众号版不放标题**（微信有自己的标题字段，正文里再写一遍是重复），front matter 里的 `title` 照留，那是元数据。

### 可选：编译 PDF 版（页底脚注）

用户要 PDF 时走这一条，不要手搓模板；`md2tex.py` 与 `dl-translation` 是同一份实现，踩过的坑都写在 [references/pdf-latex.md](references/pdf-latex.md)。

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex --source-pdf paper.pdf --pdf
python scripts/verify_pdf.py _work/pdf/paper.pdf --tex _work/pdf/paper.tex \
    --md <stem>_zh.md --footnotes _work/脚注.csv
```

默认 `--footnotes footnote`：正文 `[^n]` 渲染成 LaTeX 页底 `\footnote{}`，**脚注格式保留在 PDF 里**；要尾注形式用 `--footnotes endnote`。`verify_pdf.py` 检查编译 `!` 错误、`Overfull \vbox`（长表被整块截断）、`includegraphics` 数、书签重复、文本层汉字与连字，并**逐条核 `脚注.csv` 的内容是否进了 PDF 文本层**；有问题返回 1。PDF 与公众号版是两条独立发布分支，都以同一份 `[^n]` 译稿为源。

### 公众号版：另出一份可直接粘贴的排版稿

```bash
python scripts/build_wechat.py <stem>_zh.md <输出目录>
```

产出两份：

| 文件 | 用途 |
|---|---|
| `wechat_article.html` | 完整网页，顶部有"复制全文"按钮，粘进公众号编辑器即带样式 |
| `wechat_article.md` | 纯文本备份，日后改字用 |

脚本按用户的发布口径处理，规则写死在代码里，不需要每次交代：

1. **去掉标题**——H1 与 front matter 里的 title 都不上版面。
2. **去掉参考文献整节**——公众号里放一百条英文著录没有意义，读者需要的是原文 DOI。
3. **脚注改就地引用框，正文保留上标**——文末的脚注节拆开，每条按编号**放回它所注的那一段之后**，用左侧竖线的框呈现；同时**正文里的上标标记要留着**（转成带色的 `span`）。只做框不做标记，读者不知道这句话有注；只做标记不做框，注释得跳到文末再跳回来，等于没注。**本流程上游统一交 `[^n]` + `## 脚注` 节**（第 1 步 `footnote_recover.py --apply` 的产物）；脚本仍兼容历史稿：正文 `<sup>n</sup>`、`## 脚注` / `## 注释` / `## Notes` 节下的 `1.`、`(1)`、`-`、`注 1`、`<sup>1</sup>` 条目、折行与无空行连排、`<!-- FOOTNOTES-RECOVERED -->` 标记都认。
4. **开头两行信息**——`翻译&编辑：X`（同一人时合并写，不同人时写"翻译：X　编辑：Y"），换行接 `文献来源：` 后跟 APA 7 条目（`作者 (年份). 题名. 刊名, 页码.`）。用浅灰小字压在正文之上，与正文之间留一条细线。**题名只给原文，不加中译方括号、不挂 DOI**——公众号读者要看的是这篇东西是谁写的、发在哪，中译题名与 DOI 属于参考文献体例，两者混在一行会读成半中半英。
5. **表格压进 637px，不做横滑**——微信里 `overflow` 无效，横向滑动做不出来。四列表格只能按 px 分配：首列 88px 放"控制概念"这类标签，其余三等分各 183px，字号降到 13px。

### 微信的白名单：为什么用 class 写样式一定会掉

公众号编辑器把粘进来的 HTML 过一遍**白名单过滤**：保留结构标签与写在元素 `style=""` 里的样式，**删掉 `<style>` 块、`<link>`、全部 class 与 id**，并过滤掉一批属性。所以"本地好看、粘过去散成裸文本"的唯一原因是样式没内联——不是浏览器的问题，也不是复制方式的问题。

写版式时守住这六条，粘过去才不会走样：

| 约束 | 做法 | 为什么 |
|---|---|---|
| 样式全内联 | 每个标签带完整 `style=""`，不生成样式表 | `<style>` 与 class 一律被删 |
| 容器用 `<section>` | 不用 `<div>` | section 在白名单里，底色与圆角更容易保住 |
| 单位用 px | 宽度、边距、字号都写 px | 百分比与 `vw` 在窄屏会被压变形甚至被过滤 |
| 避开布局属性 | 不用 `position`、`flex`、`grid`、`transform`、`box-shadow`、`overflow` | 前四个会被清除；`overflow` 无效，横向滑动做不出来，表格只能压到 637px 内 |
| 上标用 `<span>` | `font-size:11px;line-height:0;vertical-align:super` | `<sup>` 不在稳定白名单，可能退化成普通数字；`line-height:0` 防止撑行高 |
| 不用 CSS 变量 | 颜色写十六进制字面值 | `var(--x)` 不解析 |

正文区实测可用宽度约 **637px**（编辑器 677px 减去两侧内边距）。四列表格按 `88px + 183px × 3` 切，首列刚好放"控制概念"四个字，其余均分；靠 `%` 分配会被压成一列。

`build_wechat.py` 的 `self_check()` 会拦住上面每一条，输出前自检，不过就报错不写文件。同一次自检里 `audit_notes()` 另管内容完整性：抽出脚注却一条没进版面、某条只有定义没上版面、输出残留字面 `[^n]` 或裸 `<sup>`，同样是硬错误；正文上标找不到定义、定义找不到上标只作提醒。**样式通过不等于内容通过**——只查样式的那版曾让 `[^n]` 稿子静默丢光脚注还报"自检通过"。

**粘贴方法**（两条都对，按钮更省事）：

1. 浏览器打开 `wechat_article.html`，点顶部"复制全文"，到编辑器 `Ctrl/⌘+V`。脚本只把根 `section` 的 `outerHTML` 写进剪贴板，按钮与页面底色不会带进去。
2. 编辑器右上角开**源码模式**，把 `wechat_article.html` 里 `<section id="wx-root">…</section>` 整段贴进去，再切回富文本视图。

粘完在手机上预览一次。少数情况下底色仍掉，用壹伴或 135 编辑器中转一遍即可——它们做的就是同一件事（CSS 内联化），只是多一层兜底。

## 第 7 步：回挂 Zotero（有 PDF 时）

文献多半是从 Zotero 文献库里拖来的，译文 PDF 出完、`verify_pdf.py` 通过之后必须挂回原条目——产物散在工作区里，过三个月没人知道它对应哪一条。这一步**向外部系统写数据**，所以有独立的状态、退出码和账本，不是"顺手做一下"。

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md   # 单篇
python scripts/zotero_attach.py --batch . --strict                # 一次交付多篇
```

走 **Zotero 本地 API**（`127.0.0.1:23119`），不碰 `zotero.sqlite`，不需要 zotero.org 账号，也不需要 `pyzotero`：

- **读**（锚定、判重）不需要任何授权；
- **写**（建附件、传文件）第一次会弹窗，点 **Always Allow**，key 存 `~/.workbuddy/zotero.json`，以后零弹窗；
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
| `scripts/mineru_extract.py` | PDF/图片/Office → Markdown，token 只需设置一次 | `--set-token`、`--token-status`、`--pages`、`--ocr`、`--model` |
| `scripts/split_refs.py` | 把参考文献区换成一行标记（不进上下文），交付前原样拼回 | `--check`、`-o`、`--restore`、`--heading` |
| `scripts/footnote_recover.py` | 从 `content_list.json` 恢复页底脚注；两侧自动补 `## 脚注` 节、中文回填、PDF 文字层交叉验证与内容级门禁（与 `dl-translation` 同一实现） | `-o`、`--source`、`--target`、`--apply`、`--translations`、`--check`、`--pdf`、`--pdf-out`、`--skip-footnote-check` |
| `scripts/footnotes.py` | 兼容入口：把旧的 `--md/--strict/--patch` 命令转发到 `footnote_recover.py`；不再作为主流程 | 旧参数 |
| `scripts/build_wechat.py` | 译稿 → 公众号排版稿；脚注归一、挂到所注段落后、硬校验不许静默丢失 | `<译稿.md>` `<输出目录>` |
| `scripts/md2tex.py` | 译稿 → XeLaTeX／PDF；`[^n]` 默认排成页底真脚注，URL 走 `\url{}`，xelatex 跨进程锁 | `--pdf`、`--footnotes`、`--source-pdf`、`--title-en` 等 |
| `scripts/verify_pdf.py` | PDF 验收：编译错误、`Overfull \vbox`、图片数、书签、文本层、逐条核脚注是否进 PDF | `<PDF>`、`--tex`、`--md`、`--footnotes` |
| `scripts/_test_footnotes.py` | `build_wechat.py` 的脚注形态回归测试（13 种写法 + 1 条必须报警的失败用例） | 无 |
| `scripts/extract_terms.py` | 从英文原文挖候选术语，标注已收录/新增，可生成项目表模板 | `--glossary`、`--min-count`、`--top`、`--write-project` |
| `scripts/mine_terms_from_pairs.py` | 有平行译文时，从「原文—译稿」句对反推实际用过的译法 | `--auto`、`--pairs`、`--min-count`、`--known` |
| `scripts/lookup_term.py` | 按词查项目术语表与总表，避免整份读入 | `--glossary`、`--exact` |
| `scripts/filter_terms.py` | 剔除候选表中的通用词与噪声，按证据强度区分主表与待核 | `--names`、`--min-docs`、`--keep-more` |
| `scripts/zh_quotes.py` | ASCII 引号 → 中文引号，跳过 front matter／参考文献／公式／代码 | `--inplace`、`--check`、`--all` |
| `scripts/style_check.py` | 扫口语化痕迹：按词表与句式列出可疑句，不自动改；`--style` 并入本篇禁用词 | `-o`、`--max`、`--style` |
| `scripts/semantic_audit.py` | 按段比对数值：年份、小数、百分比、千分位、页码区间；只查数字 | `-o` |
| `scripts/review_queue.py` | 生成待校对清单：术语不一致、表内待定、新术语候选、人工判断项、马恩引文 | `--glossary`、`--manual`、`--init-manual`、`--marx`、`--marx-note` |
| `scripts/marx_adopt.py` | 把裁好的引文译文（采用表）转成 `review_apply.py` 的决定表 | `--quotes`、`--adopt`、`--target` |
| `scripts/marx_quotes.py` | 把英文原文里的马恩引文对到《马克思恩格斯文集》译文，带卷次/章/页与可信度 | `--source`、`--target`、`--marxref`、`--years`、`--map`、`--anchor` |
| `scripts/review_apply.py` | 执行人的意见：改术语表、改译文、重跑校验、登记已决条目、重生成清单 | `--decisions`、`--resolved`、`--manifest`、`--suggest` |
| `scripts/paper_meta.py` | 生成、写入、检查译文顶部的 YAML 元信息 | `--init`、`--inject`、`--check` |
| `scripts/zotero_attach.py` | 把已验收的译文 PDF 挂回 Zotero 父条目（本地 API 读写，Zotero 10+ 可自动上传；filename+md5 判重，改稿原地覆盖；不碰 sqlite） | `<PDF>`、`--md`、`--batch`、`--strict`、`--parent-key`、`--title`、`--doi`、`--attach-title`、`--prepare-only`、`--dry-run`、`--stage` |
| `scripts/normalize_math.py` | 统一 `\[…\]`→`$$…$$`、`\(…\)`→`$…$`，跳过代码块与 `\\[2pt]` | `--inplace`、`-o`、`--check` |
| `scripts/fidelity_check.py` | 与原文对账：结构、引用、公式、未译段、术语一致性；硬查脚注清单与译文 `## 脚注` 节；`--strict-soft` 可把建议项升级为硬失败 | `--glossary`、`--strict`、`--strict-soft`、`--skip-footnote-check` |
| `scripts/merge_glossary.py` | 合并多份术语表，做姓名规范化与权威译名裁决，输出四态分流 | `-o`、`--verified`、`--no-normalize` |
| `scripts/prune_glossary.py` | 按跨文献频次裁剪术语表，低频条目移入档案 | `--min-files`、`--keep-verified` |

全部只用 Python 标准库，无需安装依赖。唯一的外部依赖是 `_marx_ref`（马恩文集句级索引），可选：没有它，第 4 步的引文匹配跳过，其余照常。
</scripts>

<glossary_resources>
`references/glossary/` 下五份资源，可信度从高到低排列，不要混用：

| 文件 | 规模 | 作用 | 怎么用 |
|---|---|---|---|
| `empirical_terms.csv` | 183 条 | **从已译文献反推的实证译法**，带出现次数与覆盖篇数 | 定译法时的第一依据；译为通用词汇但保留有分歧风险的词 |
| `verified_names.csv` | 240 条 | 有外部依据的权威译名（经典译本、新华社地名、通行音译） | 由脚本自动套用；新增条目后下次合并即生效 |
| `core_terms_draft.csv` | 134 条 | 政经核心概念译法，**待校对** | 起步时逐条确认，把 `status` 改成 `已定` |
| `glossary_core.csv` | 1170 条 | 跨文献反复出现的专名，含 `tier`（core/common）与 `status` | 按词查，不整份读 |
| `glossary_conflicts.csv` | 192 条 | 仍有多种译法、须人工裁决 | 首次使用前裁决高频项 |

`empirical_terms.csv` 与其余四份的区别在于证据类型：其他几份是"通行译法"或人工判断，这一份是"你在自己的译稿里实际用了什么"，每条都能追到原文与译文对得上的句子。它覆盖 16 篇已译文献、8179 个句对，所以只在政治经济学语料内有效，不要拿去套别的领域。

**它只收有分歧风险的词。** `worker`、`price`、`data`、`management`、`technology` 这类通用词被显式剔除——它们没有译法空间，收进来只会让表变长、让真正的术语被稀释。`agent`（主体／代理人）、`tension`（张力／紧张）、`realization`（实现／兑现）保留，因为换一个写法读者会理解成另一个概念。

`glossary_core.csv` 是从 5404 条原始累积中裁出来的：只保留**在 ≥2 份文献里出现过**的条目，以及所有有权威译名的条目。被裁掉的 4234 条多为参考文献里的人名与出版地——依规则 4，参考文献整条保留原文，这些人名根本不需要中文译名。裁剪可逆，`prune_glossary.py --min-files 1` 可复原。

`status` 四种取值：`已定`（有权威依据）、`一致`（唯一译法，无冲突）、`待裁决`（多译法并存）、`待人工`（结构异常）。只有 `已定` 和 `一致` 可以直接用。

频次推荐只反映过去几篇稿子碰巧怎么译，不构成正确性证据。裸姓氏尤其可疑——`smith` 可能是 Adam Smith（斯密），也可能是 Chris Smith（史密斯），脚本不会替你选。

维护、扩充与"从零积累核心术语表"的方法见 [references/terminology.md](references/terminology.md) 与 [references/terminology-growth.md](references/terminology-growth.md)。
</glossary_resources>

<fidelity_notes>
几条容易做错、且对账脚本抓不到的判断：

**原文错误不许静默修正。** 公式漏了下标、数字前后矛盾、引用年份与文献表不符——照原样译，然后在报告里写明位置与自己的判断。改了就变成"你的文章"而不是"译作"。

**提取缺陷不算原文。** MinerU 常把上下标压平、把 `O(n)` 读成 `0(n)`、把连字符断词接错。凡是提取结果与 PDF 目视不符，以 PDF 为准改正，并在报告里记下改了哪几处——这不算修改原文。

**引文页码是引用的一部分。** `(Marx, 1867, p. 163)` 里的 `p. 163` 原样保留；不替换成译本页码。

**作者自造的术语保留原文。** 有通行译法的照译；作者自造、学界无定译的，首次出现译后加原文括注，之后统一用中文——括注只在首次，不要每处都加。

**否定与量的范围。** `not all` 不是 `none`；`few` 不是 `some`；`tends to` 不是 `does`。政治经济学的论证常建立在这类量的差别上，译错一个词整段论证就反了。
</fidelity_notes>

<reference_files>
| 文件 | 何时读 |
|---|---|
| [references/translation-rules.md](references/translation-rules.md) | 动笔前；拿不准某处算不算增删、引用该如何处理时 |
| [references/semantic-review.md](references/semantic-review.md) | 第 4 步语义审读时；想知道"哪些类词表查不了、怎么读"时 |
| [references/style-sheet.md](references/style-sheet.md) | 第 3 步之前；定全篇语体约定、怀疑前后段行文不一致时 |
| [references/style/default.md](references/style/default.md) | 开新篇复制为项目文件；想改跨篇默认值（连续几篇都变了）时 |
| [references/workflow.md](references/workflow.md) | 长文（>1 万字）、需要断点续译、或多个文件批量处理时 |
| [references/terminology.md](references/terminology.md) | 建立项目术语表、裁决争议译法、扩充总表时 |
| [references/terminology-growth.md](references/terminology-growth.md) | 想从零系统积累核心术语表、判断某个词该不该进表时 |
| [references/marx-ref.md](references/marx-ref.md) | 有马恩引文、要核对文集译文、判断匹配可信度时 |
| [references/mineru.md](references/mineru.md) | 需要从 PDF 提取、token 配置出问题、提取质量可疑时 |
| [references/footnotes.md](references/footnotes.md) | 第 1 步脚注恢复；判断交叉验证结果、编号冲突、跨页续文与边界时 |
| [references/pdf-latex.md](references/pdf-latex.md) | 用户要 PDF 时；编译、页底脚注模式、验收清单与已知排版坑 |
| [references/review-checklist.md](references/review-checklist.md) | 交付前 |
| [references/zotero.md](references/zotero.md) | 文献来自 Zotero、要把译文 PDF 挂回条目时 |
</reference_files>

<versioning>
## 版本与更新

本 skill 由 Git 管理。`SKILL.md` front matter 的 `version` 只作人读标识，格式 `<官方基线日期>.<本地修订号>`；**版本历史与变更记录一律以 `git log` / `git tag` 为准**，不在 skill 内维护 CHANGELOG、指纹或版本号脚本。

```bash
git tag v2026-11-07.2                          # 发版
git log --oneline -- scripts/ references/    # 变更历史
git log --oneline -- SKILL.md                 # 单文件历史
```

官方基线是 `political-economy-translation_skill_2026-11-07.zip`。更新官方包时**不要整份覆盖**：仓库里留一个 `upstream` 分支存官方原版（拿到新 zip 就解压、提交到该分支），本地改进留在 `main`；`git merge upstream` 会把「两边都改过」的文件报成冲突，逐个人工合并即可——这就是原来的 `--compare` 在做的事，Git 原生做得更准。

当前相对官方基线的本地改动（合并 upstream 时重点看这几处）：

- 新增 `scripts/footnotes.py`、`references/footnotes.md`
- 改写 `SKILL.md`、`references/mineru.md`、`references/review-checklist.md`
- 重写 `scripts/build_wechat.py` 的脚注层：`[^n]` / `<sup>n</sup>` / `## 脚注` 节统一归一，新增 `audit_notes()` 硬校验；配 `scripts/_test_footnotes.py` 回归测试。旧版只认 `<sup>`，`footnotes.py --patch` 过的稿子会静默丢光脚注

若仓库采用「多个 skill 各占一个子目录」的结构，本地 `~/.workbuddy/skills/<name>` 可用 Windows 目录联接（junction）指向仓库子目录：编辑即提交，无需双向同步。
</versioning>
