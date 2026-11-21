# translation-skills

面向学术文献翻译的 Agent Skill 集合与配套校验脚本，适用于 WorkBuddy、Claude Code 等支持 `SKILL.md` 规范的工具，脚本也可脱离 Agent 独立运行。

项目核心思路是**用脚本接管机械核对**：结构、公式、脚注、引用和版式由 Python 脚本校验，通过后再进入人工审校或编译交付。仓库只包含方法、规则与脚本，不包含任何论文原文、译文或马恩原著语料。

## 包含的 Skill

| Skill | 适用领域 | 输入格式 | 特色流程与规则 | 输出格式 |
| --- | --- | --- | --- | --- |
| [dl-translation](skills/dl-translation/SKILL.md) | 深度学习、机器学习、数学、统计学论文 | arXiv 源码、PDF、Markdown、docx | arXiv 源码优先；公式逐字符校验；文首附「符号一览」与「保留英文术语一览」；机械校验后执行流畅化改写（[fluency.md](skills/dl-translation/references/fluency.md)） | 中文 Markdown、PDF |
| [political-economy-translation](skills/political-economy-translation/SKILL.md) | 政治经济学期刊论文、书章、书评、讲义（价值理论、斯拉法/剩余方法、劳动过程、金融化、全球价值链等） | PDF、Markdown | 脚注强制恢复；参考文献隔离；内置新华译名库与核心术语表；全篇风格锚校验；机械校验后执行精校轮与语义审读（[refinement.md](skills/political-economy-translation/references/refinement.md)、[semantic-review.md](skills/political-economy-translation/references/semantic-review.md)）；可选马恩引文核对 | 中文 Markdown、PDF、微信公众号排版稿 |

两个 Skill 共用同一套基础链路（脚注恢复、XeLaTeX 编译与验收、Zotero 本地回挂），且共享脚本在两处保持同步。

## 安装

### 方式一：作为 Skill 安装（推荐）

将 `skills/<name>/` 整个目录复制到对应宿主的 skills 目录，重启会话即可按名称调用：

- **WorkBuddy**：`~/.workbuddy/skills/`
- **Claude Code 等其他宿主**：对应工具的 skills 目录

Windows 用户如希望修改仓库后直接生效，可运行目录联接脚本（会自动将已有同名目录备份到 `skills/` 外部）：

```powershell
# 建立目录联接（NTFS Junction）
.\tools\link.ps1

# 撤销联接
.\tools\unlink.ps1
```

### 方式二：仅运行校验与排版脚本

所有脚本仅依赖 Python 标准库，无需安装 Skill 或第三方 Python 包：

```bash
python skills/dl-translation/scripts/fidelity_check.py --help
```

## 快速开始

以下以一篇深度学习论文为例，在译文工作目录中执行：

```bash
S=skills/dl-translation/scripts        # Windows: set S=skills\dl-translation\scripts

# 1. 取源：有 arXiv 版本直接拉取作者源码；无源码时改用 MinerU 提取 PDF
python $S/arxiv_src.py 2207.01848 -o _work/arxiv
# python $S/mineru_extract.py paper.pdf -o _work/extract --model vlm

# 2. 恢复脚注（原文与译文两侧同步补全 ## 脚注 节）
python $S/footnote_recover.py _work/extract -o _work \
  --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

# 3. 校验结构、引用、公式与脚注
python $S/fidelity_check.py <stem>_原文.md <stem>_zh.md --strict
python $S/math_fidelity.py <stem>_原文.md <stem>_zh.md --strict

# 4. 编译中文 PDF 并验收
python $S/md2tex.py <stem>_zh.md _work/pdf/paper.tex --pdf
python $S/verify_pdf.py _work/pdf/paper.pdf --md <stem>_zh.md --footnotes _work/脚注.csv

# 5. 回挂到 Zotero 文献库（可选）
python $S/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md
```

翻译政治经济学文献时，将 `$S` 替换为 `skills/political-economy-translation/scripts`，并在第 1 步前先运行 `split_refs.py` 隔离参考文献；如需输出公众号排版稿，可使用 `build_wechat.py`。

## 工作流概览

两个 Skill 的完整步骤均为 0–7 步，核心差异集中在取源、词表/符号锁定、校验后精修及交付格式：

1. **确认源与交付（Step 0）**：确定输入文件与目标产物；多篇文献支持按篇拆分子代理并行处理。
2. **获取可译正文（Step 1）**：剥离刊头、致谢与声明至 YAML front matter，图表按首次提及归位，参考文献保持英文原样。DL 优先拉取 arXiv 源码；政经强制检查并恢复 PDF 脚注。
3. **锁定术语与符号（Step 2）**：翻译前先检索本地词表（DL：`ml_dl_core` / `math_core` / `stat_core`；政经：`glossary_core` / `empirical_terms` / `verified_names` / `names_xinhua.tsv.gz`），DL 同步建立符号表骨架。
4. **分段翻译（Step 3）**：按原文结构逐段输出；政经遵循全篇风格锚（`references/style/default.md` 与篇级 `_work/<stem>_风格.md`）。
5. **机械校验与精修（Step 4 / 4.5）**：先跑 `fidelity_check.py`、`math_fidelity.py`、`style_check.py` 等脚本过门禁；通过后 DL 执行流畅化改写（只调语序断句、不改信息），政经执行精校轮与语义审读（`semantic_audit.py`）。
6. **审校清单与回填（Step 5）**：生成待确认项清单（`review_queue.py`），确认后批量回填（`review_apply.py`）。
7. **编译交付与 Zotero 回挂（Step 6–7）**：按需用 `md2tex.py` + `verify_pdf.py` 编译并验收 PDF（政经可选 `build_wechat.py`），最后通过 `zotero_attach.py` 经本地 API 回挂到 Zotero。

## 环境依赖

不需要 `pyzotero`，不需要任何云服务账号。

| 依赖 | 是否必需 | 用途 |
| --- | --- | --- |
| Python 3.9+ | 必需 | 运行全部脚本（仅用标准库） |
| 联网访问 arXiv | 仅拉取 arXiv 源码时 | 直接下载作者 LaTeX，免去 PDF 提取误差 |
| MinerU token | 仅从 PDF/图片提取时 | PDF 转 Markdown，通过 `mineru_extract.py --set-token` 录入 |
| poppler（`pdftotext` / `pdfinfo`） | 脚注交叉验证与 PDF 验收时 | 读取 PDF 文字层 |
| TeX Live（`xelatex` + `ctex`） | 编译 PDF 时 | 中文排版编译 |
| Zotero 10+ | 回挂文献库时 | 通过本地 API 挂载附件，未安装时自动跳过 |
| `_marx_ref/` 本地语料 | 可选 | 政经 Skill 的马恩引文匹配，缺失不影响其余步骤 |

## 目录结构与文档导航

```text
translation-skills/
├── MAP.md                                # 维护者导航：文件职责、修改入口与双端同步清单
├── docs/                                 # 设计决策存档（只增不改，如 Zotero 本地 API 迁移记录）
├── skills/
│   ├── dl-translation/                   # 深度学习 / 数学 / 统计论文翻译 Skill
│   │   ├── SKILL.md                      # 流程、硬规则与脚本入口
│   │   ├── references/                   # 规则细则与领域词表（glossary/）
│   │   └── scripts/                      # 19 个提取、校验与编译脚本
│   └── political-economy-translation/    # 政治经济学文献翻译 Skill
│       ├── SKILL.md                      # 流程、硬规则与脚本入口
│       ├── references/                   # 规则细则、风格总表（style/）与词表/译名库（glossary/）
│       └── scripts/                      # 提取、校验、语义审读、公众号构建与测试脚本
└── tools/
    ├── link.ps1 / unlink.ps1             # Windows 目录联接安装与撤销脚本
    └── marxref-build/                    # [实验性] 马恩引文索引自建脚本（不含原著文本）
```

- 查阅完整规则与脚本入口：[dl-translation/SKILL.md](skills/dl-translation/SKILL.md)、[political-economy-translation/SKILL.md](skills/political-economy-translation/SKILL.md)
- 查阅细则索引：[dl-translation/references/README.md](skills/dl-translation/references/README.md)、[political-economy-translation/references/README.md](skills/political-economy-translation/references/README.md)
- 参与维护或修改共享脚本：[`MAP.md`](MAP.md)
- 自建马恩引文索引：[tools/marxref-build/README.md](tools/marxref-build/README.md)

## 状态、隐私与许可

- **当前状态**：脚注恢复、结构与公式对账、PDF 编译验收、Zotero 本地回挂和公众号排版均已可用；`tools/marxref-build/` 为实验性工具，仍在迭代中。
- **隐私与网络**：脚本默认离线运行，仅在拉取 arXiv 源码或调用 MinerU 提取时联网（如已有本地 Markdown/LaTeX 可完全离线）。Zotero 回挂仅访问本机 `127.0.0.1` 本地 API，不经过 `zotero.org`，也绝不直接读写 `zotero.sqlite`。
- **许可**：本仓库代码按 [MIT License](LICENSE) 发布。`skills/*/references/glossary/` 下部分第三方数据（如新华社译名库 `names_xinhua.tsv.gz`）不自动适用 MIT，二次分发前请单独核对来源与授权。
