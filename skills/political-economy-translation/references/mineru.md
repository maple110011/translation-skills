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
| `--no-formula` | **不要用**。政经文献里公式是论证的一部分 |

### 输出结构

```
_work/extract/<文件名>/
  full.md                    ← 要用的就是这个
  images/                    ← 图片，full.md 里以相对路径引用
  *_content_list.json        ← 逐块结构，排查"为什么这段没了"时有用
  layout.json                ← 版面分析结果
```

`full.md` 里的图片路径是相对路径。如果要把 Markdown 移出这个目录，必须连 `images/` 一起移，否则图全断。

---

## 三、提取质量：五类会骗人的地方

### 1. 上下标被压平

`x²` 变成 `x2`，`S′` 变成 `S'`，`\hat{v}` 变成 `v̂` 或 `v`。
**特征**：公式看起来"对"，但量纲或含义不对。
**处理**：对照 PDF 逐式核对，尤其是指数、下标时序（`K_t` vs `K^t`）、撇号（`v′` 是转形后的价值，不能漏）。

### 2. 双栏串行

双栏 PDF 的右栏内容被插到左栏中间，句子读不通。
**特征**：段落内突然出现另一个话题的一句话，然后接回原话题。
**处理**：这类只能重新提取或手工重排。判断依据是 `layout.json` 的块顺序，或直接看 PDF。

### 3. 表格塌陷

复杂表格（多级表头、合并单元格）常被拍平成纯文本或错位。
**处理**：译之前先把表格重建成 Markdown 表格，对照 PDF 核对每个数字。表格错一位，整段论证的实证基础就错了。

### 4. 脚注丢失或错位（最常见、也最容易被漏掉）

有两种形态，**后一种抽查三页根本发现不了**：

- **错位**：脚注被丢进正文末尾、或被当成正文段落。特征是正文里冒出一个孤立年份、`ibid.`、或与上下文无关的完整句子。
- **整批丢失**：vlm 只把正文里的上标标记提出来（`<sup>n</sup>`），页底脚注正文一条也不写。实测一篇 45 页期刊论文 17 条脚注全丢，只剩 13 个标记；另外 4 个标记变形——两个被塞进行内公式（`^ { 7 }`、`^ { 8 }`），两个退化成句末裸数字（`. 5`、`power. 15`）。还有一条脚注跨页，前半在页 7 页底、后半在页 8 页底。**块级对账对此完全免疫**：译文与源文都缺，块数照样一一对应。

**处理**：不要靠翻页抽查。MinerU 的版面识别其实**认得出**脚注（`content_list.json` 里 `type=page_footnote` 带页码与完整文字），只是生成 `full.md` 时按类型白名单整类过滤。所以主源用提取包，`scripts/footnote_recover.py` 直接从那里恢复并自动补回原文与译文两侧：

```bash
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --source <stem>_原文.md --target <stem>_zh.md --apply --check --pdf paper.pdf
# 中文译文填 _work/脚注_待译.csv 的 zh 列后回填
python scripts/footnote_recover.py ./_work/extract -o ./_work \
    --translations _work/脚注_待译.csv --target <stem>_zh.md --apply --check
```

`--apply` 归一 `<sup>n</sup>` → `[^n]`、把标记**锚进正文对应句子**、把 `[^n]: …` 定义写到文末（**不插 `## 脚注` 节、不写「第 N 页脚注 n：」前缀**），写回前留备份且幂等；判不出位置的脚注进 `脚注_待锚.csv`，`--check` 逐条核「定义 + 正文引用」双向齐全、链接与中文，未落位或未填中文直接返回 1。`--pdf` 只作 PDF 文字层交叉验证（双栏期刊脚注在栏底，未确认不等于提取包有错）。作者机构／版权注与正文脚注同号时不占编号，单列到 `脚注_原刊信息.md`，不进交付稿。判据、编号规则与四层门禁见 [footnotes.md](footnotes.md)；旧 `scripts/footnotes.py` 只是兼容入口。

### 5. 公式编号被吞

`(3)` 编号可能被并入公式内部或直接丢失。
**处理**：正文里若有"由式(3)可得"，必须确保式(3)还在且编号一致。

---

## 四、提取后必做的抽查

不要整篇读一遍就信了。做这三件事，五分钟，能抓住绝大多数问题：

1. **数段落。** 取 PDF 的某一页，数它有几个自然段，再到 `full.md` 里数对应位置。差一个就说明合并或漏掉了。
2. **比公式。** 随机挑三个含公式的段落，把 PDF 上的式子和 Markdown 里的 LaTeX 并排看。重点看上下标和撇号。
3. **查脚注。** 挑一页有脚注的，确认脚注数量一致、内容对得上；但**抽查之外还要跑一次 `footnotes.py --strict`**——整批丢失是抽查抓不到的，见上节。

发现系统性缺陷（比如整篇双栏串行、脚注整批丢失），不要硬译——换 `--model` 重提，或用 `--pages` 分段重提，或改用别的工具。**在错误的底稿上翻译，后面所有校验都失去意义。**

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
| 正文有 `<sup>n</sup>` 但一条脚注正文都没有 | vlm 把页底脚注整批丢了 | 跑 `footnotes.py --strict`，用 `--patch` 补回；不要手工翻页找 |

---

## 六、什么时候不用 MinerU

- **原文已有干净的 LaTeX 源码**：直接用源码，比任何提取都准。
- **原文是 arXiv 或出版社的矢量 PDF，且已有他人提取好的 Markdown**：先看现成的，省一次调用。
- **纯数学教材**：走 `mathtranslations`，它按 LaTeX 项目重建，比 Markdown 路线更合适。

提取只是入口。真正决定译文质量的是术语、对账和通读，工具在这三件事上帮不了多少。
