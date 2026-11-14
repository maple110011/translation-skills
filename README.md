# translation-skills

两个自建翻译 skill 的单一仓库：把英文政治经济学文献、深度学习／数学／统计论文译成中文 Markdown，并用脚本证明"没漏段、引用没改、公式与脚注没丢"。

仓库是唯一真相源，`~/.workbuddy/skills/` 下的同名目录是指向这里的 NTFS junction，编辑即生效、无需双向同步。

| skill | 用途 | 主文档 |
|---|---|---|
| `political-economy-translation` | 政经期刊论文／书章／书评英译中；术语与人名治理、马恩引文、公众号排版稿 | [SKILL.md](skills/political-economy-translation/SKILL.md) |
| `dl-translation` | 深度学习／数学／统计论文英译中；公式逐条对账、符号一览、图表重定位 | [SKILL.md](skills/dl-translation/SKILL.md) |

`scripts/footnote_recover.py`、`md2tex.py`、`verify_pdf.py`、`zotero_attach.py` 在两个 skill 里是**同一份实现**（MD5 一致）；改动要同步复制到另一边，别只改一边。

---

## 一、怎么用

**加载**（Windows，不需要管理员权限）：

```powershell
powershell -ExecutionPolicy Bypass -File tools\link.ps1
```

脚本把 `~/.workbuddy/skills/<name>` 原有目录改名备份到 `~/.workbuddy/<name>.pre-junction-backup`（放在 `skills/` 之外，避免被当成第二个 skill 扫描），再创建 junction 指向本仓库子目录。撤销用 `tools\unlink.ps1`；**备份目录确认无误前不要删**。

**调用**：在 WorkBuddy 里按 skill 名字发起翻译任务即可，也可以直接跑 `skills/<name>/scripts/` 下的脚本。动手前先读对应 `SKILL.md`——它规定了步骤顺序、硬门槛与交付物，不要跳步凭记忆往下写。

常用命令（在译文所在目录执行；`scripts/` 换成对应 skill 的路径，`<stem>` 是原文文件名）：

| 目的 | 命令 |
|---|---|
| PDF → Markdown | `python scripts/mineru_extract.py paper.pdf -o _work/extract --model vlm` |
| 恢复并补全脚注 | `python scripts/footnote_recover.py _work/extract -o _work --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf` |
| 回填中文脚注 | `python scripts/footnote_recover.py _work/extract -o _work --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check` |
| 结构对账 | `python scripts/fidelity_check.py <stem>_原文.md <stem>_zh.md --glossary _work/<stem>_术语.csv --float-reflow --strict` |
| 编译 PDF | `python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex --pdf` |
| PDF 验收 | `python scripts/verify_pdf.py _work/pdf/paper.pdf --md <stem>_zh.md --footnotes _work/脚注.csv` |
| 公众号版（政经） | `python scripts/build_wechat.py <stem>_zh.md <输出目录>` |
| 回挂 Zotero | `python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md` |

---

## 二、工作流

两个 skill 共用 0–6 步骨架，**每一步的产物是下一步的输入**：

| 步骤 | 做什么 | 硬门槛 |
|---|---|---|
| 0 | 确认源文件、交付格式、输出位置；顺口问一句要不要 PDF | — |
| 1 | 取到可译正文：MinerU 提取、抽查三页、**脚注恢复**、参考文献切分 | 脚注 `--check` 不 PASS 不许进第 2 步 |
| 2 | 动笔前锁定术语／专名（dl 侧还有符号一览与保留英文术语一览） | — |
| 3 | 逐段／分块翻译，段落一进一出、公式与标记原样保留 | — |
| 4 | 机械校验：公式定界符、公式逐条比对（dl）、结构对账、引用、脚注逐条核对 | `--strict` 失败必须修到清零 |
| 5 | 人工审校清单 → 决定表 → `review_apply.py` 一条龙回填并重跑校验 | 改不动或重跑失败都返回 1 |
| 6 | 拼回书目、写元信息、归档；按需出 PDF／公众号版，最后回挂 Zotero | 交付前四层脚注门禁、`verify_pdf.py` |

**脚注是两边完全统一的**：主源为 MinerU `content_list.json` 的 `page_footnote`（`full.md` 会整类丢掉），PDF 文字层只作交叉验证；`--apply` 给原文与译文两侧同步插 `## 脚注` 节，`[^n]` 是唯一交付形态；`fidelity_check.py`、`build_wechat.py`、`verify_pdf.py` 还会再验三遍。PDF 默认把 `[^n]` 排成页底 `\footnote{}`；若正文没有引用标记（不硬猜位置），脚本自动降级为文末编号段落，绝不静默丢内容。

**两条发布分支互不干扰**：`md2tex.py` + `verify_pdf.py` 出 PDF，`build_wechat.py` 出公众号稿，都以同一份译稿为源。文献来自 Zotero 时，用 `zotero_attach.py` 把**已验收**的 PDF 挂回原条目；零配置生成待挂副本与操作指引，配置 Web API key 后自动创建子附件。

**各自的侧重**：政经 skill 强在术语四态／人名权威层、参考文献 sha256 隔离、马恩引文、发布口径基准副本；`dl-translation` 强在公式逐条对账、符号表、浮动对象按首次引用重定位与 `--float-reflow` 位置无关核对。

---

## 三、注意事项

- **硬门槛不要跳过**：`--strict` 的失败、`footnote_recover.py --check` 的返回 1、`verify_pdf.py` 的 FAIL 都要修完再交付。报告"校验通过"时把各项结论写进交付说明，不要只写一句"通过"。
- **`--strict-soft` 默认不开**：疑似未译段、段长异常、术语一致等是建议性发现，误报多；需要零容忍时才加，别把"文档写硬规则、实现只报告"当成已拦住。
- **图表已按首次引用归位时，结构对账必须带 `--float-reflow`**，否则搬动过的图块会被误报成"块级结构不一致"。
- **Zotero 拖拽的临时路径会失效**：`C:\WINDOWS\TEMP\Zotero\drag\` 会被清空，原文 PDF 可能中途就不在。需要重跑提取时先用 `D:\临时\` 里的原件或工作区的 MinerU 提取稿，别依赖 drag 目录。回挂流程见两个 skill 的 `references/zotero.md`。
- **外部依赖**：MinerU token（`mineru_extract.py` 首次运行引导录入）、`pdftotext` / `pdfinfo` / `xelatex`（poppler + TeX Live，用于脚注交叉验证与 PDF）、`pyzotero`（仅自动上传 Zotero 附件时需要）、`_marx_ref/`（政经引文匹配，可选）。除这些之外脚本只用 Python 标准库。
- **junction 与备份**：普通复制/备份工具不一定跟随 junction，备份以本仓库为准；工作区目录移动或改名会让 junction 断，重跑 `tools\link.ps1` 即可；删除 junction 只删链接、不动仓库内容。
- **提交**：按逻辑块小步提交，别把两个 skill 的改动揉成一个 commit；tag 一律带 skill 名前缀（一个 tag 覆盖全部子目录）。
- **不入库的东西**：`.gitignore` 挡住 `*.pdf`、`*.zip`、`*.bak_*`、`_marx_ref/` 等；交付译文与 PDF 在工作区里，不在这个代码仓库。马恩原著文本与语料一律不入库，详见 [政经 skill 开发文档](skills/political-economy-translation/references/development.md)（官方包合并、索引脚本状态、许可与仓库边界也都在那里）。
- **许可未定**，公开前需核对 `names_xinhua.tsv.gz` 等第三方数据的来源与许可；定许可前请勿把本仓库设为 Public。
