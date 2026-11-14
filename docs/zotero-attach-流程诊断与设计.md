# 译文 PDF 回挂 Zotero · 流程诊断与重设

诊断对象：`political-economy-translation` / `dl-translation` 两个 skill 的「回挂 Zotero」链路
（`scripts/zotero_attach.py` + `references/zotero.md` + SKILL.md 编排位）。
本文替代 `references/zotero.md` 的设计部分；脚本与编排按文中 §4、§5 重写。

---

## 0. 一句话

现在的流程不是"自动化没做好"，而是**一次都没真正执行过**：三篇实测稿全部停在 `status: prepared` 等人手动拖文件。根因不是缺 API key，是**把唯一的自动通路绑在了错误的前置条件上** —— 本机 Zotero 10 的本地 API 已经能读能写、不要账号、不要 `pyzotero`，脚本却完全没用它；而"零配置兜底"给出的是一份**没有父条目 key、没有跳转链接、还分散在三处**的副本清单，人工成本高到没人愿意做。

---

## 0.1 落地结果（2026-11-15）

按本文重写后已在真库跑通，`_pfn测试/双代理_20261114` 三篇从 `prepared` 变成 `attached`：

| 稿子 | 父条目 | 走的线索 | 附件 key |
|---|---|---|---|
| Hollmann2022 | `GAS4E39W` | DOI `10.48550/arXiv.2207.01848` | `U7MTFUDG` |
| Muller2024 | `BM3PDSX9` | DOI `10.48550/arXiv.2112.10510` | `ANZEBKQR` |
| Nagler2023 | `U28WLFMK` | 标题 1.000 | `Q9ANPHAF` |

验收实测：重跑全 `unchanged`；篡改 PDF 后重跑 `updated` 且附件数仍为 1、库里 md5 与本地一致；锚定失败 `pending`（rc=2）、`--strict`（rc=1）；上传失败自动回滚（调试期三次回滚都删净，库里没留空壳）。文件真实落在 `D:\Zotero论文数据库\storage\<附件KEY>\<stem>_zh.pdf`。

---

## 1. 实测（本机，2026-11-14）

### 1.1 环境事实

| 项 | 实测值 | 意味着 |
|---|---|---|
| Zotero 版本 | **10.0.8**（`D:\软件\Zotero\zotero.exe`） | 本地 API **支持写入与文件上传**（10+ 才有） |
| 数据目录 | `D:\Zotero论文数据库`（`useDataDir=true`） | 不是默认 `~/Zotero`，脚本不能硬编码 |
| 本地 API | `GET localhost:23119/api/users/0/items` → **200** | 已在"设置→高级"里开启，读不认证 |
| `Zotero-Server-ID` | `9MDOd3HexaRq`（每个库不同） | 写请求必须回传；不可硬编码 |
| 本地写 | `POST /items` → **401**，`WWW-Authenticate: Zotero-API-Key`，提示 `POST /api/local/authorize` | 只差一次用户弹窗授权，**不是缺 zotero.org 账号** |
| `zotero://` 协议 | 已注册（`HKCR\zotero\shell\open\command`） | 有了 parent key 就能一键跳转条目 |
| `pyzotero` | **未安装** | 现有自动路径 100% 走不通 |
| `ZOTERO_API_KEY` / `~/.workbuddy/zotero.json` | **均无** | 同上 |

结论：现有脚本的"自动"分支在这台机器上**永远是死的**，实际只会走 `prepare()`。

### 1.2 产物事实（`_pfn测试/双代理_20261114/`）

三篇交付稿的 `_work/zotero_attach.json` 全部写着 `"status": "prepared"`、`"reason": "未配置 ZOTERO_API_KEY / ZOTERO_USER_ID"`、`"parent_key": null`、`"zotero_uri": ""`。

但用本地只读 API 按 `title_en` 各搜一次，**三篇一次全中**：

| 稿子 | 前端标题 | 命中父条目 | 类型 |
|---|---|---|---|
| Hollmann2022 | TabPFN: A Transformer That Solves Small Tabular Classification Problems in a Second | `GAS4E39W` | preprint |
| Muller2024 | Transformers Can Do Bayesian Inference | `BM3PDSX9` | preprint |
| Nagler2023 | Statistical Foundations of Prior-Data Fitted Networks | `U28WLFMK` | conferencePaper |

**锚定从来不是难点，难的是脚本没去问。** 这是整个问题的核心：`prepare()` 这条路上根本没有一次"查父条目"的动作，所以清单里 parent_key 恒为 null，用户拿到的是一堆"你自己去库里找吧"。

### 1.3 顺带炸出来的 bug

Hollmann 清单里 `"doi": "hollmann2022tabpfn-zh"` —— 这是**译文 citekey**，不是 DOI。`main()` 第 226 行：

```python
doi = args.doi or fm.get("doi") or fm.get("citekey") or ""
```

citekey 被塞进 DOI 参数，再去 `items(q=...)` 搜。真配了 key 的那天，这条会拿一个不存在的标识去搜，然后靠 title 兜底——搜错条目的风险全压在 `title_score < 0.45` 这个很松的阈值上。

---

## 2. 问题清单

### P0（流程实际失效的原因）

1. **最强的通路没用上。** 本地 API 只读→可拿 parent key；本地 API 写 + 授权→可直接上传文件。两者都不需要 zotero.org 账号、不需要 `pyzotero`、不需要联网。现有实现只认 Web API，等于把唯一的零成本自动化路径锁死。
2. **零配置路径不做锚定。** `prepare()` 不查父条目，manifest 里 `parent_key` 永远 null，也就没有 `zotero://select` 链接。用户必须自己在几千条文献里翻出那条，再右键挂附件——这一步的成本比翻译一段还高，所以没人做。
3. **citekey 冒充 DOI**（§1.3）。锚定的第一优先级是脏数据。
4. **同名附件即跳过，改稿永远挂不上新版。** 判据只有 `filename == pdf.name`，一旦存在就 `already-attached`。第二次编译出的 PDF（页码变了、脚注补了）会被静默丢弃。文档里"重新出 PDF 后重跑会生成新副本与新 sha256"与实际行为**矛盾**。

### P1（会咬人，但不致命）

5. **manifest 路径会互相覆盖。** 写在 `pdf.parent/_work/zotero_attach.json`。把多篇 PDF 一起放进 `_dist/` 或交付根目录时，后一篇覆盖前一篇。
6. **待挂副本逐篇分散。** 每稿一个 `_work/zotero_inbox/`，三篇就是三处（共 2.1 MB 重复）。批量交付时用户得挨个目录翻。
7. **不在交付产出清单里。** 两份 SKILL.md 第 6 步的产出表都没有 Zotero 项，`_交付说明.md` 里也没留痕。既然不是"产出"，模型就不会当步骤执行。
8. **无批量入口。** 一次交付三篇就得跑三次，且 `--md` 要手工指。
9. **`drag_title()` 恒定失效。** 正则要「作者 - 年份 - 标题」，而输入永远是 `<stem>_zh.pdf`。front matter 缺 `title_en` 时，标题会退化成 `Hollmann2022_zh`。

### P2（一致性）

10. **两份 SKILL.md 编排位不一致。** 政经的 `</workflow>` 在第 566 行，回挂 Zotero 在第 568 行——**在流程块之外**，等于附录；dl 的在 626 行闭合，段落在 616–624，在块内。同一段文字，一个是步骤，一个是脚注。
11. DOI 搜索走 `q` 默认域（title + creator），DOI 未必命中；应显式 `qmode=everything`。
12. 幂等只看文件名，不看内容（md5/sha），无法判断"这个附件是不是当前这一版"。

---

## 3. 设计依据：Zotero 10 本地 API 的真实能力

这一节是重设的地基，全部经本机实测或官方文档核对（`/support/dev/web_api/v3/local_api`）。

| 能力 | 条件 | 设计含义 |
|---|---|---|
| 读全库条目/子附件 | 无认证；需"设置→高级"开启本地 API | **锚定零成本**，可离线、无限速 |
| 写（POST/PUT/PATCH/DELETE） | `POST /api/local/authorize` 弹窗授权拿 key；每次写带 `Zotero-Server-ID` | 一次"Always Allow"换长期 key |
| 文件上传 | 三步流程本地可用，落盘到 `storage/<附件KEY>/` | **不需要 pyzotero、不需要 S3** |
| 覆盖已有附件文件 | `If-Match: <附件条目 version>` | 版本更新可原地替换，不必删了重建 |
| 跳过重复上传 | 第一步带 md5 且磁盘已存在 → `{"exists": 1}` | 天然幂等短路 |
| 只读预览 | `GET /items/<KEY>/file` → 302 到 `file://` | 复验时可核对真实落盘路径 |

授权语义（决定配置怎么存）：

- 弹窗三键：**Allow / Always Allow / Deny**。
- `Always Allow` → 返回 `remember: true`，key **可长期复用** → 存 `~/.workbuddy/zotero.json`。
- 只点 `Allow` → key **一次性**，第一笔写成功后即失效 → 脚本必须把 `401` 当常规分支，重新授权再试一次。
- 用户拒绝 → `403 {"denied": true}`；触发弹窗的请求限每分钟 5 次（`429` + `Retry-After`）。

**不建议**绕开这条路去写 `D:\Zotero论文数据库\storage\` 或 `zotero.sqlite`：DB 被锁、会破坏同步，条目也不会出现在 UI 里。官方 API 已经把这件事做完了，没必要自己造。

### 3.1 本地实现与文档不一致的三处（实测，Zotero 10.0.8）

文档按 Web API 语义写，本地实现并不完全照做。这三条都是实测撞出来的，已写进脚本注释：

| 差异 | 官方文档说法 | 实际行为 |
|---|---|---|
| 上传参数位置 | query string | **必须放 form body**（`application/x-www-form-urlencoded`）。照 query 传 → `500` 空响应 |
| 覆盖时的 `If-Match` | 「`If-Match` 或 `If-None-Match` 头」 | 值**必须是旧文件的 md5**（文件 ETag）。传条目 version → `400 Invalid If-Match header` |
| 主机名 | `localhost:23119` | 用 **`127.0.0.1`**。Windows 上 `localhost` 先试 `::1` 再回退，每请求多 2 秒 |

另外两条工程约束：`GET /items?itemType=attachment` 全量拉取会超时（本机 3285 条），不要建全量索引，用 quicksearch 反查；空 body 时缺 `Content-Type` 会 `400`。

---

## 4. 新流程

### 4.1 三条原则

1. **先锚定，后上传。** 锚定失败就不该产出副本——没有目标的副本是垃圾。锚定是唯一必须先做对的事。
2. **本地优先，远程兜底，手工最后。** 本地 API（无 key）→ Web API（有 key）→ 汇总清单 + 一键 JS。不在任何一层"静默降级"。
3. **挂载是交付的一部分。** 有状态、有退出码、有记账、可重跑；未挂的在交付说明里必须显形。

### 4.2 步骤

```
                    ┌─ --parent-key ────────────────┐
线索解析 ──→ 锚定 ──┤  DOI（front matter / 原文）    ├─→ parent_key
（本地）            │  title_en（归一化 ≥0.85 且唯一）│
                    └─  文件名「作者 - 年 - 题」     ┘
                              │ 失败
                              ├─→ 候选 ≤3 条 + zotero:// 链接 → ambiguous（rc=3）
                              └─→ 无候选 → pending（rc=2）
                              │ 成功
                       去重/版本判定（读 children，比 md5）
                              ├─ 无同名 ────────────→ 新建 attachment
                              ├─ 同名 + md5 同 ─────→ unchanged（跳过）
                              └─ 同名 + md5 异 ─────→ 覆盖原附件（If-Match）
                              │
                        上传（三步）→ 复验（读回 children 核 md5）→ 记账
```

**第 1 步 · 线索解析（不联网）**

取值优先级：`--parent-key` > `--doi` > front matter `doi` > 原文 md 里的 DOI / arXiv 号 > front matter `title_en` > `--title` > 原文文件名「作者 - 年份 - 题名」> 译文标题（**仅当它是英文**）。

- `citekey` **不再当 DOI**，只作为候选关键词（Better BibTeX 的 key 常在 `extra` 字段里，`q` 能命中）。
- 中文标题不参与匹配：库里存的是英文原题，拿中文去搜只会命中噪声。`title_zh` 只用于附件 title。

**第 2 步 · 锚定（本地 API 只读，无需 key）**

- `GET /api/users/0/items?q=<DOI>&qmode=everything` → 先按 DOI 精确等值。
- 再按标题：取回 ≤25 条顶级条目（排除 attachment/note），做 NFKC + 小写 + 去标点 + 去冠词的归一化，`SequenceMatcher` 比值 ≥0.85 且**与第二名差值 ≥0.08** 才算唯一命中。
- 命中即拿到 `parent_key` / `parent_title` / `zotero://select/library/items/<KEY>`。
- 歧义或零命中：**不写库、不复制**，输出候选表（key、标题、年份、DOI、链接）并 `rc=3`。
- 本地 API 不可用（Zotero 没开 / <10 / 关了开关）：走 §4.4 降级，但**仍先尝试**用总账里同 `<stem>` 的历史记录补 parent_key。

**第 3 步 · 去重与版本判定**

读 `GET /items/<parent>/children`，只比 `attachment` + `linkMode in (imported_file, imported_url)`：

| 情况 | 判定 | 动作 |
|---|---|---|
| 无同名附件 | `new` | 新建 |
| 有同名，md5 相同 | `unchanged` | 跳过，记账 |
| 有同名，md5 不同 | `updated` | **复用该附件条目**，`If-Match: <version>` 覆盖其文件 |

判据用 **md5 + filename**，不用 sha256——上传协议要的就是 md5，两套哈希只会互相打架。

**第 4 步 · 授权**

- 首次：`POST /api/local/authorize`，`appName` 用 `"translation-skills (<skill>)"`，body 带 `Zotero-Server-ID`。
- 引导用户点 **Always Allow**（打印一句说明，不要静默点 Allow）。
- 结果存 `~/.workbuddy/zotero.json`：

```json
{
  "server_id": "9MDOd3HexaRq",
  "local_key": "<32 位>",
  "remember": true,
  "user_id": "0",
  "inbox": "",
  "web_api_key": "",
  "web_user_id": ""
}
```

- 按 `server_id` 分区：ID 变了说明换了库，旧 key 直接作废重授权（这是官方要求的语义）。
- 写请求 `401` → 重新授权一次；再 `401` 就退出，不循环。

**第 5 步 · 上传（三步，纯 `urllib`）**

1. 建附件条目（拿到 key，也是失败回滚的锚）：

```json
[{"itemType":"attachment","linkMode":"imported_file","parentItem":"<PARENT>",
  "title":"","contentType":"application/pdf","filename":"<stem>_zh.pdf",
  "md5":"<md5>","mtime":<毫秒>}]
```

响应键 **`success` 与 `successful` 都要认**（单对象创建返回 `success`，多对象返回 `successful`，官方文档两处写法不同）。

2. 要上传位：`POST /items/<ATT>/file?md5=&filename=&filesize=&mtime=` + `If-None-Match: *` → `{url, uploadKey}`；若返回 `{"exists":1}` 直接跳到第 4 步核验。
3. `POST <url>` 二进制 → `201`。
4. 注册：`POST /items/<ATT>/file?upload=<uploadKey>` + `If-None-Match: *` → `204`。
5. 覆盖场景把 `If-None-Match: *` 换成 `If-Match: <附件条目 version>`。
6. 第 2–4 步任一步失败 → `DELETE /items/<ATT>` 回滚，不留空壳附件。

**第 6 步 · 复验**

读回 `children`，要求存在该 `filename` 且 `md5` 一致；再 `GET /items/<ATT>/file` 确认 302 指向真实路径。只有"读回来对得上"才算 `attached`，不看返回码的脸色（沿用现有 `attached-unverified` 的教训）。

**第 7 步 · 记账**

- 单篇：`_work/zotero_attach.json`（保留，交付证据）。
- 总账：`_zotero/attached.csv`（工作区根，**追加**）：
  `time, stem, pdf, md5, parent_key, parent_title, attachment_key, status, skill`
- 同名 `stem` 已存在则更新该行，不重复追加。批量核对"哪一版挂上去了"看 md5。

### 4.3 状态与退出码

| status | 含义 | rc |
|---|---|---|
| `attached` | 新建并复验通过 | 0 |
| `updated` | 覆盖了同名旧附件并复验通过 | 0 |
| `unchanged` | 同名同 md5，无需动作 | 0 |
| `ambiguous` | 找到多个候选，等人选 | 3 |
| `pending` | 锚定或上传做不了，已生成待挂清单 | 2 |
| `error` | 硬错误（PDF 不存在、被拒授权、写库失败且回滚成功） | 1 |

批量时取最大值；`--strict` 把 `pending` 升级为 `rc=1`，用于"必须挂上才算交付"的场合。

### 4.4 降级：不复制副本，给"一键挂"

本地 API 与 Web API 都不可用时，**不要再逐篇复制 inbox**。Zotero 拖拽/`importFromFile` 自己会把文件复制进 `storage/`，中间副本是纯冗余。改为产出两样东西到 `_zotero/`：

1. `pending.md` —— 一张汇总表：PDF 绝对路径、`<stem>`、parent_key（若有）、`zotero://select/...`、候选条目。一次交付只一份，不再散落各稿。
2. `attach.js` —— 可整段粘进 **工具 → 开发者 → 运行 JavaScript**，一次挂全部：

```javascript
const jobs = [
  { pdf: "E:\\...\\Hollmann2022_zh.pdf", parent: "GAS4E39W" },
  // ...
];
for (const j of jobs) {
  const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, j.parent);
  await Zotero.Attachments.importFromFile({ file: j.pdf, parentItemID: item.id });
}
```

（`importFromFile` 的签名以本机 10.0.8 实测为准；若报错，退回 `pending.md` 手拖。脚本生成 JS 前先校验 parent key 在库里存在。）

只有在用户显式 `--stage` 时才把副本集中到 `_zotero/inbox/`（一处，不再逐篇）。

### 4.5 批量

```
python scripts/zotero_attach.py --batch <交付根> [--strict]
```

扫 `**/*_zh.pdf`（可 `--pattern` 改），自动配对同名 `_zh.md` 取 front matter，逐个走上面流程，最后打印一张表 + 写总账。单篇调用保持原样，向后兼容。

### 4.6 参数（保留旧的，新增的加粗）

`<PDF>`、`--md`、`--parent-key`、`--title`、`--doi`、`--auto`、`--prepare-only`、`--dry-run`、
**`--batch <dir>`**、**`--strict`**、**`--stage`**、**`--attach-title`**、**`--config`**、`--inbox`

语义调整：
- `--prepare-only` 改为"**只锚定不写库**"（仍会输出 parent_key 与链接，与现在"连查都不查"不同）。
- `--dry-run` 连本地 API 的查都做，但不产生任何写入与文件。
- `--auto` 表示"必须挂上，挂不上就 rc≠0"（沿用）。
- `--attach-title` 默认空（Zotero 显示文件名，`_zh` 已能区分原文）；要标注就传 `"中译（机翻+校验）"`。

---

## 5. 编排改动（SKILL.md / references）

1. **独立成"第 7 步：回挂 Zotero（有 PDF 时）"**，两份 SKILL.md 一视同仁，**都放进 `<workflow>` 块内**（政经那份现在在块外，必须先移进去）。理由：它是整条流水线里唯一"向外部系统写数据"的动作，混在交付段落里必然被当注脚跳过——三篇全 pending 就是证据。
2. 第 6 步产出表**加一行** `_work/zotero_attach.json`；第 7 步产出表列 `_zotero/attached.csv`。
3. 交付对话模板（dl 第 6 步「交付时对话里只回复」那段）**加一项**：Zotero 挂载状态（`attached/updated/unchanged/pending(需你授权)`）。
4. `references/zotero.md` 按 §3–§4 重写，删掉"零配置=复制副本+打印两步操作"的旧叙事，改成"本地 API 优先 + 一次授权 + 一键 JS 兜底"。
5. `README.md` 里 `zotero_attach.py` 的"两个 skill 同一份实现"要求不变：改完 `md5sum` 对齐两边。
6. 总账 `_zotero/` 落在**工作区根**（`译介工作/_zotero/`），不在本仓库内，因此不需要加进 `.gitignore`；它属于用户数据，不进版本库。

---

## 6. 落地顺序（已完成）

**阶段 1 · 脚本**（`zotero_attach.py` 重写，纯标准库）✅

- 本地 API 客户端：`server_id` 探测、读、授权、写、三步上传、回滚、复验。
- 锚定器：线索优先级 + 归一化匹配 + 唯一性判据 + 候选输出。
- 版本判定：md5 比对、`If-Match`（md5）覆盖。
- `--batch` / 总账 / 降级产物（`pending.md`、`attach.js`）。
- Web API（`pyzotero`）彻底移出主路径：现在整条链路**不用它**，`pyzotero` 从"可选依赖"变成"不需要"。

**阶段 2 · 文档与编排** ✅

- 两份 SKILL.md 同改：独立成「第 7 步」，都在 `<workflow>` 内（政经那份原先在块外，已移入）；交付回复模板加 Zotero 状态项；脚本参数表更新。
- `references/zotero.md` 重写（两份 MD5 一致）；README 流程表加第 7 步、外部依赖去掉 `pyzotero`。

**阶段 3 · 补账 + 全链路验证** ✅

- `_pfn测试` 三篇已真挂上（`U7MTFUDG` / `ANZEBKQR` / `Q9ANPHAF`），这是这条链路第一次真跑。
- 总账 `_zotero/attached.csv` 三行；单篇 `_work/zotero_attach.json` 更新为 `attached`／`unchanged`。
- 三处旧的 `_work/zotero_inbox/`（逐篇副本，共 2.1 MB）已无用途，**未删除**，留给你确认后自行清理。

---

## 7. 验收

| # | 场景 | 期望 | 实测 |
|---|---|---|---|
| 1 | 三篇批量，已授权 | 全 `attached`，rc=0；Zotero 里各出现一个 `_zh.pdf` 子附件，能打开 | ✅ 3/3 |
| 2 | 原样重跑 | 全 `unchanged`，库里不出现第二个附件 | ✅ |
| 3 | 改一版 PDF 重跑 | 一条 `updated`，**同一附件被替换**（附件数不变），md5 与新文件一致 | ✅ 附件仍 1 份，md5 对齐 |
| 4 | 给一个库里没有的标题 | `ambiguous` 或 `pending`，rc=3/2，有候选表，**未写入任何东西** | ✅ `pending` rc=2 |
| 5 | 关掉 Zotero | 走降级：`pending.md` + `attach.js`，无逐篇 inbox；粘 JS 能一次挂上 | ✅ 产物生成；JS 路径待人工验证 |
| 6 | 授权时点 Deny | rc=1，报"用户拒绝授权"，不重试第 3 次 | ⏳ 未构造 |
| 7 | 上传中途失败 | 附件条目被回滚删除，库里不留空壳 | ✅ 调试期三次 500/400 均回滚干净 |
| 8 | 两份 SKILL.md | `zotero_attach.py` 与 `zotero.md` MD5 一致；"回挂"都在 `<workflow>` 内、都在产出表里 | ✅ 两份都在第 7 步、均在块内 |
