# 脚注：从 MinerU 提取包恢复，补到译文 Markdown 与 PDF

这一节讲 `scripts/footnote_recover.py` 为什么存在、怎么判定、哪些事它不做。
`political-economy-translation` 与 `dl-translation` 共用**同一份脚本实现**，
下文路径按各 skill 自己的 `scripts/` 理解。

---

## 一、为什么抽查和块级对账都挡不住

MinerU（vlm 尤其）把期刊页底的脚注当成版面噪声：正文里的上标标记留下，脚注正文整批不写。实测 Kapeller et al. (2026, *Review of Political Economy*, 45 页)：

| 项目 | PDF | MinerU `full.md` |
|---|---|---|
| 页底脚注 | 17 条（1–17，连续） | 0 条 |
| 正文标记 | 17 个 | 13 个 `<sup>n</sup>` |
| 变形标记 | — | 2 个塞进行内公式（`^ { 7 }`、`^ { 8 }`），2 个退化成句末裸数字 |
| 跨页续文 | 脚注 6 前半在页 7 页底、后半在页 8 页底 | 无 |

**关键在于 `fidelity_check.py` 对此完全免疫**：它比的是译文与源文的块序列，两边都缺这 17 段，块数照样一一对应。抽查三页也挡不住——抽到的那页可能恰好有脚注，也可能没有。

---

## 二、主源是 `content_list.json`，PDF 文字层只作交叉验证

2026-11-14 的实证结论：MinerU 的版面识别**认得出**脚注——`*_content_list.json`（`type=page_footnote`，含 `page_idx` / `bbox` / 完整 `text`）、`content_list_v2.json`、`layout.json` 三处条数一致；**只有服务端生成 `full.md` 时按类型白名单把 `page_footnote` 整类过滤**。所以不需要重新 OCR、不需要装 PDF 库、不需要换 `--model`。

旧流程（`scripts/footnotes.py`）从 `pdftotext -layout` 按「页底编号 + 缩进」抓脚注，在单栏期刊上有效，但**双栏期刊的脚注排在栏底而不是页底**，缩进特征会变，可能整条漏检。因此现在：

- **主源**：`content_list.json` 的 `page_footnote`，准确、带页码、带原文；
- **交叉验证**：`--pdf paper.pdf`（或 `--text` 传已导出文字层），只用来发现「提取包被污染」「跨页续文被截断」「文字层不可读」，产出 `_work/脚注_交叉验证.md`；
- 交叉验证**未确认不等于提取包有错**，不覆盖主源结果，也不作为硬失败。

脚本按 `text` 分类：

| 类别 | 判据 | 处理 |
|---|---|---|
| `footnote` | 有数字编号、正文 ≥30 字 | 要译成中文，占 `[^n]` 编号 |
| `affiliation` | 含 University / Department / Copyright / PMLR / @ 等且 ≥40 字 | 原刊机构／版权信息，保留英文，作引用块说明 |
| `noise` | 短文本、版面误标（如标题里的 `40<sup>th</sup>`） | 不补 |
| `other` | 其余无编号长文本 | 人工判断 |

**作者角标常与正文脚注同号**（都叫 1）：若也生成 `[^1]:`，会与真正的内容脚注抢同一个编号，译文里只剩一条。所以 `affiliation` 一律不占 `[^n]` 编号。

---

## 三、完整链路

```bash
# 1) 提取后立刻恢复并补回两侧（--pdf 可选）
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf

# 2) 填 _work/脚注_待译.csv 的 zh 列，把中文回填译文
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check

# 3) 出 PDF 后连文本层一起验
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --check --pdf-out <stem>_zh.pdf
```

产出：`_work/脚注.csv`（编号、页码、分类、原文、中文译文、各层命中情况）、`脚注_原文.md`、`脚注_待译.csv`、`脚注_交叉验证.md`、`待补脚注.md`（给 `--scaffold` 时）。

---

## 四、判定规则（交叉验证这一层用）

`pdftotext -layout` 把每页页底排成「编号独占一行 + 整体缩进的几行正文」。脚本按页（`\f`）扫描，下面几条是从 17 条脚注的真实案例里调出来的：

1. **编号行** `^\s{0,8}(\d{1,2})\s*$`：前导空格上限 8，排除居中公式的分子。
2. **正文首行**：缩进 ≥2 个空格、长度 ≥25。阈值必须放宽——脚注 4、5 只有 2 空格，用 ≥3 会整条丢掉。
3. **编号必须递增**（`expected` 从 1 起）：挡掉页码、公式编号、图号这些不按 1-2-3 连续出现的误报。
4. **散文优先于公式**：首行含 `\tag`、`\frac`、`\mathbb`、`≥` 时，先看有没有两个相邻英文实词；有就仍算脚注正文（脚注 4 首行里有 `P(X . xi )`）。
5. **排除页眉**：`REVIEW OF POLITICAL ECONOMY`、`J. KAPELLER ET AL.` 之类。
6. **折行合并**：行末连字符接小写字母按断词拼接（`abso-` + `lute` → `absolute`），接大写字母保留连字符（`Kaldor-` + `Verdoorn`）；还原 `ﬁ/ﬀ/ﬂ` 连字。
7. **跨页续文**：某页最后几行有整体缩进、以小写字母或引号开头的块，且上一条脚注不以句末标点收尾，就并进上一条。

注意 `plain()` 只剥真正的排版标签（`<sup>`、`<i>`、`<span>` 等），**不会把 `<t.nagler@lmu.de>` 这样的邮箱当标签吃掉**。

---

## 五、补全到译文 Markdown：脚注，不是文末一节

**唯一交付形态是 Markdown 标准脚注**，没有任何 `## 脚注` 标题：

* 正文：`[^n]` 紧跟被注内容、位于句读之前（原刊在哪标就在哪标）；
* 文末：`[^n]: 脚注正文`，一行一条，**不带**「第 N 页脚注 n：」页面前缀。

页码与分类只留在 `_work/脚注.csv`。把页码写进定义行，`md2tex.py` 会原样排进页底
`\footnote{}`，读者在页底读到的是「第 6 页脚注 1：……」；不写正文标记、只在文末堆
一节定义，则 `md2tex.py` 只能把它降级成文末编号段落——那正是「脚注变成单独一节」
的成因。所以 `--apply` 的核心工作是**把标记锚回正文**，写定义只是收尾。

`--apply` 的顺序：

1. 摘掉旧稿的 `## 脚注` 节（有的话），逐条解析出编号、正文、「（对应「……处」）」提示语；
2. 正文 `<sup>n</sup>` → `[^n]`（确定性，唯一自动锚定）；
3. 有提示语的旧条目，按提示语在正文里定位，把 `[^n]` 插在那句话之后；
4. `--place` 给的 `anchor` 列，同样按原话定位插入；
5. 生成 `[^n]: 内容` 定义，追加到文末（参考文献之后），前面加一行 HTML 注释说明；
6. 判不出位置的脚注写进 `_work/脚注_待锚.csv`，`--check` 返回 1。

写回前自动留 `*.bak_footnotes` 备份；重复运行幂等。译文侧若 `zh` 还空着，定义行
写英文原文加 `<!-- 待译：请填入中文脚注译文 -->`，**`--check` 因此返回 1**；人已经
在 md 里写好中文的，`--apply` 不会覆盖（CSV 的 `zh` 列优先，其次 md 现存中文）。

作者机构／版权注常与正文脚注同号（都叫 1），不占 `[^n]` 编号，也不写进交付稿，
单列到 `_work/脚注_原刊信息.md`。脚注文字里的编号、URL 一字不改——`--check` 会逐条
比对，链接丢了直接报出来。

**`[^n]` 是唯一交付形态**：不许留字面 `<sup>n</sup>`；公众号版 `build_wechat.py` 认它
（内部归一成 `<sup>` 渲染，并挂到所注段落之后），PDF 版 `md2tex.py` 也认它。两者是
同一份译稿的两条发布分支。

### 判不出位置怎么办

MinerU 常把脚注号弄丢或弄变形（见第一节：17 个标志里 4 个变形）。脚本只做确定性
锚定，其余交人：

| 现象 | 处理 |
|---|---|
| `[^n]` 已在正文，但位置可疑 | 看编号是否升序：`--check` 会报「首次出现顺序不是升序」 |
| 句末标点后有个裸数字（`……劳动强度。7`） | 确认是脚注号后加 `--anchor-bare` 自动锚定 |
| 行内公式末尾有 `^ { 7 }` | 确认是脚注号后加 `--anchor-math`（`$x^{2}$` 和脚注 2 长得一样，别默认开） |
| 什么都没留下 | 人读 PDF，把正文里紧邻标记前的一句原话填进 `脚注_待锚.csv` 的 `anchor` 列，`--apply --place` 回灌 |

**不要**为了过门禁把标记塞到段末了事。脚注落错句子比缺一条更坏，且没有任何一层
自动校验能发现它。

---

## 六、补全到译文 PDF（保留脚注格式）

```bash
python scripts/md2tex.py <stem>_zh.md _work/pdf/paper.tex --source-pdf paper.pdf --pdf
python scripts/verify_pdf.py _work/pdf/paper.pdf --tex _work/pdf/paper.tex \
    --md <stem>_zh.md --footnotes _work/脚注.csv
```

`md2tex.py` 默认 `--footnotes footnote`：预扫全文 `[^n]:` 定义，把正文 `[^n]` 渲染成
LaTeX 页底 `\footnote{…}`，**脚注是页底真脚注，不是文末一段编号列表**。要尾注形式
用 `--footnotes endnote`。

**开头就有硬门禁**：只要存在「有定义、正文却没有引用」的脚注，`md2tex.py` 直接
`exit 2` 并列出编号，不再静默把它们排成文末编号段落（旧版正是这样把「脚注变一节」
做成了默认行为）。确实要降级才加 `--allow-orphan-notes`。反过来，正文有标记却
没有定义时打 `[WARN]`——PDF 里会留一个光秃秃的上标编号。

两个已踩过的坑：

- **长 URL 必须走 `\url{}`**（已加载 `xurl`）。当普通文本排进页底脚注时无法断行，实测撑出 2 处 `Overfull \hbox`；改走 `\url{}` 后归零。
- **`\footnote{}` 里的内容要过 `inline()`**：行内公式、粗体、上标仍要正确渲染，不能把 Markdown 字面塞进去；定义里的 HTML 注释（待译标记）与历史「第 N 页脚注 n：」前缀在建表时就清掉，不会漏进页底。

`verify_pdf.py` 会逐条核 `_work/脚注.csv` 的中文/英文关键串是否出现在 PDF 文本层，并检查 TeX 里 `\footnote{}` 数不少于清单内容脚注数、文本层无字面 `[^n]` / `<sup>`。

---

## 七、四层门禁

| 环节 | 查什么 | 失败行为 |
|---|---|---|
| `footnote_recover.py --check` | 清单、逐条「定义 + 正文引用」双向齐全、编号升序、URL/中文、`## 脚注` 节残留、`<sup>` 残留；给 `--pdf-out` 时还查 PDF 文本层 | 返回 1 |
| `fidelity_check.py --strict` | `_work/脚注.csv` 存在、译文每条脚注既有 `[^n]:` 定义又有正文 `[^n]`、无悬空定义/孤儿标记/编号乱序、链接与中文齐备 | `hard_fail` → 返回 1 |
| `md2tex.py`（PDF 分支入口） | 有定义没引用的脚注（会退化成文末一节） | `exit 2`，除非 `--allow-orphan-notes` / `--footnotes endnote` |
| `build_wechat.py`（公众号分支） | `self_check()` 查样式白名单，`audit_notes()` 查脚注是否静默丢失、定义是否未进版面 | 报错不写文件 |
| `verify_pdf.py`（PDF 分支验收） | 编译错误、`Overfull \vbox`、图片数、书签、文本层、逐条脚注进 PDF | 返回 1 |

唯一豁免：**纯 Markdown 输入、没有 MinerU 结果包**时，`fidelity_check.py` 显式加 `--skip-footnote-check`，并在交付报告里写明理由。

---

## 八、边界与人工责任

- 检的是**页底编号脚注**。尾注、夹注、表下注、无编号的 Notes 不在 `page_footnote` 里，仍要人工翻 PDF 确认。
- 双栏期刊、脚注排在栏底的版面：主源仍是 `content_list.json`（不受版面影响）；交叉验证可能报「未确认」，看 `脚注_交叉验证.md` 逐条目视即可。
- `--apply` 只保证**结构与内容齐全**；正文 `[^n]` 标记该落在哪句话之后，脚本判不了，必须人读。规则 2 要求「位置是结构的一部分」，补标记时不要顺手挪段落。
- `\footnote{}` 里不放行间公式、`align` 环境、整段代码；这类内容改成尾注或正文注，避免编译期炸掉。
- 文字层来自 PDF 而非 OCR；扫描件无文字层时交叉验证会报「取不到」，先 OCR 再来对账。
- 旧命令 `scripts/footnotes.py` 保留为兼容入口：它把 `--md/--strict/--patch` 转发给新脚本，但**不再从 PDF 文字层检出脚注**，`--patch` 也不再写回 Markdown。
