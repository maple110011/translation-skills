# 术语与专名

术语不一致是译稿最容易被挑出的问题，也是最容易预防的。这份文档讲三件事：手上有哪些表、新词怎么定、定下来怎么维护。

---

## 一、三类条目，三种处理

政经文献里的人名、术语、学派名混在一起，但它们的处理方式完全不同。混在一张表里用，一定会出错。

| 类型 | 例子 | 处理 | 靠什么定 |
|---|---|---|---|
| **概念术语** | `surplus value` → 剩余价值 | 意译，全文统一，可加原文括注 | 学界通行译法、经典译本 |
| **专名（人名/地名/机构）** | `Shaikh` → 谢赫、`Cambridge, MA` → 剑桥（马萨诸塞州） | 音译，全文统一 | 新华社译名室、已有译稿、名从主人 |
| **学派/理论名** | `Sraffian` → 斯拉法的、`regulation school` → 调节学派 | 半译半留，看学界习惯 | 领域惯例 |

**同一个词在不同表里可能是不同角色。** `price` 作为概念是"价格"，作为人名是"普赖斯"。现有累积表里就有一条 `price → 普赖斯`，那是人名。查表时先看 `kind` 列，不要盲信。

---

## 二、内置资源

`references/glossary/` 下五份，可信度从高到低：

| 文件 | 规模 | 内容 | 用法 |
|---|---|---|---|
| `empirical_terms.csv` | 183 条 | **从已译文献反推的实证译法**，字段 `src,dst,tier,confidence,count,docs,note` | 定译法第一依据，只收有分歧风险的词 |
| `verified_names.csv` | 240 条 | 有外部依据的权威译名，字段 `src,dst,form,confidence,basis,alias` | 由脚本自动套用，也可人工查 |
| `core_terms_draft.csv` | 134 条 | 政经核心概念，字段 `src,dst,alt,confidence,topic,status` | 先通读确认，`status` 由"待校对"改"已定" |
| `glossary_core.csv` | 1170 条 | 跨文献反复出现的专名，字段 `src,dst,kind,tier,status,basis,n_files` | 按词查，不整份读 |
| `glossary_conflicts.csv` | 192 条 | 仍有多种译法、需人工裁决的条目 | 首次使用前裁决高频项 |

`empirical_terms.csv` 的证据类型与其他几份不同：其余是"通行译法"或人工判断，这一份是"你自己的译稿里实际怎么用的"，来自 16 篇已译文献、8179 个句对的句级对齐。`count` 是出现次数，`docs` 是覆盖篇数，两个都高的条目最可靠。

它的取舍标准值得知道：**通用词汇一律不收**。`worker`、`price`、`data`、`management`、`technology` 这些译法唯一，收进表只是让表变长、让真术语被稀释。保留的是 `agent`（主体／代理人）、`tension`（张力／紧张）、`realization`（实现／兑现）、`problematic`（问题式／有问题）这一类——换种写法读者会理解成另一个概念。

`core_terms_draft.csv` 的 `alt` 列是**常见异译**，不是"都可以"。定下 `dst` 之后，`alt` 里被否决的写法要删掉，否则下次又会被选回去。`confidence` 为 `medium` 表示学界未定于一，`high` 表示有通行定译。

### 状态怎么读

`glossary_core.csv` 的 `status` 只有四种取值：

| 状态 | 含义 | 能不能直接用 |
|---|---|---|
| `已定` | 有 `verified_names.csv` 的外部依据，`basis` 列写明来源 | 可以直接用 |
| `一致` | 全表只有这一个译法，没有竞争 | 可以用，但只是"没冲突"，未经佐证 |
| `待裁决` | 有多种译法并存 | 必须先选一个 |
| `待人工` | 结构异常，机器判断不了 | 人工看 |

`basis` 列说明依据来源：`verified:high`（经典译本或权威辞书）、`verified:medium`（通行音译，未见辞书）、`normalize`（规范化后唯一）、`freq`（仅频次）、`residual`（异常残留）。

### 姓名规范化做了什么

机器翻译会把同一个人写成 `马克思·K`、`K. 马克思`、`马克思, K.`、`Marx K`。中文正文里只需要姓，所以合并表前会统一剥掉拉丁缩写：`弗利, D. K.` → `弗利`、`H.D. 库尔茨` → `库尔茨`、`邓肯·K.福利` → `邓肯·福利`。

这一步把 1047 处写法归一，也**消解了 143 条本不存在的"冲突"**（原先算 339 条冲突，规范化后剩 196 条，权威裁决后剩 192 条）。

注意：全名条目会保留名字。`Karl Marx` → `卡尔·马克思`，而 `Marx, K.` → `马克思`。两者是不同的行，不要合并。

### 几个已解决的高频坑

| 原文 | 旧推荐 | 现用 | 依据 |
|---|---|---|---|
| `smith, a.` / `Adam Smith` | 史密斯 | **斯密 / 亚当·斯密** | 古典政治经济学通行译名 |
| `foley` / `Foley, D. K.` | 福利 | **弗利** | 通行音译，避免与 welfare 混读 |
| `leontief` | 列昂惕夫 | 列昂惕夫 | 已锁定，里昂惕夫为异写 |
| `marx k` | 马克思·K | **马克思** | 规范化剥离缩写 |

裸姓氏 `smith` 仍标 `待裁决`——它可能指 Adam Smith，也可能是 Chris Smith。这类歧义不应当由脚本替你决定。

`tier` 列区分 `core`（≥3 份文献出现，或有经典译本依据）与 `common`（2 份文献）。表外还有一份 4234 条的档案（`_整理结果/glossary_archive.csv`），多为只在一篇文献里出现的参考文献人名，按需可回查。

### 查词

```bash
python scripts/lookup_term.py "surplus value" "Shaikh" "organic composition"
python scripts/lookup_term.py 剩余价值            # 反向查
python scripts/lookup_term.py Shaikh --exact
python scripts/lookup_term.py "value" --max 20 --all
```

输出会标出 `=` 精确、`~` 模糊，并在同一原文有多种译法时警告。查不到时返回码 1——这不是错误，是提醒"该你自己定了"。

---

## 三、新词怎么定

按这个顺序，前一条能解决就不用下一条：

1. **本文所属传统的经典译本。** 马克思主义 → 《资本论》人民出版社译本、《马恩全集》；斯拉法 → 《用商品生产商品》商务印书馆译本；劳动过程理论 → 布雷弗曼《劳动与垄断资本》。
2. **近五年中文核心期刊的通行译法。** 查《政治经济学评论》《马克思主义与现实》《国外理论动态》等。用词频而非单篇。
3. **相邻学科的习惯。** `precarity` 在社会学里多作"不稳定性"，劳动研究里有时作" precarious 状态"，取前者。
4. **构词法直译 + 原文括注。** 前三条都没有时，按词素直译，首次出现加原文。
5. **音译（仅专名）。** 按新华社《世界人名翻译大辞典》与《世界地名翻译大辞典》；无收录时按音节对应表。

### 音译的三条规矩

- **名从主人。** 作者自己用过汉字名（如已发表中文论文署名"谢克"），从其用法。
- **约定俗成优先于音准。** `Marx` 是"马克思"不是"马克斯"，`Keynes` 是"凯恩斯"不是"凯因斯"。
- **同名不同人可能不同译。** `Smith` 在经济学史里通常是"斯密"，在社会学里可能是"史密斯"。看语境，不要机械替换。

### 复合术语的处理

- 有既定译法的整体照译：`organic composition of capital` → 资本有机构成（不是"资本的组织构成"）。
- 修饰语 + 核心词：核心词按表，修饰语按语义。`relative surplus population` → 相对过剩人口。
- 作者自造词：首次译后加原文括注，之后统一中文。括注只加一次。

---

## 四、项目术语表

每篇文献建一份，放在 `_work/<stem>_术语.csv`：

```csv
src,dst,note
surplus value,剩余价值,
labour power,劳动力,不用“劳动能力”，全文统一
Shaikh,谢赫,Anwar Shaikh；不取“沙伊赫”
organic composition of capital,资本有机构成,
tendentially,在趋势上,不可译作“实际上”
```

`note` 列写**为什么这样定**和**排除了什么**。三个月后回头看，理由比结论有用。

### 抽取候选术语的做法

不要通读找词——四十页会漏，而且慢。用脚本数：

```bash
python scripts/extract_terms.py paper_原文.md -o _work/ \
    --glossary references/glossary --min-count 3 --write-project _work/paper_术语.csv
```

它抓五类信号，也正是人工该盯的五类：

1. 反复出现的名词短语（`count` 列；单次出现的不算术语）。
2. 带引号或斜体的词（`signals` 含 `quoted` / `italic`，作者在强调）。
3. `the X of Y` 结构（`signals` 含 `the_of`；`the law of the tendency of...` 这类几乎全是术语）。
4. 形态标记：`-ism`、`-ization`、`-ation`、`-tion`、`-ness`、`-ity`（`signals` 含 `suffix`）。
5. 首字母大写的专名（`type=name`，用于和已有专名表比对，不是为了翻译）。

脚本会自动排除含 `and`/`or` 的并列短语、含 be 动词的从句、以及被更长短语包含的片段（`production` 之于 `production function`），并把复数并入单数。

产物 `_work/paper_原文_候选术语.csv` 的 `status` 列区分 `known`（表里已有）与 `new`（待定）。给 `new` 的填 `dst`，写成项目表。**不要边译边定**——译到第三页时你已经忘了第一页怎么定的。

### 候选表要先瘦身

挖出来的名单里七成是通用词和共现噪声。直接用它定译法，真正的术语会被淹没在 `worker → 工人` 这类条目里。

```bash
python scripts/filter_terms.py _work/paper_原文_候选术语.csv -o _work/filtered \
    --names references/glossary/verified_names.csv --min-docs 1
```

**单篇翻译必须加 `--min-docs 1`**：`extract_terms.py` 的候选表只有一篇文献，默认 `--min-docs 3` 会把整张表判成"证据不足"塞进待核区。只有挖矿表（`mine_terms_from_pairs.py` 的产物，带 `dst` 列、跨十几篇文献）才用默认值——篇数在那里才有区分度。

判定原则只有一条：**换一种译法会不会改变论证，或让读者误解成另一个概念。**

| 保留 | 理由 |
|---|---|
| `agent` 主体（非代理人） | 行为主体与代理人是两回事 |
| `tension` 张力（非紧张） | 作者指结构张力，不是情绪 |
| `realization` 实现（非兑现） | 价值实现的固定用法 |
| `problematic` 问题式（非有问题） | 阿尔都塞术语，译错整段读不通 |
| `commodity production` 商品生产 | 与 `petty commodity production` 小商品生产必须区分 |

| 剔除 | 理由 |
|---|---|
| `worker` `price` `data` `management` `technology` | 译法唯一，无分歧空间 |
| `model` `content` `activity` `type` `outcome` | 通用词，不承载论证 |
| `economic outcome` `open question` `growth rate` | 日常词拼成，不是术语 |
| `mathbf x` `doi org ntwe` `kellogg et al` | 提取残留 |

脚本输出三份：`术语表.csv`（主表，出现在 ≥3 篇文献或 ≥15 次）、`待核候选.csv`（证据不足）、`剔除清单.csv`（每条带剔除原因，可审计）。**不要删剔除清单**——判断对不对，半年后靠它复核。

主表的 `dst_mined` 列记的是挖矿原始值，`dst` 是修正后的值。两者不同说明有过度修正，值得回看。

---

## 五、合并与裁决

一批文献译完后，把项目表并进总表：

```bash
# 只合并
python scripts/merge_glossary.py ./_work/*_术语.csv -o ./merged

# 合并 + 姓名规范化 + 套用权威译名
python scripts/merge_glossary.py ./_work -o ./merged --verified references/glossary/verified_names.csv
```

脚本做四件事，顺序不能颠倒：

1. **规范化**（在聚合之前）：剥掉译名里的拉丁缩写，脏字符修复。必须在聚合前做，否则同一人的不同写法会被当成不同实体，凭空造出冲突。
2. **聚合**：按归一化键（小写、去尾点、去首冠词）合并同一实体，统计各译法的频次。
3. **裁决**：命中 `verified_names.csv` 的，用权威值覆盖频次推荐，并记进 `glossary_overrides.csv`（谁被改了、原来是什么、依据是什么，全部可审）。
4. **分流**：输出 `已定` / `一致` / `待裁决` / `待人工` 四类。

产物：

| 文件 | 内容 |
|---|---|
| `glossary_master.csv` | 合并后的完整表，含 `status` 与 `basis` |
| `glossary_core.csv` | 裁剪后的常用表（`prune_glossary.py` 产物） |
| `glossary_conflicts.csv` | 仅 `待裁决` |
| `glossary_overrides.csv` | 权威值推翻频次推荐的每一处，用于复核 |
| `glossary_review.md` | 人读版，带 ☐ 勾选框 |
| `merge_report.txt` | 统计 |

**推荐值不是正确答案。** 频次只反映过去某几篇稿子碰巧怎么译。有依据的已被权威表覆盖，剩下的必须人工裁决。

**加新的权威译名**：往 `verified_names.csv` 追加一行即可，下次合并自动生效。字段 `src` 写规范的"姓 + 首字母"形式（如 `marx k.`），`alias` 用 `|` 分隔其他写法，`form` 取 `surname`/`full`/`place`。全名与姓氏要分成两行——`Karl Marx` 译"卡尔·马克思"，`Marx, K.` 译"马克思"，不是同一个条目。

### 裁剪：只留会再用到的

合并完的表会越来越胖，但胖不等于有用。机器抓的术语表有个系统性偏差：它把**参考文献里的人名**也抓进来了，而按规则 4，参考文献整条保留原文——作者、出版社、出版地都不译，这些名字根本不需要译名。

裁剪判据是**跨文献出现数**，不是出现次数。术语表按篇生成，一条只出现在一篇文献里的记录，说明此后从未被复用过；一条出现在五篇里的，说明五篇译本都需要它。这才是"常用"的实际形态。

```bash
python scripts/prune_glossary.py merged/glossary_master.csv -o pruned/ --min-files 2
```

产出 `glossary_core.csv`（保留，带 `tier` 列）与 `glossary_archive.csv`（移出，可回查）。阈值 2 保留约 22%，阈值 3 约 11%。**不要删档案**——某个专题重新开始时，被裁掉的生僻人名可能要捞回来。

`--keep-verified` 默认开启：有权威译名的条目无论频次都保留，因为它可能在下一篇里就是主角。

---

## 六、维护

- 总表只增不改：改译法时新增一行并注明替代关系，保留历史，便于追溯旧稿。
- 每次裁决冲突，把结论写回 `dst`，把被否决的写法从 `alt` 删掉。
- `core_terms_draft.csv` 的 `status` 只有两个值：`待校对`、`已定`。翻译时只采用 `已定` 的条目。
- 表超过万行后按主题拆分（价值理论 / 劳动过程 / 金融化 / 世界体系），避免单表过大。

**怎么从零积累核心术语表，见 [terminology-growth.md](terminology-growth.md)。** 那篇讲的是收录门槛、分层结构、以及为什么"攒得多"不等于"攒得对"。
