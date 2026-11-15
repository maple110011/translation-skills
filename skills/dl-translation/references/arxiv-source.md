# 从 arXiv 源码出发

有 arXiv 版本的论文，**不要从 PDF 提取**。`e-print` 里就是作者原始 LaTeX：真公式、真定理环境、真 `\cite`/`\bibitem`、真图文件。从版面反推等于把已知答案丢掉再猜一遍，还得为猜错的部分付校对成本。

```bash
python scripts/arxiv_src.py 2207.01848 -o ./_work/arxiv
python scripts/arxiv_src.py https://arxiv.org/abs/2112.10510v2 -o ./_work/arxiv
python scripts/arxiv_src.py --from <stem>_zh.md -o ./_work/arxiv   # 从 front matter 的 arxiv 字段读
```

脚本只做五件事：下载 → 安全解包 → 找主文件 → 展开 `\input` → 出结构清单。它不试图把 LaTeX 完整翻成 Markdown（那是 pandoc 和模型的活）。

---

## 一、产出

| 文件 | 内容 | 怎么用 |
|---|---|---|
| `src/` | 原始解包件，保持作者目录结构（含 `.sty` `.bib` `.bbl`） | 查宏定义、查 bib、对照编译方式 |
| `main.tex` | 主文件原样，`\input` 保留 | 对照作者结构，看注释 |
| `main.flat.tex` | 展开 `\input` 并剥掉注释后的全文 | **翻译基准**，模型直接读这份 |
| `figures/` | 正文实际引用到的图，路径已改写成 `figures/…` | 译稿里的图片引用按它写 |
| `结构清单.md` | 章节树、公式、定理、图、表、引用、脚注、自定义宏 | 定稿后逐项对账 |
| `脚注.csv` | `\footnote` 按顺序抽出（列与 `footnote_recover.py` 兼容，页码留空） | 填 `zh` 列后回填译文 |
| `原文.md` | 可选，`--md` 且有 pandoc 时转出的 Markdown | 只想块级对账时用 |

---

## 二、先确认版本，再动笔

一个包里常有好几个可编译主文件：`main.tex`、`main_neurips_workshop.tex`、`main_neurips_old.tex`……**`main.tex` 未必是你手上那篇 PDF 的版本**。

脚本会把候选按体量列出来，`结构清单.md` 里也有一节。用它跟 PDF 对三样东西：**章节数、附录范围、图表数**。对不上就 `--main main_xxx.tex` 指定。

arXiv 版常常比会议版全——附录更长、脚注更多、图更全。**以哪一版为准要问用户**，不要默默挑大的那个：多出来的内容翻译了是白做，少译的部分是漏。

---

## 三、脚注与宏：tex 路线的两处特殊

**脚注**。tex 的脚注是 `\footnote{…}`，不在 `content_list.json` 里，所以 `footnote_recover.py` 那条链路走不通。改为：

1. 脚本已生成 `_work/脚注.csv`（`page` 为空，`text` 是源码原文）；
2. 填 `zh` 列；
3. 译文照常写 `## 脚注` 节，条数必须与 `结构清单.md` 的「脚注明细」一致；
4. `fidelity_check.py` 用 `--skip-footnote-check`，脚注完整性改由**条数相等**保证。

页码对不上是正常的——tex 里没有页码概念，这一层校验在 tex 路线下换成序号对账。

**宏**。源码里到处是 `\methodname{}`、`\E`、`\dataset` 这类自定义命令，直接读会当成正文。脚本从 preamble 抽出定义表，附在 `结构清单.md` 末尾。翻译时照表还原：`\E` 是 `\mathbb{E}`，`\dataset` 是 `\mathbf{D}`，`\methodname` 是论文自己的方法名。

遇到表里没有的宏，去 `src/` 里搜 `\newcommand`，别猜。

---

## 四、对账怎么用

tex 路线没有「原文块数 = 译文块数」这种现成基准（tex 的段落切分和 Markdown 不是一一对应），所以对账换成**清单对项**：

| 项 | 要求 |
|---|---|
| 章节 | 章节树逐条对得上；附录范围一致 |
| 公式 | 编号公式逐条在译文里出现，编号不跳号；`\tag` 保持原编号 |
| 定理类环境 | 数量与类型一致（Theorem 不能译成 Proposition） |
| 图 / 表 | 数量一致，图注逐条译出，编号不改 |
| 引用 | `\cite` 键数与正文引用位置数一致；参考文献条目一字不动 |
| 脚注 | 条数一致 |

块级对账仍可做：用 `--md` 转出 `原文.md` 后跑 `fidelity_check.py`，但**它只作参考**——pandoc 不展开宏，转换结果里会残留 `\methodname` 之类的字面量，块数也未必稳。

---

## 五、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `这个条目只提供 PDF` | 作者没上传源码。退回 `mineru_extract.py` |
| 主文件选错版本 | `--main` 指定；先用章节数/附录范围比对 |
| 图缺失 | 清单会列「包里同名文件」；仍找不到就说明作者没打包，需从 PDF 裁 |
| 展开后文件奇大 | 图目录里的 `.tex` 是 tikz 源码，属正常；`--no-flat` 可只留 `main.tex` |
| pandoc 转换失败 | 自定义类/宏导致；直接用 `main.flat.tex` 翻译，不必强求 md |
| 想要 Markdown 又没装 pandoc | 脚本会提示跳过；模型可以直接读 `.tex` |
| 下载慢/超时 | `--timeout` 调大；已解包过会复用 `src/`，`--refresh` 强制重下 |

---

## 六、什么时候仍然该走 PDF 提取

- 没有 arXiv 版本（期刊正式版、书章、扫描件）；
- PDF 与 arXiv 版差异大到不能互换（会议版删节、正式版重排）；
- 只需要看几页、不做全文对账。

其余情况，源码优先。
