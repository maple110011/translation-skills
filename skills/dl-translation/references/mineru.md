# MinerU 提取：token、参数与质量

MinerU 把 PDF 转成 Markdown，包括公式（LaTeX）、表格、图片、双栏排版。这一节只讲这个 skill 怎么用它，以及哪些地方会骗人。

**一句话原则：提取结果永远是草稿，不高于原 PDF。** 与 PDF 目视不符之处，以 PDF 为准。

---

## 一、token：一次设置，之后不用管

旧的做法要么写死在脚本里，要么每次让用户粘贴——前者泄露，后者烦人。现在的解析顺序是固定的，脚本每次会告诉你命中的是哪一处：

| 优先级 | 位置 | 说明 |
|---|---|---|
| 1 | `--token sk-xxx` | 一次性覆盖，不落盘 |
| 2 | 环境变量 `MINERU_TOKEN` | 适合 CI |
| 3 | `~/.workbuddy/secrets/mineru_token.json` | `--set-token` 写入，权限 600；换位置用 `MINERU_CONFIG_DIR` |
| 4 | `~/.dsh/mineru-token`、`~/.dsh/mineru-token.txt` | 旧位置，只读，不会改写 |
| 5 | 交互输入 | 仅在终端下触发，问一次是否保存 |

### 首次设置

```bash
python scripts/mineru_extract.py --set-token
```

输入不回显。脚本会提示 MinerU 的 token 一般以 `sk-` 开头，粘错时能当场发现。写入后打印指纹（如 `sk-oDm…mniY  (len=51)`）而不是全文。

### 查看当前用的是哪个 token

```bash
python scripts/mineru_extract.py --token-status
```

输出形如：

```
来源：C:\Users\<用户名>\.dsh\mineru-token（旧文件，只读）
指纹：sk-oDm…mniY  (len=51)
解析顺序：
    命令行 --token
    环境变量 MINERU_TOKEN
    本脚本配置 C:\Users\<用户名>\.workbuddy\secrets\mineru_token.json
  ✓ 旧文件 ~/.dsh/mineru-token（只读）
    交互输入
```

**永远不要把 token 写进对话、脚本、仓库或报告。** 需要确认它是否正确，看指纹就够。日志和报错里也只出现指纹。

### token 失效的两种情形

| 报错 | 含义 | 处理 |
|---|---|---|
| `code A0202` | token 错误，或 `Bearer` 前缀缺失 | 检查复制时是否带上了空格；重新 `--set-token` |
| `code A0211` | token 过期 | 到 mineru.net → API 管理 → 重建，再 `--set-token` |

脚本会把 token 指纹附在报错里，方便判断是"这个 token 错了"还是"这个账号没额度"。

---

## 二、调用

```bash
# 单个文件，默认 vlm 模型
python scripts/mineru_extract.py paper.pdf -o ./_work/extract

# 只提第 3 到 12 页，扫描件强制 OCR，英文文献
python scripts/mineru_extract.py scan.pdf --pages 3-12 --ocr --lang en

# 整个目录（pdf/docx/pptx/图片都收）
python scripts/mineru_extract.py ./pdfs -o ./_work/extract

# 已有结果默认跳过；要重跑加 --force
python scripts/mineru_extract.py paper.pdf --force
```

### 参数怎么选

| 参数 | 建议 |
|---|---|
| `--model` | 默认 `vlm`。公式密集型理论文献用 `vlm`；纯文字、追求速度用 `pipeline`。`MinerU-HTML` 只用于网页 |
| `--ocr` | 只有在 PDF 无文字层（扫描件、影印本）时才加。给正常 PDF 加 OCR 反而降低精度 |
| `--lang` | 英文文献建议显式 `--lang en`，默认是 `ch`，会影响断行与标点判断 |
| `--pages` | 超过 200 页必须分段。也可以用它在动笔前先提两页看质量 |
| `--no-formula` | **绝不要用**。数学/统计论文里公式就是内容本身，去掉公式等于去掉论证 |
| `--extra-formats` | 默认只出 md+json。要额外格式时传 `latex`/`docx`/`html`，逗号分隔。**翻译流程不要用 latex**，理由见下节 |

### 输出结构

```
_work/extract/<文件名>/
  full.md                    ← 要用的就是这个
  images/                    ← 图片，full.md 里以相对路径引用
  *_content_list.json        ← 逐块结构，排查"为什么这段没了"时有用
  layout.json                ← 版面分析结果
```

`full.md` 里的图片路径是相对路径。如果要把 Markdown 移出这个目录，必须连 `images/` 一起移，否则图全断。

### 要不要让 MinerU 直接导出 LaTeX？

**能导，但不解决问题。** 精准解析 API 支持 `extra_formats: ["docx","html","latex"]`（本仓库脚本对应 `--extra-formats latex`），返回包里会多一个 `full.tex`。实测（29 页 ICLR 论文，`--pages 3-4`）：

- `full.tex` 的公式**仍然是一行一个** `\[ … \]`，多行推导照样被拆开——和 `full.md` 一模一样；
- 更糟的是它把 `\tag{4}` 写在 `\[ … \]` 里，这在 amsmath 下是**不合法的**（`\tag not allowed here`），导出件不能直接编译；
- 模板是 `article + ctex` 的通用重建件，正文还是英文，排版参数（字号、行距、页边）与原文无关。

所以：**仍以 `full.md` 为工作稿**，多行公式的分组在 `scripts/md2tex.py` 里按行处理（见 [pdf-latex.md](pdf-latex.md) 第二节）。LaTeX 导出只在"想要一份能编译的骨架"时有点用，不要指望它替你做对齐。

如果确实想从提取件里保留更多结构，比 LaTeX 更有用的是 `*_content_list.json` / `layout.json`：里面是逐块（`type` + 文本 + 页号 + bbox）的原始结构，可以据此判断"相邻两行公式是不是同一组"，比从 Markdown 反推可靠。当前脚本仍是按 Markdown 的连续 `$$` 块分组，够用但会误判跨页的情况。

---

## 三、提取质量：六类会骗人的地方

### 1. 上下标被压平

`x²` 变成 `x2`，`S′` 变成 `S'`，`\hat{v}` 变成 `v̂` 或 `v`。
**特征**：公式看起来"对"，但量纲或含义不对。
**处理**：对照 PDF 逐式核对，尤其是上下标层级（`x_i^2` vs `x_{i^2}`、`W^{(l)}` 的层号）、撇号（`x'` 与 `x` 是两个量）、花体与空心体（`\mathcal{L}` 损失 vs `L` Lipschitz 常数）。

### 2. 双栏串行

双栏 PDF 的右栏内容被插到左栏中间，句子读不通。
**特征**：段落内突然出现另一个话题的一句话，然后接回原话题。
**处理**：这类只能重新提取或手工重排。判断依据是 `layout.json` 的块顺序，或直接看 PDF。

### 3. 表格塌陷

复杂表格（多级表头、合并单元格）常被拍平成纯文本或错位。
**处理**：译之前先把表格重建成 Markdown 表格，对照 PDF 核对每个数字。表格错一位，整段论证的实证基础就错了。

### 4. 脚注整类丢失（最容易被忽略的静默坑）

`full.md` **不含**页底脚注：MinerU 服务端按类型白名单输出，`type=page_footnote` 被整类过滤。正文里往往只剩一个 `<sup>n</sup>` 引用标记，脚注文字一条都没有；编译 PDF 也不报错，所以肉眼看 `full.md` 很难发现。实测三篇 ICLR/ICML/NeurIPS 论文共 13 条 `page_footnote`，`full.md` 收录 **0 条**，其中 10 条是带条件、假设、复现链接的内容脚注。

**但数据没丢**：`*_content_list.json` 的 `page_footnote` 块带 `page_idx`、`bbox` 与完整文字，`content_list_v2.json`、`layout.json` 条数一致。所以**不需要重新 OCR、不需要装 PDF 库、不需要换 `--model`**。

```bash
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf
```

`--apply` 会把正文 `<sup>n</sup>` 归一成 `[^n]`、把标记**锚进正文对应句子**、把 `[^n]: …` 定义写到文末（**不插 `## 脚注` 节、不写「第 N 页脚注 n：」前缀**），写回前留 `.bak_footnotes` 备份、可重复运行。脚本产出 `脚注.csv`、`脚注_原文.md`、`脚注_待译.csv`、`脚注_交叉验证.md`、`脚注_待锚.csv`（判不出位置的，含区间提示）、`脚注_原刊信息.md`（机构／版权注，不进交付稿），并分类：

| 类别 | 判据 | 要不要补 |
|---|---|---|
| `footnote` | 带 `<sup>数字</sup>`、正文 ≥ 30 字 | **必须补并照译** |
| `affiliation` | 机构 / 通讯 / 版权 / 会议注 | 常与正文脚注同号（都叫 1），**不占 `[^n]` 编号**；作引用块说明保留英文 |
| `noise` | 版面误标，如标题里的 `40<sup>th</sup>` | 忽略 |
| `other` | 其余无编号长文本 | 人工判 |

译文侧未填中文时会留 `<!-- 待译 -->`，`--check` 因此返回 1；填好 `_work/脚注_待译.csv` 的 `zh` 列后用 `--translations ... --apply --check` 回填。**先补再译**，`[^n]` 是唯一交付形态，不要写 `<sup>n</sup>`。脚本逐条核编号、页码、链接与中文；`fidelity_check.py --strict` 与 `verify_pdf.py` 还会在交付与 PDF 两层再验一遍。细节见 SKILL.md 翻译规则「脚注」条，两个 skill 的流程完全一致。

两条不推荐的替代路径：`pdftotext -layout` 按页底抓——双栏论文的脚注在**栏底**而不是页底（Nagler 2023 就是），长脚注与 URL 还常被断行，召回不全；装 PyMuPDF/pdfplumber 按字号 + 坐标聚类——本机均未安装，引入外部依赖也违背本 skill「只用 Python 标准库」的约定。

### 5. 算法框：抽成 div，不是围栏代码块

算法框（Algorithm 环境）在 `full.md` 里是一个 HTML div，**不是**三反引号代码块：

```html
<div class="mineru-algorithm" style="white-space: pre-wrap; font-family:monospace;">
算法 10.4: 坐标上升变分推断 (CAVI)。

1 初始化  $q_{j}(z_{j})$  for j = 1 : J
2 foreach t = 1 : T do
3    foreach j = 1 : J do
</div>
```

行结构与缩进靠 `white-space: pre-wrap` 保留（`3` 后面那四个空格就是嵌套层级），内容里混着 `$…$` 行内公式。

**处理**：
- 保留 div 与 `class`/`style`，只译文字；步号、行序、缩进空格不动，`$…$` 不动。`md2tex.py` 靠 `mineru-algorithm` 认出它并排成带上下细横线的算法块；删掉外壳就只能当正文排，标签还会印到纸上。
- 也有算法框在 `full.md` 里被压成散文（`Algorithm 10.4 (…). The … can be computed …`），那种没有 div 也没有缩进，只能回 PDF 按原版式恢复成围栏代码块（见 SKILL.md `<code_blocks>`）。
- `fidelity_check.py` 把 div 当「算法框」单独核：块数、行数不一致是硬性失败，步号序列与缩进变化是建议性发现；`verify_pdf.py` 再核一遍「算法框首行是否进了 PDF 文本层」。

### 6. 公式编号被吞

`(3)` 编号可能被并入公式内部或直接丢失。
**处理**：正文里若有"由式(3)可得"，必须确保式(3)还在且编号一致。

---

## 四、提取后必做的抽查

不要整篇读一遍就信了。做这三件事，五分钟，能抓住绝大多数问题：

1. **数段落。** 取 PDF 的某一页，数它有几个自然段，再到 `full.md` 里数对应位置。差一个就说明合并或漏掉了。
2. **比公式。** 随机挑三个含公式的段落，把 PDF 上的式子和 Markdown 里的 LaTeX 并排看。重点看上下标和撇号。
3. **查脚注。** 跑 `python scripts/footnote_recover.py ./_work/extract -o ./_work --source <stem>_原文.md --target <stem>_zh.md --apply --check`；返回 1 就先按上节补（中文译文填 `脚注_待译.csv` 后回填），再动笔。不要只挑一页肉眼比对——`full.md` 是整类丢脚注，抽查一页看不出系统性缺失。给 `--pdf` 可做 PDF 文字层交叉验证，结果在 `_work/脚注_交叉验证.md`；双栏期刊脚注在栏底，未确认不等于提取包有错。

发现系统性缺陷（比如整篇双栏串行），不要硬译——换 `--model` 重提，或用 `--pages` 分段重提，或改用别的工具。**在错误的底稿上翻译，后面所有校验都失去意义。**

---

## 五、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `HTTP 403 SignatureDoesNotMatch` | 上传时多带了 `Content-Type` 等头 | 脚本已用 `http.client` 规避；若自行改代码，注意不能用 `urllib` 发 PUT |
| `code A0202` | token 错误 | 见上节 |
| `code -60006` | 超过 200 页 | 用 `--pages` 分段 |
| `code -60005` | 超过 200MB | 拆分 PDF |
| `code -60018` | 当日任务数达上限 | 次日再试；或先用 `--pages` 提关键章节 |
| 一直停在 `waiting-file` | 上传未完成 | 检查上传是否报错；必要时 `--force` 重跑 |
| 状态 `failed` | 解析失败 | 看 `err_msg`；多为加密 PDF 或损坏文件 |
| 图片全断 | Markdown 与 `images/` 分离 | 一起移动 |
| 中文乱码 | 编码问题 | `full.md` 是 UTF-8，读取时不要用 GBK |

---

## 六、什么时候不用 MinerU

- **原文已有干净的 LaTeX 源码**：直接用源码，比任何提取都准。
- **原文是 arXiv 或出版社的矢量 PDF，且已有他人提取好的 Markdown**：先看现成的，省一次调用。
- **纯数学教材**：走 `mathtranslations`，它按 LaTeX 项目重建，比 Markdown 路线更合适。

提取只是入口。真正决定译文质量的是术语、对账和通读，工具在这三件事上帮不了多少。
