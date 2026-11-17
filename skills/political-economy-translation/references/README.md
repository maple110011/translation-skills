# 政经 skill 的参考文档

`SKILL.md` 管流程与门槛；这个目录放细则。**先读 SKILL.md，再按需要回来查。**

| 文件 | 一句话职责 | 什么时候读 |
|---|---|---|
| `translation-rules.md` | 六条硬规则的边界与判例：忠实不增删、结构不动、信达雅不越界、引用原样、公式定界符、成品只留正文 | 每次动笔前；判"这算不算增删"时 |
| `terminology.md` | 三类条目三种处理、内置资源、新词怎么定、项目表怎么建、合并与裁决 | 第 2 步定术语时；遇到译名分歧时 |
| `terminology-growth.md` | 核心术语表怎么积累：三层结构、收录门槛、"依据"是什么、四个已踩的坑 | 维护跨篇总表时 |
| `style-sheet.md` | 全篇风格约定怎么建、怎么用、怎么并回总表 | 第 2 步之后、动笔之前 |
| `style/default.md` | 默认风格总表（自称、论证动词、句式、数字体例、引文页码） | 起 `_work/<stem>_风格.md` 时抄底 |
| `review-checklist.md` | 交付前四遍检查：少没少／意思偏没偏／中文通不通／技术结构 | 第 5 步；交付前 |
| `semantic-review.md` | 语义审读怎么读、查什么、举证格式、怎么防自我确认 | 需要人读一遍语义时 |
| `workflow.md` | 长文断点续译、原文更新、批量多文件、只译一部分 | 正文超约 1.5 万词或一次多篇时 |
| `footnotes.md` | 脚注从 `content_list.json` 恢复到 md 与 PDF 的完整链路与判定规则 | 第 1 步；脚注 `--check` 不 PASS 时 |
| `mineru.md` | MinerU token、调用参数、五类会骗人的提取缺陷、抽查与排障；参考文献切分（`split_refs.py`） | 第 1 步提取 |
| `figures.md` | 图表按"首次提及"归位、多联图并排与按原刊 bbox 定宽、发布口径基准 | 处理图表时 |
| `delivery.md` | 交付：书目拼回、产物清单、YAML 元信息四组字段、发布稿删节口径、归档与回复 | 第 6 步 |
| `wechat.md` | 公众号版：五条发布口径、白名单六条、637px 版心、两道自检与粘贴方法 | 出公众号版时 |
| `pdf-latex.md` | 译文 md → PDF：首页版式、公式分组、间距、跳转、图表（与 dl 共用） | 用户要 PDF 时 |
| `zotero.md` | 译文 PDF 回挂 Zotero 父条目：锚定、判重、附件命名、降级（与 dl 共用） | 第 7 步 |
| `marx-ref.md` | 马恩引文核对：接入 `_marx_ref`、按卷收窄、可信度、段落定位 | 文中有马恩引文时 |
| `development.md` | 维护向：马恩原著与语料不入库的理由、索引脚本 WIP 状态、官方包更新、许可与仓库边界、维护约定 | 改仓库结构、公开发布前 |
| `glossary/` | 数据：`glossary_core.csv`、`empirical_terms.csv`、`verified_names.csv`、`names_xinhua.tsv.gz`、`glossary_conflicts.csv`、`pick_name.py` | 查译名；`terminology.md` 会告诉你优先级 |

## 读的顺序

1. 什么都不确定 → `translation-rules.md` + `terminology.md`；
2. 手上有一篇稿子 → `style-sheet.md` 起风格表，`review-checklist.md` 收尾；
3. 出了问题（脚注丢、PDF 丑、Zotero 挂不上）→ 对应那份专文，别在 SKILL.md 里找答案。

## 改这里的规矩

- 判据写进 references，流程只写"做什么"。SKILL.md 里铺判例会把它撑成一本手册。
- 改完一条规则，回头看一眼 `SKILL.md` 里有没有同义的旧说法——两处不一致时，模型会按先读到的那条执行。
- 新增文件要登记到本表，并在 `SKILL.md` 的 references 表里加一行，否则没人会读到它。
