# translation-skills

两个原创翻译 skill 的单一仓库。仓库是唯一真相源，`~/.workbuddy/skills/` 下对应目录通过 NTFS 目录联接（junction）指向这里，编辑即提交，无需双向同步。

```
translation-skills/
├── skills/
│   ├── political-economy-translation/   政经文献英译中（40 个文件）
│   └── ml-math-stats-translation/       ML / 数学 / 统计论文英译中（23 个文件）
├── tools/
│   ├── link.ps1        把本地 skill 目录切换为指向本仓库的 junction（可逆）
│   ├── unlink.ps1      撤销 junction，恢复切换前的本地目录
│   └── marxref-build/  马恩引文索引构建脚本（27 个 .py，纯代码，见该目录 README）
├── .gitattributes
├── .gitignore
└── README.md
```

## 关于马恩原著文本：不包含

**本仓库不包含任何马恩原著文本，仅包含索引构建脚本。**

- 不含《马克思恩格斯文集》（人民出版社 2009）中文译文、MECW 英文原文，也不含任何由原文衍生的 PDF、HTML、句级语料 `jsonl`、对齐表、页码映射或检索索引成品。工作区里的 `_marx_ref/`（约 919 MB）整份被 `.gitignore` 排除，从未提交。
- 与马恩引文工具相关的只有**脚本代码**：`skills/political-economy-translation/scripts/marx_quotes.py`（从英文文献找引文并对到文集译文）、`marx_adopt.py`（采用表转决定表）、`references/marx-ref.md`（方法说明），以及 `tools/marxref-build/` 下 27 个索引构建脚本（约 160 KB）。这些文件里没有一句原著原文，中文长串均为注释与算法说明。
- **这套索引构建脚本是项目内的工作脚本，有待进一步优化**：覆盖不全（第 8、9 卷未进索引）、句级对齐约四分之一存在错位风险需人工核对、参数与卷次映射硬编码、外部语料源未锁版本、无回归测试。详见 [`tools/marxref-build/README.md`](tools/marxref-build/README.md)。

因此本仓库体积始终在几 MB 量级，不存在马恩语料把仓库撑到 GitHub 上限的问题；后续优化脚本也只增加代码、不增加语料。

不在本仓库内：`mathtranslations`（`libinyam/mathtranslations-skill` 的 clone，MIT，带 LICENSE/NOTICE）、`paper-xray`（`Wang-auspicious/paper-xray` 的 clone），以及顶层 12 个 `latex-*-audit` / `mathtranslation-*`（它们是 mathtranslations 仓库 `skills/` 子目录的逐字副本）。这些都是上游资产，留各自的 origin 便于 `git pull`，不要并进来。

## 本地加载

```powershell
powershell -ExecutionPolicy Bypass -File tools\link.ps1
```

脚本把 `~/.workbuddy/skills/<name>` 里的原目录改名备份到 `~/.workbuddy/<name>.pre-junction-backup`（放在 `skills/` 之外，避免被当成新 skill 扫描），再创建 junction 指向本仓库的子目录。跨盘（C: → E:）已实测可用，创建 junction 不需要管理员权限。

撤销：

```powershell
powershell -ExecutionPolicy Bypass -File tools\unlink.ps1
```

删除 junction 只删链接、不动仓库内容，再把备份目录改回原名。**备份目录确认无误前不要删**。注意：普通复制/备份工具不一定跟随 junction，备份要以本仓库为准；工作区目录若移动或改名，junction 会断，重跑 `link.ps1` 即可。

## 外部数据：马恩语料不入库

`political-economy-translation` 的 `scripts/marx_quotes.py` 可以把英文文献里的马恩直接引语对到《马克思恩格斯文集》的中文译文。它消费的是工作区里的 `_marx_ref/`（引擎 + 句级语料），通过 `--marxref` 或环境变量 `MARX_REF` 指定，**是可选依赖**：没有它，其余流程照常运行，只是跳过引文匹配。

`_marx_ref/` **不进本仓库**，理由有三：

1. **体积**：当前 919 MB（PDF 332 MB、分卷中间文件 332 MB、句级索引 jsonl 109 MB、HTML 88 MB）。GitHub 建议仓库 <1 GB、"强烈建议 <5 GB"，单文件 >100 MiB 会被直接阻断。919 MB 已经贴着建议线，而且 Git 会保留**每一次历史版本**——加卷次、加索引、做新版本快照，仓库只会单调膨胀；一旦 push 过，想清除得用 `git filter-repo` 重写历史。GitHub 官方文档也直说 Git 不是备份工具。
2. **版权**：MECW 英文版多为 CC0，但《马克思恩格斯文集》（人民出版社 2009）的中文译文是受版权保护的整理成果。把中译全文放进**公开**仓库有侵权风险；这条比体积更硬。
3. **职责**：语料是数据、不是代码，更新频率和发布节奏与 skill 完全不同，也不该跟着 skill 一起打 tag。

仓库里只有**索引构建脚本**（`tools/marxref-build/`）与调用脚本、说明文档，没有一行原著文本——见开头「关于马恩原著文本：不包含」。若确实需要给语料做云端备份，按优先级考虑：私有仓库 → 对象存储 / 网盘 → Git LFS / Release 附件；但先解决授权，且**不要放进这个代码仓库**。更省事的做法是备份「索引构建脚本 + 语料版本号 + 来源清单 + 内容哈希」，运行时从本地重建——脚本部分已经这么做了。

`.gitignore` 里已挡住 `_marx_ref/`、`*.pdf`、`*.zip` 等二进制大文件。`skills/political-economy-translation/references/glossary/names_xinhua.tsv.gz`（3.6 MB）是 skill 自带的数据依赖，保留跟踪；其来源与许可待核后在许可文件里注明。

## 官方包更新

`political-economy-translation` 的基线是 `political-economy-translation_skill_2026-11-07.zip`，当前本地版 `2026-11-07.2`（见该 skill 的 `SKILL.md` front matter 与 `<versioning>` 节）。

拿到新官方包时**不要整份覆盖**：把新 zip 解压到临时目录，用 `git diff --no-index <解压目录> skills/political-economy-translation/` 看差异；两边都改过的文件（当前是 `SKILL.md`、`references/mineru.md`、`references/review-checklist.md`）要人工逐段合并，本地新增的 `scripts/footnotes.py`、`references/footnotes.md` 一律保留。更彻底的做法是另开 `upstream` 分支只存官方原版，`git merge upstream` 让 Git 直接报冲突。合并完打 tag：

```bash
git tag political-economy/v2026-11-07.2
git tag ml-math-stats/v1
```

一个仓库的 tag 覆盖全部子目录，所以 tag 一律带 skill 名前缀；单 skill 历史用 `git log --oneline -- skills/<name>/` 看。

## 许可

尚未选定。两个 skill 与 `tools/marxref-build/` 下的索引构建脚本都是自建代码，但 `political-economy-translation` 内含 `names_xinhua.tsv.gz` 等第三方数据，公开前需逐项核来源与许可；马恩原著文本与语料（见上）一律不入库。定许可前请勿把本仓库设为 Public。

`tools/marxref-build/` 的脚本虽不含原文，但其中 `fetch_*` / `index_mecw.py` 会在运行时抓取外部马恩文本，是否抓取及后续使用、分发的授权责任在使用者；本仓库既不提供也不代管语料。
