# 术语：怎么定、怎么存、怎么查

术语不一致是译文里最容易积少成多的错误：第 2 页定"超额风险"，第 20 页写成"过度风险"，读者会以为是两个概念。解决办法只有一个——**动笔前定完，之后照表**。

---

## 1 裁决顺序：默认保留英文，译名要有依据

**默认动作是"不译"。** 前沿论文里大量概念没有通行中文译名，硬造一个中文词，读者既查不到原文也没法与英文文献、代码、检索结果对上。所以裁决顺序改成"有依据才译，没依据就保留"：

| 顺序 | 依据 | 动作 |
|---|---|---|
| 1 | **本项目术语表**已定 | 照表；同一篇里不许改 |
| 2 | **种子表** `status=已定` | 照译 |
| 3 | **权威通行译法**：《数学名词》、全国科学技术名词审定委员会、中文教材里稳定使用的定名 | 定译名，`note` 写依据 |
| 4 | **以上都没有**：自造概念、新架构、新指标、缩写、多译法并存、拿不准 | **保留英文原文**（`kind=keep`），不造词 |

`status=待裁决` 不再意味着"必须选一个中文词"：两种译法都通行且本篇找不到权威依据时，**默认 `keep`**，记进待校对清单让人确认即可。

被判定为 `keep` 的，通常就是这几类：`prior-data fitted networks`、`in-context learning`、`amortized inference`、`tabular foundation model`、`post-hoc localization`、`Transformer Neural Processes`，以及 `PFN`／`PPD`／`ICL`／`TabPFN` 这类缩写。仍要照译的是有稳定定名的通用词：`posterior predictive distribution` → 后验预测分布、`prior` → 先验、`KL divergence` → KL 散度、`consistency` → 相合性。

### 1.1 保留英文的写法

- **逐字符照抄**：大小写、连字符、单复数、缩写、斜体标记，与原文该处完全一致。原文写 `PFNs` 就写 `PFNs`，写 `prior-data fitted networks (PFNs)` 就整串照写。
- **首次出现照抄，不补中文简述**：`prior-data fitted networks (PFNs)` 就写这一串，后面不要接 `（在模拟数据上预训练…）`。中文简述只属于开头「保留英文术语一览」的简述列；正文里出现就是「增」，与规则 6 冲突，脚本会硬失败。旧版「首现可加一句简述」的许可已废止。
- **不中英混跳**：定了 `keep` 就全文保留英文，不许第 2 页英文、第 12 页冒出一个自造中文名。
- **标题、图注、表注、符号一览"含义"列**里的 `keep` 术语同样照抄；不要为了"看起来像中文标题"把专名改掉。
- **写进译文开头的「保留英文术语一览」**（`<!-- kept-terms:start -->` … `<!-- kept-terms:end -->`），列「英文原文｜中文简述（可空）｜出现范围」。它是新增元信息，对账脚本会先剥掉。

### 1.2 项目表里怎么登记

```csv
src,dst,alt,kind,status,note
prior-data fitted networks,@keep,先验数据拟合网络|先验数据拟合网,keep,已定,作者自造概念，中文文献无通行译名
in-context learning,@keep,上下文学习|语境学习,keep,已定,两种中文译法并存且均易与统计含义混淆
posterior predictive distribution,后验预测分布,,term,已定,种子表已定
```

- `dst=@keep` 是机器可读的"不译"标记，`lookup_term.py` 显示「保留英文原文（不译）」；
- `kind=keep` 让 `fidelity_check.py` 与 `review_queue.py` 跳过"疑似未译术语"，改做反向检查；
- `alt` 在 `keep` 条目里的语义变成**禁止出现的中文写法**（不是备选译法），用 `|` 分隔；
- `fidelity_check.py` 查两件事：英文串在译文正文里确实出现（否则＝漏了或误译），`alt` 里的中文写法没有出现（否则＝偷偷译了）。

---

## 2 学科分流：同一个词，两种译法

统计、数学、深度学习三个领域共用大量词汇，含义与译法并不一致。这些词必须看语境，不能一律套表：

| 英文 | 统计/数学 | 深度学习 | 判断依据 |
|---|---|---|---|
| consistency | 相合性 | 一致性 | 出现在估计量、渐近性语境 → 相合性 |
| robust | 稳健的 | 鲁棒的 | 稳健标准误、稳健估计 → 稳健；对抗攻击、分布偏移 → 鲁棒 |
| kernel | 核（核函数、核密度） | 卷积核 | 与"带宽、平滑参数"同现 → 核；与"步长、填充"同现 → 卷积核 |
| inference | 推断（统计推断） | 推理（模型推理、推理成本） | 与"置信、检验、渐近"同现 → 推断；与"延迟、吞吐、部署"同现 → 推理 |
| value | 值 | 价值（价值函数、价值网络） | 强化学习语境 → 价值 |
| bias | 偏差（估计的偏差） | 偏置（偏置项） | 与 variance 对照 → 偏差；与 weight 并列 → 偏置 |
| sample | 样本 | 采样（sample from） | 名词 → 样本；动词 → 采样 |
| power | 功效（检验的功效） | 算力（compute power 另说） | 假设检验语境 → 功效 |
| attention | — | 注意力 | |
| normal | 正态的 | 归一化的（normalize） | distribution → 正态；layer → 归一化 |
| regular | 正则的 | 正则化 | |
| generalization | 推广（数学） | 泛化 | 机器学习语境一律"泛化" |
| estimation | 估计 | 估计 | |
| training | 训练 | 训练 | |
| bound | 界 | 界 | |
| convergence | 收敛 | 收敛（训练收敛） | |

同一篇论文里若两个学科的词都出现（例如"用统计学习理论分析深度学习"），**按出现位置分流**，并在术语表里用两行记录，不要只留一行。

---

## 3 缩写与专名

- **两种首现格式，别混**：有通行译名的写成「中文（English, ABBR）」，例："随机梯度下降（stochastic gradient descent, SGD）"；`keep` 术语**只写英文原串**，例："in-context learning (ICL)"，不加中文简述括注。之后按各自那一种统一，不要三种混用。
- **不译的**：模型名（Transformer、ResNet、BERT、GPT）、数据集名（ImageNet、CIFAR-10）、软件（PyTorch、JAX）、算法名（Adam、AdamW）、评价指标（BLEU、FID），以及 §1 判为 `keep` 的全部关键术语。
- **半译的**：`large language model (LLM)` → 大语言模型（LLM）；`reinforcement learning from human feedback (RLHF)` → 基于人类反馈的强化学习（RLHF）。
- **缩写本身有歧义时保留英文**：`EM`（expectation-maximization 还是 embedding？）、`MLE`（极大似然还是最大似然估计量），看上下文，必要时在表里注明。
- **标题里的专名照抄**，不要为了"看起来像中文标题"把 ResNet 改成"残差网络"。

---

## 4 项目术语表的用法

```bash
# 从原文挖候选术语，标出已在表里的与新增的
python scripts/extract_terms.py 原文.md -o _work/ --glossary references/glossary --min-count 3

# 按词查（不要整份读进上下文）
python scripts/lookup_term.py "excess risk" "相合性" --glossary references/glossary/
```

术语表是**项目级**的：这篇定"超额风险"，下一篇可能定"过量风险"，不要跨项目套用。项目表只收本篇真正用到的 20–40 条，不要复制总表——表越长，越没人照着用。

三类词不要进表：通用词（`data`、`model`、`result`）、描述性短语（`end-to-end`、`state-of-the-art`）、只出现一次的临时说法。它们没有分歧空间，进表只会稀释注意力。

要进表的是**译法一换、读者会理解成另一个概念**的词：`identifiability` 可识别性、`sharp bound` 最优界、`oracle inequality` oracle 不等式、`double descent` 双下降，以及**决定保留英文的关键术语**（`prior-data fitted networks`、`in-context learning`）——后者不进表同样会漂移，只是漂移方向是"某处被顺手译成了中文"。

`extract_terms.py` 的输出多一列 `keep_default`：`status=new` 的候选一律标 `yes`，即"种子表里查不到既有译法 → 默认保留英文"。`--write-project` 生成的模板六列与项目表一致，新增术语预填 `dst=@keep, kind=keep, status=已定`；查到权威译名再改，不要留空——留空就会边译边定。

---

## 5 术语与符号是两套东西

- **术语表**管"词怎么译"（attention → 注意力）；
- **符号一览**管"记号是什么"（$\alpha$ → 学习率）。

两者会互相牵连：术语表里定 `learning rate → 学习率`，符号表里 $\eta$ 的含义就该写"学习率"，不能写"步长"。交付前对一遍：符号表"含义"列里出现的每个中文术语，都要能在术语表里找到同一写法；**若某个概念是 `keep` 条目，含义列直接写英文串**，不要替它造一个中文名（例如 $\pi$ 的含义写 `posterior predictive distribution (PPD)` 以外的自造译法就不合格）。

---

## 6 维护

种子表可以直接编辑（CSV，六列：`src,dst,alt,kind,status,note`）。新增条目时：

- `status` 填 `已定`（有权威依据）或 `待裁决`（多译法并存）；
- `alt` 写备选译法，用 `|` 分隔，供 `fidelity_check.py` 查异译；
- `note` 写一句为什么——半年后你会需要这句话。

`kind` 取 `term`／`abbr`／`name`／`keep`。标成 `name` 的条目在一致性检查里会被跳过（人名地名不该被译成中文）；标成 `keep` 的条目走独立的反向检查：英文串必须在正文出现，`alt` 里的中文写法必须不出现。新增 `keep` 条目时 `dst` 必须写 `@keep`（`lookup_term.py` 与 `extract_terms.py` 靠它识别），否则会被当成漏填的译名。
