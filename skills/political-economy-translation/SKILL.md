---
name: political-economy-translation
description: 将英文政治经济学文献（马克思主义价值理论、斯拉法/剩余方法、劳动过程理论、金融化、全球价值链、平台劳动等）翻译为中文 Markdown，并做机械对账。输入可为 PDF、已提取的 Markdown、docx；输出段落与源文一一对应、Markdown 结构不变、引用原样、公式统一为 $$…$$ 与 $…$ 的译文；成品只留标题、作者、正文、附录，刊头与声明移入 YAML front matter；一次多篇时一篇交给一个子代理。This skill should be used when translating political-economy papers, book chapters, review essays, or lecture notes into Chinese under strict fidelity constraints, when a MinerU extraction step is needed first, and when a batch of accumulated glossary CSVs has to be consolidated before translating.
agent_created: true
version: 2026-11-21.2
---

# 政治经济学文献翻译

把一篇英文政治经济学文献变成可直接投稿或发布的中文 Markdown，并且**能证明**没有漏段、没有多加话、引用没被改、公式格式统一。

难点不在英文，在四件事：术语必须前后一致（`labour power` 不能一处"劳动力"一处"劳动能力"）；人名音译必须统一（`Shaikh` 不能随机"谢赫"/"沙伊赫"）；公式与引用是硬约束（错一个符号、改一条文献，审稿人立刻发现）；中文要读起来像中文写的，而不是英文的倒影。

<what_this_skill_is_for>
**适用**：期刊论文、书章、书评、会议论文、讲义、工作论文的英译中；正文含大量公式与文献引用；译文要交给编辑、导师或期刊。

**不适用**：中译英（对账逻辑假定源为英文）；纯数学教材或论文（用 `mathtranslations`）；只要摘要或要点；扫描件无可提取文字且未 OCR；整本书的翻译与统稿——本 skill 按单篇处理，一篇一个术语表、一篇一次对账；书里单独一章当论文译，适用。
</what_this_skill_is_for>

<non_negotiable_rules>
六条硬规则。违反任何一条，译文就不合格，不管读起来多通顺。**边界与判例见 [references/translation-rules.md](references/translation-rules.md)。**

**1. 忠实原文，不增不删。** 段落与源文严格一一对应：不合并两段、不把一段拆成两段、不省略"重复"的过渡句、不加原文没有的解释、背景、评价。译者想补充的内容一律不进正文。

**2. 保留 Markdown 结构。** `#` 层数与顺序、有序/无序列表及层级、`>` 引用深度、表格行列、图片路径、脚注标记、代码块、`**粗体**` `*斜体*` `` `代码` `` 全部原样。只译文字，不动标记。

**3. 在忠实的前提下做到信达雅。** 调语序、拆长句、补虚词与量词、把名词化还原成动词、把被动改主动，都属于"润色"而非"增删"。判据：改写后信息量完全等价，且中文读者不必回看英文就能懂。**禁止为通顺模糊掉限定词**（`only`、`merely`、`tendentially`、`in the long run`、`as such`）——它们在政治经济学里是承重的。**顺序固定：准确 → 通顺 → 文气，不可倒做**；润色的门禁、留痕与复检见 [references/refinement.md](references/refinement.md)。

**4. 文献引用保持原样，不翻译。** `(Shaikh, 2016, p. 42)`、`Marx (1867)`、`[12]`、`ibid.`、`op. cit.`、参考文献条目整条、引文中的书名与篇名，逐字符保留。分界：**正文叙述里的学者姓名音译，括号内引用原样**。

**5. 公式定界符统一。** 行间一律 `$$…$$`，行内一律 `$…$`；`\[…\]`→`$$…$$`，`\(…\)`→`$…$`。公式内容不译、不改写、不重排，`\text{…}` 内英文保留。由 `scripts/normalize_math.py` 机械完成。

**6. 成品只留标题、作者、正文、附录。** 刊名与卷期页码、版权行、复用指引、DOI、刊物网址、出版社标记、收稿／接受日期、JEL 分类、关键词、致谢、资助、利益冲突声明、伦理／可复现性声明、ORCID、作者简介——**一律不进译文**，它们要么进 YAML front matter，要么本来就不必给读者看。**标题（H1）与作者行保留**：读者拿到的是一篇署名文章，不是一份无署名的内部稿；作者行只留姓名，删单位角标、通讯邮箱与 ORCID。摘要属于正文，保留。清单、去处与脚本见 [references/delivery.md](references/delivery.md) 第四节。
</non_negotiable_rules>

<workflow>
按顺序执行。每一步都有产物，下一步读上一步的产物，不要跳步凭记忆往下写。

## 第 0 步：确认源与交付

- 源优先级：**出版版 PDF > 作者 docx/tex > MinerU 提取的 Markdown**。冲突以 PDF 为准，提取结果只是工作草稿。
- 交付默认 Markdown；**顺口问一句要不要 PDF**，公众号排版稿也是可选分支（见第 6 步）。两条发布线都以同一份 `[^n]` 译稿为源，互不干扰。
- 输出放源文件同目录，命名 `<原文名>_zh.md`；中间产物放 `_work/`。用户没说清只问一次。
- **一次多篇 → 一篇一个子代理**，不要在自己这里轮着译（见下）。

### 多篇并行：一篇一个子代理

同时交来两篇以上时，**为每篇起一个子代理**，让它从第 1 步跑到第 6 步。主代理不译正文，只做分发、核对与汇报。

任务说明要自足：该篇的源路径与产物路径、目标读者、交付口径（第 0 步那几条）、术语来源（继承批次表还是新建）、以及"跑完把 `_work/` 证据与校验结论报回来"。子代理看不到这次对话，**没写进去的要求它不会知道**。

三条理由都是实测踩出来的：

- **术语会串味。** 同一上下文里两篇互相感染，第二篇会悄悄继承第一篇的临时决定，而那未必适用。
- **对账会混。** 两篇的 `_work/` 里 `脚注.csv`、`公式差异.csv`、`术语.csv` 名字几乎一样，交替操作时读写错文件不会有任何报错。
- **上下文会被两篇正文挤爆。** 单篇长文的原文已占掉大半个窗口；两篇叠在一起，后半程只能靠印象译，质量掉得比读得慢更明显。

**跨篇术语统一仍然要做**，顺序是：先抽各篇候选 → 合并去重 → 人工裁一次 → 把共同表分给各子代理继承（`references/workflow.md` 第四节）。收齐后主代理逐篇核对：`fidelity_check.py --strict` 是否通过、`paper_meta.py --check` 是否干净、`_work/` 证据是否齐全。**不要只看子代理的回话**——回话是它的结论，产物才是事实。


## 第 1 步：取得可译的正文

**已有 Markdown** → 直接用，先扫提取缺陷：公式是否成了图片、表格是否塌成纯文本、脚注是否丢。

**有 PDF** → `python scripts/mineru_extract.py paper.pdf -o ./_work/extract --model vlm`（首次运行引导录 token，`--token-status` 可查）。参数取舍与排障见 [references/mineru.md](references/mineru.md)。

**有 docx** → pandoc 转 Markdown，同样查公式与表格。

提取完成后**必须对照 PDF 抽查**：随机翻三页，比对段落数、公式、脚注。提取错了再译，等于把错误洗进译文。

### 脚注恢复：提取后、动笔前的硬门槛

MinerU 的版面识别认得出页底脚注（`content_list.json` 里 `type=page_footnote`），但生成 `full.md` 时按类型白名单把它们**整类过滤**：正文常只剩 `<sup>n</sup>`，脚注正文一条也没有。块级对账对此完全免疫——原文与译文一起缺，块数照样对得上。实测一篇 45 页期刊论文 17 条脚注全丢、4 个标记变形，而对账全绿。

```bash
# 1) 恢复并把标记锚回正文、定义落到文末（--pdf 可选，做文字层交叉验证）
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf
# 2) 填 _work/脚注_待译.csv 的 zh 列（中文脚注译文），再回填
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check
# 2b) 脚本判不出位置的：填好 _work/脚注_待锚.csv 的 anchor 列后回灌
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --target <stem>_zh.md --apply --place _work/脚注_待锚.csv --check
```

**脚注不是文末一节，是真正的脚注。** `--apply` 只做三件事：把 `<sup>n</sup>` 归一成 `[^n]`、把每条标记**锚进正文对应句子**、把 `[^n]: 脚注正文` 定义放在文末。**不写 `## 脚注` 标题，不写「第 N 页脚注 n：」页面前缀**——页码和分类只留在 `_work/脚注.csv`。写回前留 `.bak_footnotes` 备份，重复运行幂等。历史稿的「文末补一节」会自动迁移；作者机构／版权注常与正文脚注同号，不占 `[^n]` 编号、不进交付稿，单列 `_work/脚注_原刊信息.md`；版面噪声（`40<sup>th</sup>`）不补。

**标记必须落进正文，这是门禁而不是建议。** 句末裸数字、塞进行内公式的 `^{7}`、提示语对不上的会进 `脚注_待锚.csv`，`--check` 因此返回 1。宁可阻塞，也不要把标记塞到段末——脚注落错句子比缺一条更坏。确认是裸编号可加 `--anchor-bare` / `--anchor-math`；否则人读 PDF 填 `anchor`（正文里紧邻标记前的一句原话），`--place` 回灌。

**`[^n]` 是唯一交付形态**：公众号版 `build_wechat.py` 认它（归一成 `<sup>` 并挂到所注段落之后），PDF 版 `md2tex.py` 默认排成页底 `\footnote{}`。交付稿里不许留字面 `<sup>n</sup>`——`footnote_recover.py --check`、`fidelity_check.py --strict`、`build_wechat.py` 的 `audit_notes()`、`md2tex.py` 的开头门禁、`verify_pdf.py` 都会拦。

`--pdf` 的交叉验证只用来发现提取包被污染或跨页续文被截断：**双栏期刊的脚注在栏底不在页底**，`pdftotext -layout` 的缩进特征会失效，未确认不等于提取包有错（详见 `_work/脚注_交叉验证.md`）。判据与编号规则见 [references/footnotes.md](references/footnotes.md)。无脚注的文献清单 0 条即 PASS，但仍要翻两页页底确认；纯 Markdown 输入无提取包时可加 `--skip-footnote-check` 并写明理由。

### 刊头与版尾先剔掉

期刊 PDF 的首页与文末夹着一批只属于原刊的内容，**在动笔之前就从源文工作副本里剔掉**，别整篇译完再删：译了是白工，还会在术语表里留下 `Conflicting Interests`、`Article reuse guidelines` 这类只有声明才用的词条。

```bash
python scripts/strip_meta.py _work/<stem>_原文_正文.md --meta _work/meta.yaml --check   # 先看清单
python scripts/strip_meta.py _work/<stem>_原文_正文.md --meta _work/meta.yaml --apply   # 剔
python scripts/strip_meta.py <stem>_zh.md --meta _work/meta.yaml --apply                # 译文侧同口径
```

顺序是「脚注恢复 → 剔刊头版尾 → 切书目」：作者简介常排在书目之后，先剔掉，书目才真的是最后一节。剔的是**源文工作副本**（`_work/` 里那份），MinerU 原始提取包不动；两侧同口径跑一遍，块序列仍一一对应，`fidelity_check.py` 不必另造"发布口径副本"。

脚本按标题名与版头特征认，认不出的特例（作者单位写成一段、声明夹在正文中间）手工删，删完把位置记进 `_work/<stem>_待校对.md`。**卷期、DOI、版权、JEL、关键词、资助别丢**——`--dump-yaml` 会把能认的著录打印出来，并进 `meta.yaml`。

**参考文献先切出去，不进翻译上下文。** 书目整条保持英文原样，让模型读它没有收益，代价却实在——一百条英文著录过一遍，总有一条被"顺手"译掉书名或调换姓序。`split_refs.py` 把书目区换成一行 `<!-- REFS-ORIGINAL lines=74 -->`，译文里原样留着，交付前由脚本拼回。命令与三条判定条件见 [references/mineru.md](references/mineru.md) 第七节；没有书目或判定不切时跳过这一步。

### 图表按"首次提及"归位

出版社为不留白把图表挪到两三页之后，MinerU 按版面位置提取，于是"这里写 Table 1 summarizes…，表却在三百字开外"。**规则：图表跟着第一次提到它的那一段走**；连同引出句一起搬，跨节搬要连标题一起搬，一处不能丢、顺序不能乱。

**改了位置，对账基准也要改**：生成 `_work/<stem>_原文_发布口径.md`，在这份副本里把图表挪到与译文相同的位置再做基准——**原文是证据，不改原文文件**。四条细则与多联图的宽度还原（`figure_layout.py` + `md2tex --fig-meta`）见 [references/figures.md](references/figures.md)。

### 人名表缺失时：补进权威层

取名人名走三层（`references/glossary/pick_name.py`）：`names_override.csv` 学界惯用 → `verified_names.csv` 权威译名 → `glossary_core.csv` → 新华社标准。查不到时脚本退 1——**这时不要就地音译了事**，那个人名会在下一篇里再被音译成另一个样子。做法是往 `verified_names.csv` 补两条（`surname` 管正文姓氏单用，`full` 管首次出现的全名），`basis` 写清依据（哪个中译本、哪本工具书）；`glossary_conflicts.csv` 里挂着"待裁决"的顺手标成已裁决。格式见 [references/terminology.md](references/terminology.md)。

## 第 2 步：锁定术语与专名

在动笔之前把译法定下来，不要边译边决定——这是同一篇文章内部不一致的唯一根源。

```bash
# 抽候选（只找候选，不猜译法）
python scripts/extract_terms.py paper_原文.md -o _work/ \
    --glossary references/glossary --min-count 3 --write-project _work/paper_术语.csv
# 查已有资源定译法（用脚本查，不要整份读进上下文）
python scripts/lookup_term.py "surplus value" "Shaikh" --glossary references/glossary/
# 有旧译稿时：从平行语料反推你自己怎么译的
python scripts/mine_terms_from_pairs.py --auto -o _work/pairs --min-count 4
# 候选表瘦身（单篇必须 --min-docs 1）
python scripts/filter_terms.py _work/<stem>_候选术语.csv -o _work/filtered \
    --names references/glossary/verified_names.csv --min-docs 1
```

查不到的按裁决顺序定：**本领域通行译法 > 马恩全集/《资本论》既有译名 > 学界近年论文 > 音译规则**。`empirical_terms.csv` 是唯一有"你自己怎么译"证据的一档（183 条，从 16 篇已译文献反推，带出现次数与覆盖篇数），优先用它。

**候选表先瘦身再定稿**：七成是通用词与共现噪声，不瘦身会淹没真正的术语。判定只有一条——**换一种译法会不会改变论证，或让读者误解成另一个概念**。据此剔除通用词（`worker`/`price`/`data`）、描述性短语（`process oriented`）、提取残片（`mathbf v`），保留 `agent`（主体/代理人）、`tension`（张力/紧张）、`realization`（实现/兑现）这类。**描述性短语不要硬译**：表里出现一个不通的条目，比缺一条危害大——下次翻译会照着它抄。

**项目表定稿后再动笔。** `_work/<stem>_术语.csv` 是此后每一段的唯一依据，只收本篇真正用到的 20–40 条，不要复制总表；术语表是**项目级**的，不跨项目套用。完整裁决规则、资源优先级与合并流程见 [references/terminology.md](references/terminology.md)。

## 第 3 步：通读全文，逐段输出

**上下文和输出是两件事，别捆在一起切。** 一篇一万五千词的论文约两万 tokens，放进窗口毫无压力；真正有限的是"一次能写多长"。旧做法把两者一起切，每块都看不见全文——一致性问题出在这里，不在块大块小。

- **原文整篇读入，不切**（真超窗口按 [references/workflow.md](references/workflow.md) 断点续译）；
- **输出按段推进**，一段 2000–4000 汉字（对应源文约 7000–14000 字符）；
- **段界落在 `##` 或自然段落处**，不在句子中间停；
- **每段写完立刻落盘**——不是为了省上下文，是为了出错能定位。

### 全篇风格锚：一次定，段段照

上下文解决不了风格漂移：模型每段都在重新做词的选择，而选择没有记忆（第 2 段"本文主张"、第 9 段"文章认为"）。所以风格要落到文件上，跟术语表一样分两层：总表 `references/style/default.md`（跨篇默认值）、项目表 `_work/<stem>_风格.md`（`cp references/style/default.md _work/<stem>_风格.md` 后改差异项）。

每段翻译时带**项目表 + 样板段**两样。**样板段比形容词管用**：第一段译完后挑两三百字回填进去，之后每段带着它——写"学术、克制、准确"没有约束力，一段真实译文有。约定定下就别中途改；要改就回头统一改已译部分。细则见 [references/style-sheet.md](references/style-sheet.md)。

每一段按这个顺序走：读对应的原文，数清段落/列表项/公式块/表格各几处 → 译 → 立刻按同样的段落数追加进译文。

译的时候守住这些：

- **段落一进一出。** 源文一段，译文一段，中间不合并；英文常把两个论点塞进一个长段，中文读者习惯分开——但不能分，只能在段内调节。
- **标题译，`#` 数不变**，编号保留，术语照表；**列表项一进一出**，嵌套层级不变。
- **表格**：表头译，数字、单位、显著性星号、括号里的标准误原样，表注照译；**图片**：`alt` 译，路径一字不改。
- **脚注**：标记就地，内容照译。正文只用 `[^n]`（不许 `<sup>`），位置是**被注内容之后、句读之前**；定义写文末 `[^n]: …`，不另起节、不带页面前缀。第 1 步已锚好英文，这里只填中文（`--apply` 不覆盖已有中文）。
- **引用块 `>` 层级保留、内容译**；**代码块与公式块整块不动**。
- **参考文献标记一行不动**：`<!-- REFS-ORIGINAL … -->` 不译、不删、不挪、不缩进、不在前后加空行。它不是正文，是"此处原样嵌入书目"的指令；改写它，`fidelity_check.py` 会报结构块数不一致，`split_refs.py --restore` 也会拒绝拼回。
- **不写译者注**，需要解释的写进"原文疑点"——那属于增。
- **语体是学术书面语。** `东西`／`大把`／`说白了`／`所幸`、调侃与亲切的插入语一律改掉；标准是"这句话能不能出现在《资本论》中译本的注释里"。宁可略生硬，不可口语化；生硬不等于病句，照搬英文框架（`是……加以……的`）仍要改。译完跑 `python scripts/style_check.py <stem>_zh.md --style _work/<stem>_风格.md`，按句列出可疑处，逐句定去留。判据见 [references/translation-rules.md](references/translation-rules.md) 规则 3。
- **句读、语序、主从由你定**：长句该拆、散句该合，都不算增删。**只有一处不能动**：段落、列表、表格、公式的块结构，那是第 4 步对账的依据。

## 第 4 步：机械校验

**对账用切分后的那一对文件**（`_work/<stem>_正文.md` 对 `_work/<stem>_正文_zh.md`），书目区不在账内——拿含书目的原文去对，会对出一串假差异。没切分的稿子照旧用原文对 `<stem>_zh.md`。

```bash
python scripts/normalize_math.py <stem>_zh.md --inplace          # 1) 定界符统一（幂等）
python scripts/zh_quotes.py <stem>_zh.md --inplace               # 2) 引号统一为中文引号（幂等）
python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --strict                     # 3) 与原文对账
python scripts/semantic_audit.py <stem>_正文.md <stem>_正文_zh.md -o _work/<stem>_数字核对.md  # 4) 数字
```

**中文引号是体例，不是可选项**：`"..."`→`“...”`，嵌套沿用 `“……‘……’……”`。`zh_quotes.py` 只动正文，跳过 front matter、参考文献、公式、代码、图片语法与英文所有格撇号（`Dymski's`）；引号数不成对时它会提示——那说明有一处落单。

`fidelity_check.py` 查块级结构、标题层级、列表项、引用块、表格行、图片路径、引用是否原样、`\[` `\(` 是否清零、整段未译、段长异常、术语混用，以及**脚注门禁**（清单存在、每条既有定义又有正文引用、无悬空/孤儿/乱序）。

**引文是不是马恩原话，交给 `_marx_ref` 对一遍**：`marx_quotes.py` 把英文引文对到《马克思恩格斯文集》中文译文，先按引用年份把范围收到对应那一卷（`--anchor vol`，默认）——全库搜时 `(1978: 351)` 会配到第 5 卷，收到第 6 卷才落对。它同时抓带引号的串与**没有引号、末尾只缀 `(1978: 357)` 的裸段落**（长引文在提取稿里的常态）。**引号体例与引用体例都要先看一眼**：Sage／T&F 的英式排版通篇单引号 `‘…’`（脚本自带扫描，引擎只认双引号），引用串则有 `(1978: 357)`、`(Marx [1867] 1976: 173)`、`(Marx, 1987a [1872]: 90)` 三种写法，最后一种年份后不接冒号、锚定靠方括号里的首版年——遇到 MEGA 体例记得把版刻年一并写进 `--years`。判据不是分数（作者引 Penguin 版、文集底本是 MECW，对得上也常只得 0.2–0.5），而是**卷次与引用年份是否相符、同篇引文章是否集中、前两名候选分不分得开、引文里的数字对不对**。引到**未入库的卷**（如 1973 年 Penguin《大纲》，中文在第 8 卷）时，`锚定` 列会写「缺卷·全库」并把该行压到「低」——那行是全库搜出来的巧合，不要用。

**引擎给的译文要裁**：它会把命中句与前后句拼起来打分，返回的「文集译文」常比引文本身长得多。CSV 的 `裁句提示` 按字数比标出（英译中正常 1.6–2.0 倍，超 2.6 倍就是带了引文之外的上下文），但**哪几句才算引文范围脚本判不了**——要读英文引文与中文候选逐条裁定，写进采用表（`marx_adopt.py` 转成决定表）。**引文默认直接用文集译文**，不再另译。三种情况不要硬套：文集里没有这一句（多为作者转述）、文集中文本身残缺、文集译文在此语境读不通——都写进 `说明`。只产 CSV，**不要产双语对照 md，也不要用 annotate 回填**。详见 [references/marx-ref.md](references/marx-ref.md)。

**结构对账管"有没有少"，管不住"意思有没有偏"。** 长文翻译错得最多的不是整段，是**只差一个词、整句判断就反了**的地方。

- **数值可以机械查**：`semantic_audit.py` 按段配对只比数字（年份、小数、百分比、千分位、页码区间），`10,000`/`10 000`/`10000` 归一后算同一个值。数字没错时它安静地报 0 处，那是正确结果。
- **否定、限定、逻辑不要交给脚本。** 试过：Saros2014 报 11 处，逐条核完 6–8 处是误报（`thus far` 被当因果 `thus`、"自从"义的 `since` 被当因果、`must` 译成"还须"被判漏译）。补词表修不掉——同一个词在不同位置承担不同语义功能，字符串匹配看不见。
- **语义偏离只能读**，方法见 [references/semantic-review.md](references/semantic-review.md)：逐段读、只给"通过/偏离/疑点"三种结论、偏离必须贴原文与译文两段。**更好的做法是换个执行者**：把原文与译文交给独立上下文的子任务，不给它翻译过程与术语决策，让它按三态结论逐段列段号、写文件，不接受"整体准确"。实测它报出的一个疑点是真的（`given the organic composition of capital` 译作"就资本有机构成而言"，丢了"在 q 既定时"这层限定）。但它消除的只是"我刚译完所以我觉得对"，不是模型的能力边界。
- **脚本通过不等于译文合格**：块级结构发现不了段内增删（靠段长启发式兜底，而启发式会误报），也不能判断译文对不对、术语准不准、中文通不通。

**口径要分清**：块结构、引用、公式残留、正文卫生、脚注门禁是真硬校验（`--strict` 返回 1）；疑似未译段、段长异常、术语一致、语体是建议性发现（误报多，只打印不拦）；要零容忍加 `--strict-soft`。

人工复核清单（详细版见 [references/review-checklist.md](references/review-checklist.md)）：每段都译了吗；限定词保住了吗；术语与表一致吗（含复数、所有格、缩写）；中文像中文吗（成串的"的"、连续的"被"）；数字年份页码逐个对过吗；原文含糊处记进报告了吗（**不要替作者圆场**）。

### 精校轮：先准确，再通顺，最后才是文气

润色是整条流程里唯一"改对的地方可能改出新错"的环节，所以要独立成一轮、带门禁、留痕。三层不可倒序：**L1 保真**（量与否定、模态、时点、指代、术语、引文——**原文说了算**，术语表和前译都不是权威）→ **L2 句法**（语序、断句、名词化→动词、被动→主动、代词还原——译者全权）→ **L3 文气**（节奏、用词轻重——可整层跳过，跳过仍可交付）。**L1 的候选就是上面语义审读的产出，不重做**；这一轮新增的是 L2／L3 与"裁决—编辑—复检"这条线。

四个动作，每个带一次检查：

1. **候选只记录，不动正文**：散装候选统一进 `_work/<stem>_精校候选.csv`（`段号,层,类型,原文片段,现译,建议,依据,裁决,动作`），不改文件。散在对话里就无法统计覆盖率，也无法回退。
2. **裁决回原文**：只认"原文这句话说了什么"。四种错误裁决要挡掉——"术语表这么定所以对"（表定词形，不定此句意思）、"前面十处都这么译"（一致性≠正确性）、"作者用词不严谨我按本意译"（替作者改）、"加半句限定更清楚"（是增）。`dismiss` 也要写依据，空着的驳回和没查过没有区别。
3. **最小编辑**：只改被裁决指出的那一处（顺手改邻句会污染 diff）；跨段一律不做（段界是对账基准）；`[^n]`、`$$…$$`、`(Shaikh, 2016, p. 42)`、`<!-- REFS-ORIGINAL … -->`、`#` 与列表符号、图片路径一个不碰。diff 行数超过候选条数三倍，说明改过头了。一段 L1 偏离超过三处，重译比逐处改便宜。
4. **复检**：三层任何一层动过都重跑第 4 步那四条命令，不许"只是改了措辞"免检。脚本只保证"与改前一致"，改过引文、数字、限定词的地方要回原文再核——脚本不保证"与原文一致"。

同一处被两个来源给出冲突建议（术语表要 A、语义审读要 B）时，不要挑一个、也不要折中成第三种：进 `_work/<stem>_精校冲突.csv` 交人裁决。

收据写成**段号区间**，写清每层各几条，让人一眼看出有没有跳段：`精校覆盖 §1–§58（L1 偏离 5、疑点 2、L2 26、L3 9、驳回 7）`。完整判据、错误裁决表与冲突处理见 [references/refinement.md](references/refinement.md)。

## 第 5 步：审校清单与回填

三类判断不能替用户做，也不该悄悄做掉：**语义歧义**、**学派立场**、**原文疑误**。

**翻译时就记，不要等到最后补。** 第 3 步之前先 `python scripts/review_queue.py --init-manual _work/<stem>_人工待校.csv`，遇到情况随手写一行（`位置,类型,原文,译法A,译法B,建议,理由`）：`多译法`（`surplus approach` 剩余方法/剩余进路）、`歧义`（`determination` 决定/规定）、`学派立场`（`regulation` 调节（调节学派）/规制）、`原文疑误`、`文风`。

```bash
python scripts/review_queue.py <stem>_原文.md <stem>_zh.md \
    --glossary _work/<stem>_术语.csv --manual _work/<stem>_人工待校.csv \
    --suggest _work/<stem>_候选术语_建议.csv --resolved _work/<stem>_已决定.csv \
    --marx _work/<stem>_马恩引文.csv --marx-note _work/<stem>_引文备注.csv \
    --marx-adopt _work/<stem>_引文采用.csv -o _work/<stem>_待校对.md
```

清单是给人读的：一条一个问题，下面留「你的意见：」，写"按建议"就够。五节：要你定的（附备选、建议、理由）／我可以直接改的（术语表定了但译文没用上）／只在括号引用里出现的（按规则 4 本就保留英文，**不要混进第 2 节**）／候选术语（**必须带上下文与建议译法**）／马恩引文（5.1 并排给"文集原话/现译"；5.2 摊开低匹配项，**跑完要逐条核查**并把结论写进 `引文备注.csv`）。

人回完后一条命令收口：

```bash
python scripts/review_apply.py --target <stem>_zh.md --glossary _work/<stem>_术语.csv \
    --decisions _work/<stem>_决定.csv --resolved _work/<stem>_已决定.csv \
    --source <stem>_原文.md --manifest _work/<stem>_待校对.md \
    --manual _work/<stem>_人工待校.csv --suggest _work/<stem>_候选术语_建议.csv
```

决定表列 `键,动作,旧,新,说明`：`term:<原文>`（改术语表，`旧` 非空时顺带换掉译文旧写法）、`text:<任意>`（只替换译文）、`candidate:<原文>`（`accept`/`drop`）、`manual:<原文>`（`keep` 仅登记）。脚本一条龙改表改译文、重跑归一与对账、登记已决、重生成清单；**任何一条改不动都停下来报出来，不静默跳过**。

**交付时按这个顺序说**：必须你定的（给两种译法与各自后果，不要只说"请确认"）→ 建议确认的（证据薄的条目）→ 已按约定处理的（一句话带过）。**清单是空的也要说清空的是哪一层**——"机械检查零发现"不等于译文没问题，只等于结构、引用、公式、术语对得上。

## 第 6 步：交付与归档

**先把书目拼回去**：`python scripts/split_refs.py --restore _work/<stem>_正文_zh.md -o <stem>_zh.md`（sha256 对不上就停）。

**再把句子里的人名补成中文名**：`python scripts/zh_cite_names.py <stem>_zh.md --apply`。判据只有一条——**这个名字在句子里有没有职务**：有（主语、宾语、定语、"用……的话说"）就译，写成 `斯蒂德曼（Steedman, 1977: ch. 6）`；没有、只是标出处，纯括号照抄原文 `（Marx 1992: 534）`，**一个字都不动**。脚本只做前者（`--brackets` 是给普及本留的例外开关，默认关）。规则全文见 [references/translation-rules.md](references/translation-rules.md) 规则 4「学者姓名：句中留中文，括号附原名」。译名从 `verified_names.csv` 取，查不到不猜、列进 `_work/<stem>_人名待补.md`，补表后重跑（幂等）。

**再确认一遍成品是干净的**：`python scripts/strip_meta.py <stem>_zh.md --check` 应该返回 0（没有可剔的块）；残留 `©`、`doi.org`、`JEL`、`关键词`、`作者简介` 说明第 1 步漏跑了。成品的样子是：**标题 → 作者行 → 摘要 → 正文 → 附录 → 参考文献**，没有别的。

产物清单、YAML 元信息（著录信息全在这里：卷期页码、DOI、版权、关键词、JEL、资助）、发布口径的完整清单与归档、对话回复内容，见 [references/delivery.md](references/delivery.md)。

**不要在正文末尾追加"译者说明""术语对照表""译后记"**，除非用户明确要求——它们会让译文与原文结构不再一一对应。

### 可选：编译 PDF 版（页底脚注）

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex \
    --source-pdf paper.pdf --fig-meta _work/图片版式.csv --pdf --zotero
python scripts/verify_pdf.py _work/pdf/paper.pdf --tex _work/pdf/paper.tex \
    --md <stem>_zh.md --footnotes _work/脚注.csv
```

编译完自动复制一份到译稿旁边，名字是 `<stem>_zh.pdf`（`_work/pdf/paper.pdf` 只是中间产物）；`--zotero` 会接着把这份挂回库，见第 7 步。

**首页只放中文标题、英文原题、作者**，一条横线之后就是正文——不加「文献类型／原文题目／原文作者／DOI」那张表，正文开头的 H1 与作者行也会跳过（首页已经排过，正文里再来一遍就是重复）。`dl-translation` 那边保留信息表，两边口径不同。

默认 `--footnotes footnote`：`[^n]` 渲染成页底 `\footnote{}`，脚注格式保留在 PDF 里；要尾注用 `--footnotes endnote`。`verify_pdf.py` 查编译 `!` 错误、`Overfull \vbox`、图片数、书签、文本层汉字与连字，逐条核 `脚注.csv` 的内容是否进了 PDF（中文对照从译稿的 `[^n]:` 定义取，`脚注.csv` 的 zh 列空着也能核），并**正面确认日志里出现了 `Output written`**——XeTeX 的内部错误只进 stdout、不写 `.log`，只看 `!` 行会把"编到第 11 页就死了"判成通过（实测过）。与 `dl-translation` 同一份实现，踩过的坑见 [references/pdf-latex.md](references/pdf-latex.md)。

### 可选：公众号版

`python scripts/build_wechat.py <stem>_zh.md <输出目录>` 出可直接粘贴的排版稿（**去标题、去作者行**、去参考文献、脚注改就地引用框、正文保留上标、表格压进 637px、**公式渲染成内联 SVG**）。公式这条路只有在浏览器里才走得通——微信过滤 `<script>`，`$…$` 粘过去就是字面美元符；脚本把公式留成占位符，把 MathJax 内联进 HTML，打开页面时渲染，复制按钮取渲染后的 DOM。六条结构约束（`fontCache:none`、不靠 `transform`、尺寸写 `style`、**块级公式必须 `<p>` 内嵌行内 svg** 否则微信前后加空行）与两个已知限制（二次编辑易丢公式、公式多时 Chrome 粘贴可能卡）见 [references/wechat.md](references/wechat.md)。**白名单与内联样式**——`<style>`/class 会被编辑器整段删掉，所以样式必须写在 `style=""` 里、单位必须 px；粘贴方法与两道自检见 [references/wechat.md](references/wechat.md)。

## 第 7 步：回挂 Zotero（有 PDF 时）

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md --detect   # 先查来源，只读
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md           # 单篇挂回
python scripts/zotero_attach.py --batch . --strict                        # 多篇交付门禁
```

走 **Zotero 本地 API**（`127.0.0.1:23119`），不碰 `sqlite`、不需要账号：读（锚定、判重）不需授权；写第一次弹窗点 **Always Allow**，key 存 `~/.workbuddy/zotero.json`。**先 `--detect` 再挂**：它只读，报告「在库／不在库／歧义／查不了」、条目 key 与标题、判定依据、原文附件名，退出码 0/2/3；Zotero 没开时明说"查不了"，不会假装库里没有。锚定顺序：`--parent-key` → DOI/arXiv → `source_pdf` 与附件文件名匹配 → 英文标题相似度（≥0.85 且唯一）；**中文标题不参与匹配**，**front matter 里不存 source_file／source_pdf，全靠 DOI 与标题反查**。状态六种 `attached`/`updated`/`unchanged`/`ambiguous`/`pending`/`error`，退出码 0/1/2/3，**`--strict` 把任何没挂上的都算失败**（交付门禁用这个）。写不进去时不要手工复制：脚本在 `_zotero/` 产出 `pending.md` 与 `attach.js`（粘进 Zotero「工具 → 开发者 → 运行 JavaScript」一次挂完）。判重用 filename+md5，改稿重出直接重跑即原地覆盖；附件命名 `zh - <原文附件名>.pdf`，标题与文件名一致。详见 [references/zotero.md](references/zotero.md)。
</workflow>

<scripts>
| 脚本 | 用途 | 关键参数 |
|---|---|---|
| `scripts/mineru_extract.py` | PDF/图片/Office → Markdown | `--set-token`、`--token-status`、`--pages`、`--ocr`、`--model` |
| `scripts/split_refs.py` | 把参考文献区换成一行标记（不进上下文），交付前原样拼回 | `--check`、`-o`、`--restore`、`--heading` |
| `scripts/footnote_recover.py` | 从 `content_list.json` 恢复页底脚注；`--apply` 把 `[^n]` 锚进正文、定义落文末、迁移旧稿、中文回填、交叉验证与内容级门禁；判不出位置的进 `脚注_待锚.csv`（与 dl 同一实现） | `-o`、`--source`、`--target`、`--apply`、`--place`、`--anchor-bare`、`--anchor-math`、`--translations`、`--check`、`--pdf`、`--pdf-out`、`--skip-footnote-check` |
| `scripts/footnotes.py` | 兼容入口：把旧参数转发给 `footnote_recover.py`；不再作为主流程 | 旧参数 |
| `scripts/figure_layout.py` | 多联图合并成一行、按原刊占比定宽、子图标签归并；产 `图片版式.csv`（与 dl 同一实现） | `<extract>`、`--md`、`-o`、`--apply` |
| `scripts/md2tex.py` | 译稿 → XeLaTeX／PDF；`[^n]` 默认页底真脚注，URL 走 `\url{}`，图宽按 `--fig-meta`、图号按原刊编号，跨进程锁；编译完把 PDF 复制成 `<stem>_zh.pdf` 并按需挂 Zotero | `--pdf`、`--footnotes`、`--fig-meta`、`--source-pdf`、`--title-en`、`--zotero`、`--zotero-dry-run` |
| `scripts/verify_pdf.py` | PDF 验收：编译错误、`Overfull`、图片数、书签、文本层、逐条核脚注 | `<PDF>`、`--tex`、`--md`、`--footnotes` |
| `scripts/build_wechat.py` | 译稿 → 公众号排版稿；脚注归一、挂到所注段落后、样式与内容双自检 | `<译稿.md>` `<输出目录>` |
| `scripts/_test_footnotes.py` | 公众号脚注层的回归测试（13 种写法 + 1 条必须报警的失败用例） | 无 |
| `scripts/_test_marx_quotes.py` | 引号体例与引用体例的回归测试（英式单引号、MEGA 式引用串、撇号、去重） | 无 |
| `scripts/_test_md2tex_head.py` | 「标题下这一行是不是作者名」的回归测试：该删的作者行删掉，中文摘要首句不能被误删 | 无 |
| `scripts/extract_terms.py` | 挖候选术语，标注已收录/新增，可生成项目表模板 | `--glossary`、`--min-count`、`--top`、`--write-project` |
| `scripts/mine_terms_from_pairs.py` | 有平行译文时从「原文—译稿」句对反推实际用过的译法 | `--auto`、`--pairs`、`--min-count`、`--known` |
| `scripts/lookup_term.py` | 按词查项目表与总表，避免整份读入 | `--glossary`、`--exact` |
| `scripts/filter_terms.py` | 剔除通用词与噪声，按证据强度分主表与待核 | `--names`、`--min-docs`、`--keep-more` |
| `scripts/zh_quotes.py` | ASCII 引号 → 中文引号，跳过 front matter／参考文献／公式／代码 | `--inplace`、`--check`、`--all` |
| `scripts/zh_cite_names.py` | 句中人名补中文名：`Steedman（1977）` → `斯蒂德曼（Steedman, 1977）`；纯括号引用 `（Marx 1992: 534）` 默认不动。译名只从 `verified_names.csv` 取，查不到列清单不猜 | `--apply`、`--brackets`、`--glossary`、`--report` |
| `scripts/style_check.py` | 扫口语化痕迹，按句列出可疑处，不自动改 | `-o`、`--max`、`--style` |
| `scripts/semantic_audit.py` | 按段比对数值：年份、小数、百分比、千分位、页码区间 | `-o` |
| `scripts/marx_quotes.py` | 把马恩引文对到《文集》译文，带卷次/章/页与可信度；认双/单引号两种引号体例与 MEGA 式引用串 | `--source`、`--target`、`--marxref`、`--years`、`--map`、`--anchor` |
| `scripts/marx_adopt.py` | 把裁好的引文译文（采用表）转成 `review_apply.py` 的决定表 | `--quotes`、`--adopt`、`--target` |
| `scripts/review_queue.py` | 生成待校对清单：术语不一致、候选、人工判断项、马恩引文 | `--glossary`、`--manual`、`--init-manual`、`--marx`、`--marx-note` |
| `scripts/review_apply.py` | 执行人的意见：改术语表与译文、重跑校验、登记已决、重生成清单 | `--decisions`、`--resolved`、`--manifest`、`--suggest` |
| `scripts/paper_meta.py` | 生成、写入、检查译文顶部的 YAML 元信息 | `--init`、`--inject`、`--check` |
| `scripts/zotero_attach.py` | 把已验收的译文 PDF 挂回 Zotero 父条目（本地 API，filename+md5 判重，不碰 sqlite）；`--detect` 只报来源 | `<PDF>`、`--md`、`--detect`、`--batch`、`--strict`、`--parent-key`、`--title`、`--doi`、`--attach-title`、`--prepare-only`、`--dry-run`、`--stage` |
| `scripts/normalize_math.py` | 统一 `\[…\]`→`$$…$$`、`\(…\)`→`$…$`，跳过代码块与 `\\[2pt]` | `--inplace`、`-o`、`--check` |
| `scripts/fidelity_check.py` | 与原文对账：结构、引用、公式、未译段、术语；硬查脚注「正文 `[^n]` + 文末 `[^n]:`」双全、无 `## 脚注` 残留；`--strict-soft` 升级建议项 | `--glossary`、`--strict`、`--strict-soft`、`--skip-footnote-check` |
| `scripts/merge_glossary.py` | 合并多份术语表，做姓名规范化与权威译名裁决，输出四态分流 | `-o`、`--verified`、`--no-normalize` |
| `scripts/prune_glossary.py` | 按跨文献频次裁剪术语表，低频条目移入档案 | `--min-files`、`--keep-verified` |

全部只用 Python 标准库，无需安装依赖。唯一的外部依赖是 `_marx_ref`（马恩文集句级索引），可选：没有它，第 4 步的引文匹配跳过，其余照常。
</scripts>

<glossary_resources>
`references/glossary/` 下五份资源，可信度从高到低，不要混用：

| 文件 | 规模 | 作用 |
|---|---|---|
| `empirical_terms.csv` | 183 条 | **从已译文献反推的实证译法**，带出现次数与覆盖篇数；定译法的第一依据 |
| `verified_names.csv` | 240 条 | 有外部依据的权威译名（经典译本、新华社地名、通行音译），脚本自动套用 |
| `core_terms_draft.csv` | 134 条 | 政经核心概念，**待校对**；起步时逐条确认，把 `status` 改成 `已定` |
| `glossary_core.csv` | 1170 条 | 跨文献反复出现的专名，含 `tier` 与 `status`；按词查，不整份读 |
| `glossary_conflicts.csv` | 192 条 | 仍有多种译法、须人工裁决；首次使用前裁决高频项 |

`empirical_terms.csv` 与其余四份的区别在证据类型：其他是"通行译法"或人工判断，这一份是"你在自己译稿里实际用了什么"，每条都能追到原文与译文对得上的句子（覆盖 16 篇、8179 个句对），**只在政治经济学语料内有效**。它只收有分歧风险的词，`worker`/`price`/`data` 这类被显式剔除。

`glossary_core.csv` 是从 5404 条原始累积中裁出来的：只保留**在 ≥2 份文献里出现过**的条目与所有有权威译名的条目；被裁的 4234 条多为参考文献里的人名与出版地（参考文献整条保留原文，本就不需要译名）。裁剪可逆，`prune_glossary.py --min-files 1` 可复原。

`status` 四种取值：`已定`（有权威依据）、`一致`（唯一译法）、`待裁决`（多译法并存）、`待人工`（结构异常）。只有 `已定` 与 `一致` 可直接用。**频次推荐只反映过去几篇稿子碰巧怎么译，不构成正确性证据**——裸姓氏尤其可疑（`smith` 可能是 Adam Smith 或 Chris Smith），脚本不会替你选。

维护、扩充与从零积累的方法见 [references/terminology.md](references/terminology.md) 与 [references/terminology-growth.md](references/terminology-growth.md)。
</glossary_resources>

<fidelity_notes>
几条容易做错、且对账脚本抓不到的判断：

**原文错误不许静默修正。** 公式漏下标、数字前后矛盾、引用年份与文献表不符——照原样译，然后在报告里写明位置与判断。改了就变成"你的文章"而不是"译作"。

**提取缺陷不算原文。** 上下标压平、`O(n)` 读成 `0(n)`、连字符断词接错——凡与 PDF 目视不符，以 PDF 为准改正并记下改了哪几处。

**引文页码是引用的一部分。** `(Marx, 1867, p. 163)` 里的 `p. 163` 原样保留，不替换成译本页码。

**作者自造的术语保留原文。** 有通行译法的照译；学界无定译的，首次出现译后加原文括注，之后统一用中文——括注只在首次，不要每处都加。

**否定与量的范围。** `not all` 不是 `none`；`few` 不是 `some`；`tends to` 不是 `does`。政治经济学的论证常建立在这类量的差别上，译错一个词整段论证就反了。
</fidelity_notes>

<reference_files>
| 文件 | 何时读 |
|---|---|
| [references/translation-rules.md](references/translation-rules.md) | 动笔前；拿不准某处算不算增删、引用该如何处理时 |
| [references/semantic-review.md](references/semantic-review.md) | 第 4 步语义审读时；想知道"哪些类词表查不了、怎么读"时 |
| [references/refinement.md](references/refinement.md) | 要润色、要改已译稿；判断某处改动会不会改出新错时 |
| [references/style-sheet.md](references/style-sheet.md) | 第 3 步之前；定全篇语体约定、怀疑前后段行文不一致时 |
| [references/style/default.md](references/style/default.md) | 开新篇复制为项目文件；想改跨篇默认值（连续几篇都变了）时 |
| [references/figures.md](references/figures.md) | 图表归位、多联图并排、图片尺寸、发布口径基准 |
| [references/delivery.md](references/delivery.md) | 第 6 步；产物清单、元信息字段、发布稿删节、归档 |
| [references/wechat.md](references/wechat.md) | 出公众号版时；白名单约束、粘贴方法与自检 |
| [references/workflow.md](references/workflow.md) | 长文（>1 万字）、断点续译、批量多文件时 |
| [references/terminology.md](references/terminology.md) | 建立项目术语表、裁决争议译法、扩充总表时 |
| [references/terminology-growth.md](references/terminology-growth.md) | 想从零系统积累核心术语表、判断某个词该不该进表时 |
| [references/marx-ref.md](references/marx-ref.md) | 有马恩引文、要核对文集译文、判断匹配可信度时 |
| [references/mineru.md](references/mineru.md) | 需要从 PDF 提取、token 配置出问题、参考文献切分时 |
| [references/footnotes.md](references/footnotes.md) | 第 1 步脚注恢复；判断交叉验证结果、编号冲突、跨页续文时 |
| [references/pdf-latex.md](references/pdf-latex.md) | 用户要 PDF 时；编译、页底脚注、验收清单与排版坑 |
| [references/review-checklist.md](references/review-checklist.md) | 交付前 |
| [references/zotero.md](references/zotero.md) | 文献来自 Zotero、要把译文 PDF 挂回条目时 |
| [references/development.md](references/development.md) | 维护仓库、更新官方包、查许可与本地改动清单时 |
</reference_files>

<versioning>
## 版本与更新

本 skill 由 Git 管理。front matter 的 `version` 只作人读标识（`<官方基线日期>.<本地修订号>`）；**版本历史与变更记录一律以 `git log` / `git tag` 为准**，不在 skill 内维护 CHANGELOG、指纹或版本号脚本。

官方基线 `political-economy-translation_skill_2026-11-07.zip` 的更新方法（**不要整份覆盖**，用 `upstream` 分支 `git merge` 逐个人工合并）、tag 命名前缀、以及**相对基线的本地改动清单**，见 [references/development.md](references/development.md) 第三节。

若宿主 skills 目录用目录联接（Windows junction／Unix symlink）指向本仓库子目录，编辑即生效，无需双向同步。
</versioning>
