# 交付：产物清单、元信息、发布口径与归档

这一步决定"交出去的东西长什么样"。三件事：把书目拼回去、把只属于原刊的内容删掉、把这一篇的收获并回总表。

## 一、先把书目拼回去

译文里那行标记只是占位，交付前必须换成原文著录：

```bash
python scripts/split_refs.py --restore _work/<stem>_正文_zh.md -o <stem>_zh.md
```

拼回时会核对参考文献文件与切分时是不是同一份（sha256 对不上就停），并检查标记在不在、是否只剩一处。标记丢了，脚本报出"应在原第几行插入"，手工补回再跑——**不要凭记忆把书目贴到别处**。标题想用中文加 `--heading 参考文献`：标题属于结构，可以译；条目是原文，一字不动。

## 二、产物清单

| 文件 | 内容 |
|---|---|
| `<stem>_zh.md` | 译文（书目已原样拼回），顶部带 YAML front matter，`normalize_math.py` 与 `fidelity_check.py` 都通过 |
| `_work/<stem>_切分.json` | 切点、书目行数与 sha256，`--restore` 靠它核对 |
| `_work/<stem>_风格.md` | 全篇语体约定与样板段，续译与改稿的基准 |
| `_work/<stem>_术语.csv` | 本项目定下的术语与专名 |
| `_work/<stem>_引文采用.csv` | 马恩引文的裁定结果：哪几句用文集译文、为什么（有引文时才有） |
| `_work/<stem>_待校对.md` | 审校清单：机械发现 + 人工判断项（含马恩引文核对） |
| `_work/<stem>_数字核对.md` | 数值比对结果（脚本产出，通常 0 处） |
| `_work/脚注.csv` / `脚注_原文.md` / `脚注_待译.csv` | 第 1 步恢复的脚注清单、英文原文与中文待译表；证明脚注没被整批丢掉。**页码只在这里，别写进译稿的定义行** |
| `_work/脚注_待锚.csv` | 脚本判不出正文位置的脚注（含区间提示）；填 `anchor` 后 `--apply --place` 回灌 |
| `_work/脚注_原刊信息.md` | 作者机构／版权注（与正文脚注同号但不占 `[^n]`），只备查，不进交付稿 |
| `_work/图片版式.csv` | 每张图的原刊栏宽占比与所属图组；`md2tex --fig-meta` 用它还原尺寸 |
| `_work/脚注_交叉验证.md` | PDF 文字层交叉验证结果（给 `--pdf` 时产出） |
| `<stem>_校对报告.txt` | `fidelity_check.py` 的原始输出 |
| `_work/<stem>_原文_发布口径.md` | 按发布版式重排过的源文基准（图表归位、元信息剔除后），供校验；**不改原文文件** |
| `<stem>_zh.pdf` / `_work/pdf/paper.tex` | 可选 PDF 版：页底真脚注，编译后必须跑 `verify_pdf.py` |
| `<stem>_公众号版.html` / `.md` | 可直接粘贴的排版稿（要公众号版时才出，见 [wechat.md](wechat.md)） |

## 三、译文顶部的元信息

```bash
python scripts/paper_meta.py --init paper_原文.md -o _work/meta.yaml   # 生成草稿
# 补齐 title_zh、authors、journal 等字段
python scripts/paper_meta.py --inject <stem>_zh.md --meta _work/meta.yaml
python scripts/paper_meta.py --check <stem>_zh.md                      # 查漏字段
```

字段分四组，各有各的用途：

| 组 | 字段 | 之后能用来做什么 |
|---|---|---|
| 身份 | `title`、`title_zh`、`authors`、`year`、`journal`、`volume/issue/pages`、`doi`、`type` | 建文献库、生成引用 |
| 著录 | `keywords`、`jel`、`notes` | 关键词与分类号；版权行、资助、ORCID 这类零碎，值得留就写成 `notes` 里一句话 |
| 过程 | `translated_at`、`translator`、`extraction` | 哪天译的、用什么提取的 |
| 质量 | `fidelity`（块数、段落数、引用数、公式数、`status`） | 按"真正通过校验"筛语料，而不是靠文件名 |

**只有这四组。** 早先还有 `copyright`、`school`、`language`、`orcid`、`funding`、`source_file`、`source_sha256`、`glossary`、`terms_used`、`review_open`、`draft` 十一个字段，已经全部去掉：`language` 永远是 `en`；`school` 只在一部分文章里有意义；哈希与源文件名随工作目录一起消失，换个盘就查不到；术语表路径与条目数在 `_work/` 里有原件；`review_open` 与 `draft` 是流程中间态，交付那一刻必然要清零。留着它们只会让 front matter 比正文还长，而真正被程序读回去的只有 `doi`、`title`、`authors` 这几项。

**`title` 常常要手改**：MinerU 的 H1 有一半时候是期刊名或文章类型（"Research Article"），不是论文标题。`authors` 也要人工填——脚本不去猜，猜错了比空着更麻烦。

**front matter 不算增删。** 规则 1 约束的是正文：段落与源文一一对应、不添加原文没有的内容。元信息是文件属性，标准 Markdown 渲染时不显示，所有对账脚本都会先剥掉它再比对（`fidelity_check.py`、`normalize_math.py`、`review_queue.py` 都实现了 `strip_frontmatter`）。但边界要守住：**只放元信息**，不许塞译者按语、内容摘要、术语对照表——那些放进 `_work/` 下的独立文件。

`--check` 只对 `title`／`title_zh`／`year`／`authors` 四个字段判空值——这四项空着，这份译文就没法被引用，其余字段允许留空。跑完 `--check` 顺带看一眼有没有旧字段残留（脚本会点出来），有的删掉即可。

## 四、发布稿口径：成品只留标题、作者、正文、附录

期刊 PDF 的正文前后有一批**只属于原刊、不属于译文**的内容。判据一句话：**读者需不需要它来判断这是一篇什么文章。** 标题与作者需要；卷期、版权、DOI、JEL 不需要——它们是引用信息，属于元数据。

| 要删的 | 去处 |
|---|---|
| 刊名、卷期页码、复用指引、刊物网址、出版社标记（`S Sage`） | `journal`／`volume`／`issue`／`pages`；正文里删掉 |
| 版权行（`© 2023 …`） | 删。要留档就并进 `notes` 一句话，不单设字段 |
| DOI | `doi` |
| 收稿／接受／在线发表日期 | `year` |
| JEL 分类、关键词 | `jel`／`keywords` |
| 致谢、作者说明、作者贡献 | 删（含学术性说明的进 `notes`） |
| 基金资助 | 删。要留档并进 `notes`，"无资助"不必写 |
| 利益冲突声明、伦理声明、数据可用性 | 删（数据地址、审批号进 `notes`） |
| ORCID iD | 删。要留档并进 `notes` |
| 文末作者简介 | 删（`authors` 只留姓名与单位） |
| 作者单位角标、通讯邮箱 | 删（**姓名保留**） |
| 参考文献前的"按体例保留原文，不译。共 N 条。" | 删——这是流程备注，不是文章的一部分 |

```bash
python scripts/strip_meta.py _work/<stem>_原文_正文.md --meta _work/meta.yaml --dump-yaml --check
python scripts/strip_meta.py _work/<stem>_原文_正文.md --meta _work/meta.yaml --apply
python scripts/strip_meta.py <stem>_zh.md --meta _work/meta.yaml --apply
```

**规范位置是第 1 步**（动笔之前）：源文工作副本先剔干净，译文从第一段起就不含这些块，对账基准天然对齐。**已经译完的老稿**照样能补跑，只是跑完要重跑 `fidelity_check.py`——块号会变，之前记在报告里的"第几段"全部作废。

**脚注要查断号**：正常情况机构／版权注在 `footnote_recover.py` 那一步就归到 `_work/脚注_原刊信息.md` 了，不占 `[^n]` 编号；只有当你手工删掉的是带编号的注释时，才需要重编号并跑 `--check` 确认没有悬空引用。

**删了正文，基准也要跟着删。** 两侧都跑 `strip_meta.py` 就自动一致；如果只删了译文、基准还是原样，`fidelity_check.py` 会立刻报块级结构不一致——**不要**为了过校验去改原文，也别另做一份"发布口径副本"绕过去，那是给同一个事实留两份记录。

标题与作者行在两条通道上处置不同，别混：**Markdown 交付稿两者都留**（读者拿到的是一篇署名文章）；**公众号推文 HTML 两者都不上版面**——微信有自己的标题字段，作者由「文献来源」那一行（APA 条目）与公众号主体承担，正文里再写一遍既重复又挤掉开头的信息位。`build_wechat.py` 的 `strip_lead()` 负责这两件事，`title`／`authors` 仍留在 front matter 里供生成 APA 条目。

**不要在正文末尾追加"译者说明""术语对照表""译后记"**，除非用户明确要求——它们会让译文与原文结构不再一一对应。作者的附录、数学附录、数据附录**要留**：那是文章的一部分，不是版尾声明。

## 五、归档：把这一篇的收获并回总表

```bash
python scripts/merge_glossary.py _work/<stem>_术语.csv -o _work/merge   # 并回总表，看新增冲突
```

术语有脚本，风格没有——**风格总表靠你一分钟的判断**。译完翻一遍 `_work/<stem>_风格.md` 里改过的项，问一句：这条是这篇的特例，还是我的偏好变了？

- 只有这篇因为作者用法特殊 → 留在项目文件，不上抬；
- 连续两三篇都这么改 → 并回 `references/style/default.md`，下次开篇复制到的就是新基线。

不并回，总表就永远停在旧值，每篇都得重改；单篇特例上抬，下一篇会被莫名其妙地约束。分寸在"连续两三篇"这个尺度上，不在单次。

只看报告里"待裁决"涨了多少：涨得多说明这个分支的译法还没收敛，该停下来定一次内部标准，而不是继续逐篇临时决定。若确认没有新冲突，把 `_work/merge/glossary_master.csv` 的条目并回 `references/glossary/glossary_core.csv`，下次翻译即可查到。

## 六、对话里怎么回复

只回复：译文绝对路径；校验结论（哪些通过、哪些需人工判断）；原文中有无疑点或提取缺陷；以及没做的部分（没有附录、公式是图片无法提取）；**Zotero 挂载状态**（`attached`／`updated`／`unchanged`／`pending（需你点授权）`）。不复述译文内容。
