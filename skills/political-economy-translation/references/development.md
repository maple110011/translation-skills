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

本 skill 的基线是 `political-economy-translation_skill_2026-11-07.zip`，当前本地版 `2026-11-17.1`（见 `SKILL.md` front matter 与 `<versioning>` 节）。版本管理文件（`version.json` / `CHANGELOG.md` / `scripts/skill_version.py`）已移到工作区 `_skill_版本管理_精简前备份/`，现在靠 Git 管理；`SKILL.md` 的版本号可能滞后于实际改动，以提交历史为准。

拿到新官方包时**不要整份覆盖**：解压到临时目录，用
`git diff --no-index <解压目录> skills/political-economy-translation/` 看差异；两边都改过的文件要人工逐段合并，本地新增文件一律保留。更彻底的做法是另开 `upstream` 分支只存官方原版，`git merge upstream` 让 Git 直接报冲突。

合并完打 tag（一个仓库的 tag 覆盖全部子目录，所以一律带 skill 名前缀）：

```bash
git tag political-economy/v2026-11-07.2
git tag dl/v1
```

单 skill 历史用 `git log --oneline -- skills/<name>/` 看。

### 相对官方基线的本地改动（合并 upstream 时重点看这几处）

- 新增 `scripts/footnotes.py`、`references/footnotes.md`；
- 改写 `SKILL.md`、`references/mineru.md`、`references/review-checklist.md`；
- 重写 `scripts/build_wechat.py` 的脚注层：`[^n]` / `<sup>n</sup>` / `## 脚注` 节统一归一，新增 `audit_notes()` 硬校验，配 `scripts/_test_footnotes.py` 回归测试。旧版只认 `<sup>`，`footnotes.py --patch` 过的稿子会静默丢光脚注；
- **脚注改「就地锚定」**（2026-11-16）：`footnote_recover.py --apply` 不再插 `## 脚注` 节，改为把 `[^n]` 锚进正文、定义 `[^n]: …` 落文末且不带「第 N 页脚注 n：」前缀；旧稿自动迁移，判不出位置的进 `脚注_待锚.csv`（`--place` 回灌，`--anchor-bare` / `--anchor-math` 自动锚定）；`--check` 与两个 skill 的 `fidelity_check.py` 改为硬查「定义 + 正文引用」双向齐全、编号升序；`md2tex.py` 对「有定义没引用」默认 `exit 2`（`--allow-orphan-notes` 才降级）——之前正是这条静默降级把脚注排成了文末一节；
- **图片版式**（2026-11-17）：新增 `scripts/figure_layout.py`（按 `content_list.json` 的 bbox 合并多联图、按原刊栏宽占比定宽、图号跟随原刊编号），`md2tex --fig-meta` 消费它产出的 `图片版式.csv`；公众号分支补裸图渲染（`figures` 块，px 宽度，`inline-block` 并排）；
- **SKILL.md 精简**（2026-11-17）：流程细节下沉到 `references/`（`figures.md`、`delivery.md`、`wechat.md` 为本次新增），SKILL 只留流程、硬门槛与指向。

---

## 四、许可与仓库边界

代码以 MIT 发布（见仓库根 `LICENSE`）。例外是本 skill 内含 `references/glossary/names_xinhua.tsv.gz`（3.6 MB）等第三方数据，其来源与许可需单独核对，不自动适用 MIT；马恩原著文本与语料一律不入库。二次分发前请逐项确认。

`.gitignore` 已挡住 `_marx_ref/`、`*.pdf`、`*.zip`、`*.bak_*` 等二进制大文件；`names_xinhua.tsv.gz` 是 skill 自带数据依赖，保留跟踪。

不在本仓库内：`mathtranslations`（`libinyam/mathtranslations-skill` 的 clone，MIT，带 LICENSE/NOTICE）、`paper-xray`，以及顶层 12 个 `latex-*-audit` / `mathtranslation-*`（mathtranslations 仓库 `skills/` 子目录的逐字副本）。这些都是上游资产，留各自的 origin 便于 `git pull`，不要并进来。

---

## 五、维护约定

导航与「改哪里」的完整清单在仓库根 [MAP.md](../../../MAP.md)。这里只留与本 skill 特有数据相关的三条：

- 马恩原著文本、语料与 `_marx_ref/` 一律不入库；改动 `glossary/` 下的数据要能说明来源与许可。
- 共享实现（`footnote_recover.py`／`md2tex.py`／`verify_pdf.py`／`zotero_attach.py`）改动后同步复制到 `dl-translation`，并用 `md5sum` 核对。
- 仓库是唯一真相源：如果宿主的 skills 目录用目录联接（Windows junction／Unix symlink）指向本仓库子目录，编辑即生效；工作区移动或改名后重建联接即可，删除联接只删链接、不动仓库内容。
