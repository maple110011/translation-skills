# dl skill 的参考文档

`SKILL.md` 管流程与门槛；这个目录放细则。**先读 SKILL.md，再按需要回来查。**

| 文件 | 一句话职责 | 什么时候读 |
|---|---|---|
| `accuracy-rules.md` | 六类准确性规则：公式不可改写、定理条件与强度、数值与表格、算法与代码、引用与交叉引用、术语与缩写 | 每次动笔前；判"这样改算不算等价"时 |
| `terminology.md` | 裁决顺序（默认保留英文）、学科分流、缩写与专名、项目表用法、术语与符号的分工 | 第 2 步定术语时 |
| `notation.md` | 符号一览表：位置与标记、收什么不收什么、排序写法、与原文 Notation 节的关系、脚本怎么配合 | 第 3 步搭符号骨架时 |
| `review-checklist.md` | 交付前清单：脚本查过的读结论、必须人读的、交付时怎么说、最容易漏的十处 | 第 5 步；交付前 |
| `figures.md` | 图与表：三条底线、就近重定位、并排图块写法、子图说明、宽图、实验表格、按原刊 bbox 还原尺寸与图号 | 有浮动对象时 |
| `workflow.md` | 长文断点、原文更新、批量多篇、只译一部分、与其他工具的边界 | 正文超约 1.5 万词或一次多篇时 |
| `mineru.md` | MinerU token、调用参数、五类会骗人的提取缺陷、抽查与排障 | 没有 arXiv 源码、只能从 PDF 提取时 |
| `arxiv-source.md` | 从 arXiv e-print 取作者 LaTeX：产出、多版本主文件怎么选、宏与脚注怎么处理、怎么按清单对账 | 论文有 arXiv 版本时（优先于 PDF 提取） |
| `pdf-latex.md` | 译文 md → PDF：首页版式、公式分组、间距、跳转、图表（与政经共用） | 用户要 PDF 时 |
| `zotero.md` | 译文 PDF 回挂 Zotero 父条目：锚定、判重、附件命名、降级（与政经共用） | 第 7 步 |
| `glossary/` | 数据：`ml_dl_core.csv`、`math_core.csv`、`stat_core.csv` | 查译名；`terminology.md` 会告诉你优先级 |

## 读的顺序

1. 什么都不确定 → `accuracy-rules.md` + `terminology.md` + `notation.md`；
2. 手上有一篇稿子 → `figures.md` 处理图表，`review-checklist.md` 收尾；
3. 出了问题（公式对不上、符号表缺、PDF 丑、Zotero 挂不上）→ 对应那份专文。

## 改这里的规矩

- 判据写进 references，流程只写"做什么"。
- 改完一条规则，回头看一眼 `SKILL.md` 里有没有同义的旧说法——两处不一致时，模型按先读到的那条执行。
- 新增文件要登记到本表，并在 `SKILL.md` 的 references 表里加一行。
- 与政经共用的两份（`pdf-latex.md`、`zotero.md`）改动要点见仓库根 [MAP.md](../../../MAP.md)。
