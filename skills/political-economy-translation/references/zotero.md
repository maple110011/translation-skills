# 把译文 PDF 挂回 Zotero 条目

文献多是从 Zotero 文献库里拖出来的：Windows 的 `Zotero\drag` 临时目录会被清空，原文 PDF 常常已经不在，但文献条目还在库里。译文 PDF 出完、验收通过后，应该回到那个条目下面，而不是散落在工作区。

两个翻译 skill 共用 `scripts/zotero_attach.py` 的同一份实现（MD5 必须一致，改完复制到另一边）。

---

## 一、在流程里的位置

第 7 步，`verify_pdf.py` 通过之后。挂的是**已验收的** PDF，不是中间产物；公众号版、Markdown 译文与 PDF 是三份独立产物，只有 PDF 进 Zotero。

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md   # 单篇
python scripts/zotero_attach.py --batch . --strict                # 一次交付多篇
```

---

## 二、走本地 API，不碰 zotero.org

Zotero 7+ 在 `127.0.0.1:23119/api` 上暴露一套本地 API：

| 能力 | 条件 |
|---|---|
| 读条目、子附件、附件 md5 | 不需要认证；只需「设置 → 高级 → 允许此计算机上的其他应用程序与 Zotero 通信」 |
| 写条目、传文件（Zotero 10+） | `POST /api/local/authorize` 弹窗授权，用户点 **Always Allow** 拿到可长期复用的 key |
| 文件落盘 | 上传后进 `<数据目录>/storage/<附件KEY>/`，与手动拖拽完全一样 |

所以**不需要** zotero.org API key，**不需要** `pyzotero`，**不需要**联网。这也意味着旧文档里那套「没配 key 就只能手工拖」的前提不成立。

### 首次配置（一次）

1. Zotero → 设置 → 高级 → 勾「允许此计算机上的其他应用程序与 Zotero 通信」；
2. 跑一次脚本，Zotero 弹窗问是否允许写入 → 点 **Always Allow**；
3. key 落到 `~/.workbuddy/zotero.json`（这是默认路径，换位置用 `--config` 或环境变量 `ZOTERO_CONFIG`）：

```json
{"server_id": "9MDOd3HexaRq", "local_key": "<32 位>", "remember": true, "user_id": "0"}
```

`server_id` 标识"这一套库"。换了库（或换了数据目录）这个 ID 会变，脚本会重新授权一次——这是官方要求的语义，不是 bug。要撤销：Zotero → 设置 → 高级 → **Clear Write Authorizations**。

只点 **Allow**（不点 Always Allow）也能跑，但 key 一次性，每次都要弹窗；脚本会提示。

---

## 三、锚定：先证明挂给谁

线索按可靠性从高到低：

| 顺序 | 线索 | 判据 |
|---|---|---|
| 1 | `--parent-key` | 直接取条目 |
| 2 | DOI / arXiv | front matter 的 `doi` / `arxiv`，或原文 md 里捞出的 `10.xxxx/...`；`qmode=everything` 搜回来后**等值比较 DOI 字段** |
| 3 | `source_pdf` | front matter 里那条原文 PDF 的文件名，与库里附件的 `filename` **逐字（NFKC 归一）相等** → 反查 `parentItem`。这是最硬的证据，因为该文件名就是 Zotero 自己写出来的 |
| 4 | 英文标题 | 归一化后相似度 ≥ 0.85，且与第二名差 ≥ 0.08（唯一）；副标题差异单独放宽容 |

**中文标题不参与匹配**：库里存的是英文原题，拿 `title_zh` 去搜只会命中噪声。`citekey` 只作搜索关键词，**绝不当作 DOI**（旧版把译文 citekey `xxx-zh` 塞进 DOI 参数，搜出来必然是噪声）。

歧义时输出前三候选（key、相似度、标题）并返回 3，**一条都不写**。

---

## 四、判重与版本

读父条目的 `children`，只比 `attachment`：

| 情况 | 状态 | 动作 |
|---|---|---|
| 没有同名附件 | `attached` | 新建附件条目 → 三步上传 |
| 同名，md5 相同 | `unchanged` | 跳过，不弹授权窗 |
| 同名，md5 不同 | `updated` | **复用该附件条目**，覆盖其文件；附件数不变 |

判据是 **filename + md5**，不是只看文件名——只看文件名会让改稿重出的 PDF 永远挂不上新版（旧版的行为，且与文档自述矛盾）。

改稿后直接重跑即可；不要手工去 Zotero 里删旧附件，也不要新建"中译 v2"。

---

### 附件名与标题

Zotero 里那个附件的**文件名与标题**按同一套规则生成：

| 字段 | 取值 |
|---|---|
| `filename` | `zh - <原文附件名>.pdf` |
| `title` | 同上，去掉 `.pdf` |

「原文附件名」优先取父条目下已有的原文 PDF 附件（Zotero 自己按「作者 et al. - 年 - 题名」命名的那份），其次取 front matter 的 `source_pdf`，都没有才退回 `<stem>`。这样附件列表里原文和译文挨着排、一眼对得上，排序也在同一段。

**title 必须显式写**：通过 API 建附件时留空，Zotero 会存一个空标题，而不是回退去显示文件名——列表里就是一片空白。旧实现踩的就是这个。

旧版挂成 `<stem>_zh.pdf` 的，重跑一次会自动删掉旧附件、按新名重建（只删这个脚本自己的命名，不碰原文附件）。前缀用 `--name-prefix` 改，标题用 `--attach-title` 覆盖。

---

## 五、状态、退出码与降级

| 状态 | 含义 | rc |
|---|---|---|
| `attached` / `updated` / `unchanged` | 挂好了（新建／覆盖／本就是这版） | 0 |
| `error` | 硬错；若刚建过附件条目，已回滚删除，不留空壳 | 1 |
| `pending` | 没锚定，或写不了 | 2 |
| `ambiguous` | 多个候选，等人选 | 3 |

`--strict` 把 `pending`／`ambiguous`／`prepared` 一律算失败（rc=1），交付门禁用；`--auto` 同理。

写不进去时**不要复制副本**——Zotero 拖拽/导入时会自己把文件复制进 `storage/`，中间副本纯冗余。Zotero 没启动、本地 API 没开或版本太低时，脚本**不会中断**：每篇记 `pending`（rc=2），照常产出下面两样东西：

- `pending.md`：一次交付一张汇总表（PDF 路径、父条目 key、标题、状态）；
- `attach.js`：整段粘进 Zotero「工具 → 开发者 → 运行 JavaScript」，Run 一次挂完全部已锚定的：

```js
const jobs = [{ pdf: "E:\\...\\Xxx_zh.pdf", parent: "ABCD1234" }];
for (const j of jobs) {
  const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, j.parent);
  await Zotero.Attachments.importFromFile({ file: j.pdf, parentItemID: item.id });
}
```

只有显式 `--stage` 才把待挂 PDF 集中复制到 `_zotero/inbox/` 一处。

记账：单篇写 `_work/zotero_attach.json`；总账 `_zotero/attached.csv` 按 `<stem>` 一行，记当前挂的是哪一版（核对 `md5`）。

---

## 六、实测踩到的三个坑（Zotero 10.0.8）

这三条与官方文档的描述不一致，改代码前先看：

1. **文件上传参数必须放在 form body 里**。官方文档写的是 query string（Web API 语义），本地实现照 query 传会返回 **500 空响应**；放 `application/x-www-form-urlencoded` 的 body 里才 200。
2. **覆盖上传的 `If-Match` 要填旧文件的 md5**（文件 ETag），不是条目 version。填 version 返回 `400 Invalid If-Match header`。
3. **用 `127.0.0.1` 而不是 `localhost`**。Windows 上 `localhost` 先试 `::1` 再回退 IPv4，每个请求多 2 秒；批量时肉眼可见。

另外：`GET /items?itemType=attachment` 全量拉附件表会超时（本机 3285 条），不要建全量索引，用 quicksearch 反查即可。

---

## 七、安全约束

- **绝不直接读写 `zotero.sqlite`**：Zotero 运行时数据库被锁，手工插 item 会破坏同步，也可能损坏整个文献库。写入只走官方本地/Web API。
- 不移动、不删除、不覆盖用户的**原文**文件；只新增译文附件的副本。
- 上传失败回滚：新建的空壳附件条目会被删掉，不在库里留"缺文件"的坏条目。
- 同名同 md5 幂等跳过，不重复挂。
- `--dry-run` 只读：查条目、判重，不写库、不产文件、不弹授权窗。

---

## 八、故障排查

| 现象 | 原因 / 处理 |
|---|---|
| 「本地 API 不可用」 | Zotero 没启动，或设置→高级 里那个开关没勾 |
| 授权弹窗一直不来 | Zotero 版本 < 10，没有本地写入；用 `attach.js` 一键挂 |
| 「用户在 Zotero 弹窗里拒绝了授权」 | 重跑，点 Allow / Always Allow；每分钟最多 5 次弹窗 |
| 「授权弹窗请求过频」 | `429`，等一分钟 |
| 「Invalid If-Match header」 | 覆盖时旧附件没有 md5；脚本会自动改成删除重建，若仍报错说明旧附件是 linked file |
| 「复验对不上」 | 上传返回成功但读回 md5 不符；看 Zotero 是否在同步/校验中，稍后重跑 `unchanged` 即可确认 |
| 「没找到父条目」 | 给 `--parent-key`；或补 front matter 的 `doi`／`arxiv`／`source_pdf`（`paper_meta.py --init` 能自动抓大部分） |
| 三篇全 `pending` 而库里明明有 | 检查译文 md 是否缺 front matter，或批量扫到了 `_work/` 下的中间件（脚本已跳过该目录） |
| 附件挂上了但打不开 | 到 `storage/<附件KEY>/` 看文件是否存在、字节数对不对；对不上就重跑，`update` 会覆盖 |
