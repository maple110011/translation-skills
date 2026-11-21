# 马恩引文索引构建工具

把《马克思恩格斯文集》（人民出版社 2009）的中文译文与 MECW 英文原文对齐成**句级索引**，
供 `political-economy-translation` skill 的 `scripts/marx_quotes.py` 检索：输入英文文献里的
马恩引文，返回文集译文、章次与印刷页码。

**本目录只含工具与篇目元数据，不含任何原文。** 语料需自备，来源见下文。

## 目录里有什么

| 分组 | 文件 | 作用 |
|---|---|---|
| 取源 | `fetch_mecw.py`、`fetch_pdf.py`、`index_mecw.py` | 从公开源抓英文 HTML 与各卷 PDF；只取文件头索引篇目 |
| 建库 | `build_corpus.py`、`build_vol.py`、`build_works.py`、`build_vol8.py`、`make_letters.py` | HTML → 块级语料 → 句级语料 |
| 对齐 | `align.py`、`align_para.py`、`align_sent.py`、`align_vol8.py`、`map_vol8.py` | 段落级 DP 与句级对齐 |
| 定位 | `page_map.py`、`repaginate.py`、`refix_pages.py`、`verify_pages.py`、`finalize.py` | 印刷页码抽取、重锚、抽检 |
| 映射 | `resolve_works.py`、`resolve_content.py`、`disambiguate.py` | 中英篇目映射与候选消歧 |
| 检索 | `engine.py`、`server.py`、`client.py`、`quotes.py`、`article.py` | 检索引擎、HTTP 接口、Markdown 引文抽取与回填 |
| 前端 | `export_web.py` | 单文件网页（可选，作者标注「默认不维护」） |
| 启停 | `start_service.bat`、`stop_service.bat` | Windows 后台起停服务 |
| 元数据 | `works.csv`、`index/*.json`、`index/works_decisions.csv` | 篇目映射表、篇目索引、映射决策记录 |
| 文档 | `PIPELINE.md`、`接口使用说明.md`、`CHANGELOG_20261109_页码重锚.md` | 建库管线与覆盖情况、接口说明、页码重锚记录 |
| 探针 | `test/test_article8.py` | 端到端冒烟测试 |

合计 32 个 `.py`（含探针）、2 个 `.bat`、4 份文档、9 个元数据文件，约 250 KB。

`index/*.json` 里只有**文件名、篇目名、日期与映射决策**（如 `{"vol": 38, "file": "MECW38-006.html"}`），
没有正文；`works.csv` 是中英篇目对照表。

## 目录里没有什么

以下一律不在本目录、也不在本仓库：

- 《马克思恩格斯文集》中文译文，包括任何整句、段落、章节；
- MECW 英文原文，以及从 MARX-ZH-CN 等站点抓取的 HTML／纯文本；
- 各卷 PDF、分页文本、页码映射产物；
- 句级语料 `corpus/*.jsonl`、英文篇目正文索引 `index/*.jsonl`、句级对齐表；
- 索引成品本身（约 73k 句的检索库）。

脚本里出现的《资本论》《马克思恩格斯文集》等只是文档字符串里的书名；中文长串均为算法说明、
踩坑记录与参数注释，不是原文引语。

## 语料从哪来

三路来源，都是公开可取的项目／数据集；也可以直接用你自己手上的正版电子文本，按下面的落位摆放。

| 语料 | 公开源 | 落位到 | 取法 |
|---|---|---|---|
| 《文集》中文 HTML | `github.com/MARX-ZH-CN/MARX-ZH-CN.github.io` 的 `docs/MEA/{1..8,10}/` | `raw/mea{N}/*.html` | 该仓库按篇一 HTML，逐篇下载（**没有第 9 卷**） |
| MECW 英文 HTML | 同一仓库的 `en/MECW/{1..50}/` | `raw/mecw{N}/*.html` | `python fetch_mecw.py`（按 `index/dl_works.json` 批量下） |
| 各卷 PDF（取印刷页码） | `hf-mirror.com` 的 `VoiceOfML/Teachers` 数据集 | `pdf/mea{N}.pdf`、`.txt` | `python fetch_pdf.py`（Range 分段下载后拼接） |

篇目索引从英文侧探测：`python index_mecw.py` 用 Range 请求只取文件头，全 50 卷约 6700 篇，
产出 `index/dl_works.json`、`dl_letters.json`、`dl_extra.json`。

### 构建顺序

```bash
python fetch_mecw.py                        # 英文 HTML（选编卷与书信卷按需）
python index_mecw.py                        # 篇目索引
python build_corpus.py                      # 两侧 HTML → 块级语料 corpus/mea*.jsonl、mecw*.jsonl
python resolve_works.py && python disambiguate.py   # 篇目映射 → works.csv
python build_vol.py 5 6 7                   # 《资本论》三卷
python build_works.py 1 2 3 4               # 选编卷
python make_letters.py && python build_works.py 10  # 书信卷
python page_map.py 5 6 7 1 2 3 4 10         # 补印刷页码（第 3 卷建议 PAGE_LIMIT=1200）
python finalize.py && python refix_pages.py # 收尾 + 页码重锚（顺序不可颠倒）
python verify_pages.py                      # 页码抽检
python server.py --port 8080                # 起服务
```

要加一卷、`works.csv` 的五种写法、页码为什么必须重锚、第 8／9 卷为什么放弃，都在
[`PIPELINE.md`](PIPELINE.md)。接口怎么接见 [`接口使用说明.md`](接口使用说明.md)。

### 语料目录的期望结构

脚本以自身所在目录为根（`os.path.dirname(os.path.abspath(__file__))`），语料与脚本同级：

```text
<本目录>/
├── raw/mea{N}/*.html   raw/mecw{N}/*.html     原始 HTML
├── corpus/mea{N}.jsonl  corpus/mecw{N}.jsonl  块级语料
├── corpus/vol{N}_sent.jsonl                   句级索引（带 page）
├── pdf/mea{N}.pdf  pdf/mea{N}.txt             各卷 PDF 与文字层
└── index/*.json                               篇目索引与映射
```

没有 `corpus/vol{N}_sent.jsonl` 时 `engine.py` 无内容可检索；`corpus/mea{N}.jsonl`（段落库）
缺失时，句级定位会退化为只给半句，脚本会打 warning——此时必须手工翻纸质本核对，不要用
`文集译文` 列。

## 授权与责任

- 正版底本是人民出版社 2009 年《马克思恩格斯文集》（十卷）。本仓库只提供工具，不提供文本。
- `fetch_*.py` / `index_mecw.py` 运行时会从上述公开源抓取原文。**是否抓取、抓取后如何使用与
  分发，授权责任在使用者。** 个人研究核对之外，不应再分发《文集》中文正文。
- 期刊多要求引文照抄文集；引用前请与纸质本核对页码与标点。

## 状态：有待进一步优化

这是一套为特定项目写的工作脚本，**尚未工程化**，已知待办包括：

1. **覆盖不全**：第 8 卷（《资本论》手稿选编，中文为摘选、缺数字锚，三种对齐方案均不可靠）与
   第 9 卷（语料源缺该卷 HTML，只能从 PDF 抽 OCR 层）未进索引；当前实际覆盖 8 卷、73 202 句。
2. **对齐精度有限**：保守估计约四分之一中文句存在句级错位风险，需逐条人工核对；
   `article.py` 的 replace 模式会删掉英文原句且无标记可查。
3. **参数硬编码**：页码跳跃上限 `PAGE_LIMIT` 需按卷手调；卷次—年份映射、`works.csv` 的
   `@z=n` 偏移等写在代码或数据文件里，换版本要改。
4. **外部源不稳**：依赖 MARX-ZH-CN 仓库与 hf-mirror 数据集的可用性，没有固定版本号或内容
   哈希；`index_mecw.py` 靠 Range 请求探测篇目，卷号跳号需特殊容忍（≥6）。
5. **测试薄弱**：只有 `test_article8.py` 一个端到端探针，外加 `verify_pages.py` 的页码抽检，
   没有回归测试。
6. **路径约定未抽象**：语料目录与脚本同级，未做成配置项，换机器要按原结构摆放。

## 提交约定

只提交脚本、文档与篇目元数据，**不要提交语料、索引成品或任何原文片段**。仓库根的
`.gitignore` 已挡住 `_marx_ref/`、`*.pdf`、`*.zip` 等，但新增的数据文件名仍可能漏网：
提交前用 `git status` 与 `git check-ignore -v <file>` 复核，尤其注意 `.jsonl`、`.html`
与大体积 `.json`。
