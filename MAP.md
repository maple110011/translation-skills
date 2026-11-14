# 维护者地图

[README](README.md) 讲**怎么用**；这里只回答另一个问题：**要改某件事，动哪个文件。**

---

## 一、目录在管什么

| 路径 | 管什么 | 什么时候碰 |
|---|---|---|
| `README.md` | 面向使用者：装在哪、怎么跑、有哪些坑 | 用法、依赖、命令变了 |
| `MAP.md` | 本文件：维护者导航 | 增删文件、换职责时同步改 |
| `skills/<skill>/SKILL.md` | 该 skill 的**流程**：步骤顺序、硬门槛、交付物 | 改步骤、改门槛、登记新脚本 |
| `skills/<skill>/references/` | 细则与判例，按需查阅（索引见各目录 `README.md`） | 改规则细节、补踩坑记录 |
| `skills/<skill>/scripts/` | 全部可执行逻辑 | 改行为 |
| `docs/` | 设计决策存档：**为什么这么做**，只增不改 | 做过取舍、踩过坑，写一条 |
| `tools/` | junction 脚本、马恩索引构建工具 | 换机器、改索引 |

---

## 二、我要改……去哪

| 想改 | 位置 | 注意 |
|---|---|---|
| 某一步做什么、卡什么门槛 | `SKILL.md` 的 `<workflow>` 块 | 步骤写在 `<workflow>` **外面**等于没进流程，模型会跳过（政经的回挂 Zotero 就这样漏了三篇） |
| 交付要产出哪些文件 | `SKILL.md` 第 6／7 步的产出表 | 不在产出表里的东西，实际上没人做、也没人验收 |
| 术语裁决与译名 | `references/terminology.md`（规则）+ `references/glossary/*.csv`（数据） | 规则与数据分开，别在 CSV 里写判据 |
| 人名权威译名 | `references/glossary/names_xinhua.tsv.gz`、`verified_names.csv` | 新华社译名库，压缩入库 |
| 脚注链路 | `references/footnotes.md` + `scripts/footnote_recover.py` | 两边同一份实现 |
| PDF 版式（首页、符号表位置、公式分组） | `references/pdf-latex.md` + `scripts/md2tex.py` | 改版式要重编样例并跑 `verify_pdf.py` |
| PDF 验收口径 | `scripts/verify_pdf.py` + `SKILL.md` 第 6 步的验收段 | 加检查项要同时改文档，否则"文档说查、代码不查" |
| 回挂 Zotero | `references/zotero.md` + `scripts/zotero_attach.py` | 走本地 API，**绝不碰 `zotero.sqlite`** |
| MinerU 提取 | `references/mineru.md` + `scripts/mineru_extract.py` | 两份文案不同，口径必须一致 |
| 图表／浮动对象 | dl：`references/figures.md`；政经：`SKILL.md` 的「图表归位」一节 | 政经还没抽成独立文件，改一边时另一边也看一眼 |
| 符号一览 | `references/notation.md` + `scripts/notation.py` | dl 专有 |
| 马恩引文核对 | `references/marx-ref.md` + `scripts/marx_quotes.py` | 政经专有；依赖 `_marx_ref/`（可选） |
| 公众号排版 | 政经 `SKILL.md` 公众号章节 + `scripts/build_wechat.py` | 白名单只认内联样式，别改成 class |
| 加一个新脚本 | `scripts/` + **两处** SKILL.md 的脚本表 | 表里不登记，模型就不知道它存在 |
| 改一条判据 | 先翻 `docs/` 有没有记过为什么这么定 | 没记就补一条决策记录再改 |

---

## 三、两边必须同改的文件

这些是"同一份实现、两个副本"，只改一边会让另一个 skill 静默用旧逻辑：

| 文件 | 备注 |
|---|---|
| `scripts/footnote_recover.py` | 必须字节一致 |
| `scripts/md2tex.py` | 必须字节一致 |
| `scripts/verify_pdf.py` | 必须字节一致 |
| `scripts/zotero_attach.py` | 必须字节一致 |
| `references/zotero.md` | 必须字节一致 |
| `references/pdf-latex.md` | **内容有意不同**：政经版多一段"适用范围"，其余部分要同步 |

核对：

```bash
cd skills && md5sum */scripts/{footnote_recover,md2tex,verify_pdf,zotero_attach}.py */references/zotero.md
```

前四个与 `zotero.md` 应当两两相等；`pdf-latex.md` 不等是正常的。

---

## 四、文档分三层，别互相抄

| 层 | 位置 | 回答的问题 | 谁读 |
|---|---|---|---|
| 流程 | `SKILL.md` | 按什么顺序做、什么算通过 | 执行任务的模型 |
| 细则 | `references/*.md` | 这条规则具体怎么判、踩过什么坑 | 执行者 + 维护者 |
| 决策 | `docs/*.md` | 当初为什么这么定、否掉了什么 | 维护者 |

写的时候守住边界：

- `SKILL.md` 只留"做什么、卡什么"，判据细节下沉到 references，别在流程里铺判例。
- references 不复述步骤顺序；它假设读者已经读过 SKILL.md。
- docs 只记取舍与证据，不写操作手册；操作手册过期了没人改，决策记录过期了反而有史料价值。

---

## 五、五条容易踩的规矩

1. **步骤必须在 `<workflow>` 内**。写在块外就是附录：模型的执行清单里没有它。
2. **产出表是硬约束**。不在表里的文件不会被产出，也不会被验收。
3. **硬门槛要真的返回非零**。`--strict` 失败、`--check` 返回 1、`verify_pdf` FAIL，必须汇进退出码；只打印不返回等于没拦。
4. **共享脚本改一边等于改一半**。另一个 skill 会继续用旧逻辑，而且不会报错。
5. **提交按逻辑块小步走**，别把两个 skill 的改动揉成一个 commit；tag 带 skill 名前缀。
