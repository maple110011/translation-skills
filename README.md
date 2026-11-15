# translation-skills

> 两个面向 AI 编程助手的翻译 Skill：把英文政治经济学文献、深度学习／数学／统计论文译成中文 Markdown，并用可执行的校验证明「没漏段、引用没改、公式与脚注没丢」。

大模型翻译的通病不是读不懂英文，而是**读起来挺顺、逐字对不上**：公式差一个下标、定理弱化了条件、脚注整批消失、参考文献被顺手翻了。这些错误在中文里看不出破绽，等到要引用时才发现。

本仓库的做法是把「对不对」变成**可执行的检查**：每一步都产出可复核的文件，能机械比对的一律交给脚本，检查不过就返回非零。译文不是「模型说它译完了」，而是「对账跑完了」。

---

## 两个 Skill

| Skill | 译什么 | 强在哪 |
|---|---|---|
| [`dl-translation`](skills/dl-translation/SKILL.md) | 深度学习、机器学习、数学、统计论文 | 公式逐字符比对、符号一览、定理条件与强度、浮动对象按首次引用重定位 |
| [`political-economy-translation`](skills/political-economy-translation/SKILL.md) | 政治经济学期刊论文、书章、书评 | 术语四态与人名权威层、马恩引文对到文集译文、参考文献 sha256 隔离、公众号排版稿 |

两者共用同一套骨架（0–7 步）与同一份底层实现（脚注恢复、PDF 编译、PDF 验收、文献库回挂），差异在领域规则。

---

## 何时用 / 什么时候别用

**用（满足任一即可）**

- 论文、预印本、书章、书评的英译中，译文要长期查阅或供人审阅
- 正文含公式推导、定理—证明、算法伪代码、实验表格，要求逐字保真
- 要求术语全文一致、关键术语保留英文原文、脚注一条不丢
- 交付物需要是可验收的东西：Markdown、排版 PDF、公众号稿，或回挂到文献库
- 想复核一份已有译文「到底漏没漏」

**别用**

- 中译英——全部对账逻辑假定「源为英文、目标为中文」
- 文学、思想史、时评——那类文本的重点是语气与脉络，与「公式优先」的取舍相反
- 只要摘要或要点——直接摘要，不必走这套流程
- 纯排版工程（复刻作者的 `.tex` 工程、修编译错误）——本仓库只把**已定稿的中文 Markdown** 编成 PDF

---

## 设计原则

1. **产物驱动。** 每一步产出确定的文件，下一步只吃这些文件。中间件留在 `_work/`，交付物留在稿件根目录。
2. **能机械查的不靠人读。** 结构块数、引用条数、公式字符、脚注编号、数值、图表位置、PDF 文本层——全部脚本比对；人只判断语义与风格。
3. **不过就不交付。** `--strict` 失败、脚注 `--check` 返回 1、`verify_pdf` FAIL，都汇进退出码，不允许「打印警告然后继续」。

---

## 工作流

两个 Skill 共用 0–7 步，**每一步的产物是下一步的输入**：

| 步骤 | 做什么 | 硬门槛 |
|---|---|---|
| 0 | 确认源文件、交付格式、输出位置；问一句要不要 PDF | — |
| 1 | 取到可译正文：MinerU 提取、抽查三页、**脚注恢复**、参考文献切分 | 脚注 `--check` 不 PASS 不许进第 2 步 |
| 2 | 动笔前锁定术语／专名（dl 侧还有符号一览与保留英文术语一览） | — |
| 3 | 逐段／分块翻译，段落一进一出，公式与标记原样保留 | — |
| 4 | 机械校验：公式定界符、公式逐条比对、结构对账、引用、脚注逐条核对 | `--strict` 失败必须修到清零 |
| 5 | 人工审校清单 → 决定表 → 一条龙回填并重跑校验 | 改不动或重跑失败都返回 1 |
| 6 | 拼回书目、写元信息、归档；按需出 PDF／公众号稿 | 交付前四层脚注门禁、`verify_pdf.py` |
| 7 | 把已验收的译文 PDF 挂回文献库（Zotero）父条目 | 六种状态与退出码，`--strict` 可做交付门禁 |

脚注是两边完全统一的：主源为 MinerU `content_list.json` 的 `page_footnote`（`full.md` 会整类丢掉），PDF 文字层只作交叉验证；`[^n]` 是唯一交付形态，`fidelity_check.py`、`build_wechat.py`、`verify_pdf.py` 会再验三遍。PDF 默认排成页底真脚注；正文没有引用标记时自动降级为文末编号段落，绝不静默丢内容。

---

## 安装

两种方式，按你需要选：

**A. 作为 Skill 使用。** 把 `skills/<name>/` 整个目录复制到你所用宿主的 skills 目录，重启会话即可按名字调用：

| 宿主 | 目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/` |
| Claude Code 等读取 `SKILL.md` 的工具 | 各自的 skills 目录 |

Windows 下如果希望「改仓库即生效」而不复制，可用 `tools/link.ps1` 建目录联接（junction）指向仓库子目录，撤销用 `tools/unlink.ps1`。这是便利脚本，不是必需步骤。

**B. 只用脚本。** 不装 Skill 也能直接跑，脚本只依赖 Python 标准库：

```bash
python skills/dl-translation/scripts/fidelity_check.py --help
```

---

## 快速开始

以一篇深度学习论文为例（在译文目录下执行）：

```bash
S=skills/dl-translation/scripts          # Windows: set S=skills\dl-translation\scripts

# 1. PDF → Markdown（首次要 MinerU token）
python $S/mineru_extract.py paper.pdf -o _work/extract --model vlm

# 2. 恢复脚注，原文与译文两侧同步补 ## 脚注 节
python $S/footnote_recover.py _work/extract -o _work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

# 3. 结构、引用、公式、脚注一起对账
python $S/fidelity_check.py <stem>_原文.md <stem>_zh.md --strict
python $S/math_fidelity.py <stem>_原文.md <stem>_zh.md --strict

# 4. 编译 PDF 并验收
python $S/md2tex.py <stem>_zh.md _work/pdf/paper.tex --pdf
python $S/verify_pdf.py _work/pdf/paper.pdf --md <stem>_zh.md --footnotes _work/脚注.csv

# 5. 回挂文献库（可选）
python $S/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md
```

政经侧把 `$S` 换成 `skills/political-economy-translation/scripts`，并在第 1 步前用 `split_refs.py` 把参考文献切出去。

---

## 文件结构

```
translation-skills/
├── README.md                     # 本文件：是什么、怎么用
├── MAP.md                        # 维护者地图：改一件事该动哪个文件
├── LICENSE
├── docs/                         # 决策存档：为什么这么做（只增不改）
│   ├── README.md
│   └── 2026-11-zotero回挂流程重设.md
├── skills/
│   ├── dl-translation/
│   │   ├── SKILL.md              # 流程、硬门槛、交付物
│   │   ├── references/           # 细则：准确性规则、符号、图表、PDF、文献库…
│   │   │   └── glossary/         # 术语数据（ML/DL、数学、统计）
│   │   └── scripts/              # 16 个脚本，纯标准库
│   └── political-economy-translation/
│       ├── SKILL.md
│       ├── references/           # 细则：五条硬规则、术语、风格、马恩引文…
│       │   ├── style/            # 默认风格总表
│       │   └── glossary/         # 术语与权威人名数据
│       └── scripts/              # 24 个脚本，纯标准库
├── tools/
│   ├── link.ps1 / unlink.ps1     # Windows 目录联接（可选便利脚本）
│   └── marxref-build/            # 马恩文集句级索引构建（实验性）
```

两层文档各管一段：**`SKILL.md` 说按什么顺序做、什么算通过**；**`references/` 说这条规则具体怎么判**。`docs/` 只记取舍与证据，不写操作手册。

---

## 校验能抓到什么

| 脚本 | 查什么 | 抓不到什么 |
|---|---|---|
| `fidelity_check.py` | 正文块一一对应、标题层级、引用原样、定理环境、未译段、术语一致、正文卫生、脚注逐条 | 译错但结构正确的句子 |
| `math_fidelity.py` | 公式数量、逐字一致、`\tag` 编号、`$` 配对 | 数学上等价但改了写法的公式 |
| `notation.py` | 符号表与正文是否互相覆盖 | 符号含义译错 |
| `figures.py` | 图注数、图号、就近性、正文引用、文件存在 | 图内容译错（位图） |
| `semantic_audit.py` | 年份、小数、百分比、千分位、页码区间 | 非数值的事实错误 |
| `verify_pdf.py` | 编译错误、`Overfull \vbox`、图片数、书签、文本层汉字、脚注是否进 PDF | 版面美观 |
| `zotero_attach.py` | 父条目是否锚对、附件是否已是最新、上传后 md5 是否一致 | 译文质量 |

**机械校验通过 ≠ 译文无误**：审校清单（`references/review-checklist.md`）单独列了必须人读的部分。

---

## 依赖

| 依赖 | 必需？ | 用途 |
|---|---|---|
| Python 3.9+ | 是 | 全部脚本，**只用标准库** |
| MinerU token | 提取时必需 | PDF／图片 → Markdown；`mineru_extract.py --set-token` 录入 |
| poppler（`pdftotext`／`pdfinfo`） | 脚注交叉验证、PDF 验收时需要 | 读 PDF 文字层 |
| TeX Live（`xelatex` + ctex） | 出 PDF 时需要 | 中文排版编译 |
| Zotero 10+ | 回挂文献库时需要 | 本地 API 读写；没有 Zotero 时该步自动降级 |
| 马恩文集语料 `_marx_ref/` | 可选 | 政经 skill 的引文匹配；没有它其余步骤照常 |

不需要 `pyzotero`，不需要任何云服务账号。

---

## 文档在哪

| 想看 | 去 |
|---|---|
| 怎么用、有哪些坑 | 本文件 |
| 改代码：动哪个文件、哪些必须两边同改 | [MAP.md](MAP.md) |
| 某个 skill 的细则 | `skills/<name>/references/README.md`（索引） |
| 为什么这样设计、否掉了什么 | [docs/README.md](docs/README.md) |
| 某个脚本怎么调 | `python skills/<name>/scripts/<script>.py --help` |

---

## 状态与边界

**已可用**：脚注恢复链路、结构与公式对账、PDF 编译与验收、文献库回挂、公众号排版。

**实验性**：`tools/marxref-build/`（马恩文集索引构建），脚本仍在迭代，不保证输出稳定。

**不在本仓库**：任何原文与译文、生成的 PDF、马恩原著文本与语料（`_marx_ref/`）、个人文献库数据。译文与产物属于使用者自己的稿子，仓库只放方法与代码。

---

## 隐私

- 脚本不出网，唯一的外部调用是 MinerU 提取（可跳过，直接喂已提取的 Markdown）。
- 文献库回挂走 Zotero 本地 API（`127.0.0.1`），不经过 zotero.org，不需要账号；**不读写 `zotero.sqlite`**。
- 术语表与译名数据都在本地，不含个人身份信息。

---

## 许可

代码以 **MIT** 发布，见 [LICENSE](LICENSE)。

例外：`skills/*/references/glossary/` 下的部分数据来自第三方（如新华社译名库 `names_xinhua.tsv.gz`），其来源与许可需单独核对，不自动适用 MIT；马恩原著文本与语料一律不入库。二次分发前请逐项确认。
