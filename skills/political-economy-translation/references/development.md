# 开发 / 维护说明（political-economy-translation）

面向维护这个 skill 与仓库的人；正常翻译不需要读。仓库级的「是什么 / 怎么用 /
工作流 / 注意事项」见仓库根目录 `README.md`。

---

## 一、马恩原著文本与语料：不包含

**本仓库不包含任何马恩原著文本，仅包含索引构建脚本。**

- 不含《马克思恩格斯文集》（人民出版社 2009）中文译文、MECW 英文原文，也不含任何由原文衍生的 PDF、HTML、句级语料 `jsonl`、对齐表、页码映射或检索索引成品。工作区里的 `_marx_ref/`（约 919 MB）整份被 `.gitignore` 排除，从未提交。
- 与本 skill 的引文工具相关的只有**脚本代码**：`scripts/marx_quotes.py`（从英文文献找引文并对到文集译文）、`marx_adopt.py`（采用表转决定表）、`references/marx-ref.md`（方法说明），以及 `tools/marxref-build/` 下 27 个索引构建脚本（约 160 KB）。这些文件里没有一句原著原文，中文长串均为注释与算法说明。
- `_marx_ref/` 是 `marx_quotes.py` 的**可选依赖**，通过 `--marxref` 或环境变量 `MARX_REF` 指定；没有它，其余流程照常运行，只是跳过引文匹配。

不入库的三条理由：

1. **体积**：当前 919 MB（PDF 332 MB、分卷中间文件 332 MB、句级索引 jsonl 109 MB、HTML 88 MB）。GitHub 建议仓库 <1 GB、单文件 >100 MiB 会被阻断；Git 还会保留每一次历史版本，一旦 push 过想清除得重写历史。
2. **版权**：MECW 英文版多为 CC0，但《马克思恩格斯文集》（人民出版社 2009）的中文译文是受版权保护的整理成果，放进**公开**仓库有侵权风险。这条比体积更硬。
3. **职责**：语料是数据、不是代码，更新频率与发布节奏和 skill 完全不同，不该跟着 skill 一起打 tag。

若确实需要给语料做云端备份，按优先级：私有仓库 → 对象存储/网盘 → Git LFS/Release 附件；先解决授权，且**不要放进这个代码仓库**。更省事的做法是备份「索引构建脚本 + 语料版本号 + 来源清单 + 内容哈希」，运行时从本地重建——脚本部分已经这么做了。

`tools/marxref-build/` 的脚本虽不含原文，但其中 `fetch_*` / `index_mecw.py` 会在运行时抓取外部马恩文本；是否抓取及后续使用、分发的授权责任在使用者，本仓库既不提供也不代管语料。

---

## 二、索引构建脚本的状态（WIP）

`tools/marxref-build/` 是项目内的工作脚本，有待进一步优化：

- 覆盖不全：第 8、9 卷未进索引；第 10 卷配对率约 75%。
- 句级对齐约四分之一存在错位风险需人工核对（数字抽检 62.3% 完全一致；实测 9 条引文 6 条错位）。
- 参数与卷次映射硬编码、外部语料源未锁版本、无回归测试。

`mea{vol}.jsonl` 缺失时，引文匹配会退化为半句。详见 `tools/marxref-build/README.md`。

---

## 三、官方包更新

本 skill 的基线是 `political-economy-translation_skill_2026-11-07.zip`，当前本地版 `2026-11-07.2`（见 `SKILL.md` front matter 与 `<versioning>` 节）。版本管理文件（`version.json` / `CHANGELOG.md` / `scripts/skill_version.py`）已移到工作区 `_skill_版本管理_精简前备份/`，现在靠 Git 管理；`SKILL.md` 的版本号可能滞后于实际改动，以提交历史为准。

拿到新官方包时**不要整份覆盖**：解压到临时目录，用
`git diff --no-index <解压目录> skills/political-economy-translation/` 看差异；两边都改过的文件要人工逐段合并，本地新增文件一律保留。更彻底的做法是另开 `upstream` 分支只存官方原版，`git merge upstream` 让 Git 直接报冲突。

合并完打 tag（一个仓库的 tag 覆盖全部子目录，所以一律带 skill 名前缀）：

```bash
git tag political-economy/v2026-11-07.2
git tag dl/v1
```

单 skill 历史用 `git log --oneline -- skills/<name>/` 看。

---

## 四、许可与仓库边界

尚未选定许可。两个 skill 与 `tools/marxref-build/` 下的索引构建脚本都是自建代码，但本 skill 内含 `references/glossary/names_xinhua.tsv.gz`（3.6 MB）等第三方数据，公开前需逐项核来源与许可；马恩原著文本与语料一律不入库。**定许可前请勿把本仓库设为 Public。**

`.gitignore` 已挡住 `_marx_ref/`、`*.pdf`、`*.zip`、`*.bak_*` 等二进制大文件；`names_xinhua.tsv.gz` 是 skill 自带数据依赖，保留跟踪。

不在本仓库内：`mathtranslations`（`libinyam/mathtranslations-skill` 的 clone，MIT，带 LICENSE/NOTICE）、`paper-xray`，以及顶层 12 个 `latex-*-audit` / `mathtranslation-*`（mathtranslations 仓库 `skills/` 子目录的逐字副本）。这些都是上游资产，留各自的 origin 便于 `git pull`，不要并进来。

---

## 五、维护约定

- `scripts/footnote_recover.py`、`md2tex.py`、`verify_pdf.py`、`zotero_attach.py` 与 `dl-translation` 是**同一份实现**，改动后要同步复制到另一边，并在两个 SKILL.md 的脚本表里同步登记。
- 仓库是唯一真相源；`~/.workbuddy/skills/` 是 junction，普通复制/备份工具不一定跟随它，备份以本仓库为准。工作区目录若移动或改名，junction 会断，重跑 `tools/link.ps1` 即可；删除 junction 只删链接、不动仓库内容。
- 提交按逻辑块小步进行，别把多个 skill 的改动揉成一个 commit。
