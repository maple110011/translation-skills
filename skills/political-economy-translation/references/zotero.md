# 把译文 PDF 挂回 Zotero 条目

多数文献是从 Zotero 文献库里拖出来的。Windows 下 Zotero 会把 PDF 放在
`C:\WINDOWS\TEMP\Zotero\drag\`，这个临时目录**会被清空**：译到一半或交付时
原文 PDF 常常已经不在，但文献条目还在库里。所以译文 PDF 出完、验收通过后，
应该回到那个条目下面，而不是散落在工作区。

两个翻译 skill 共用 `scripts/zotero_attach.py` 的同一份实现。

---

## 一、在流程里的位置

第 6 步交付之后、`verify_pdf.py` 通过之后才挂。挂的是一个**已验收的** PDF，
不是中间产物。公众号版、Markdown 译文与 PDF 是三份独立产物，只有 PDF 进 Zotero。

```bash
python scripts/zotero_attach.py <stem>_zh.pdf --md <stem>_zh.md
```

脚本会从译文的 YAML front matter 取 `title` / `title_en` / `doi` / `citekey`
作为父条目线索；也可显式给 `--title`、`--doi`、`--parent-key`。

---

## 二、零配置：待挂副本 + 操作指引（默认）

本机没有 Zotero API key 时，脚本**不会失败**，而是：

1. 把 PDF 复制到 `<PDF同级>/_work/zotero_inbox/`（可用 `--inbox` 改），
   同名且 sha256 一致则复用，不重复复制；
2. 写 `_work/zotero_attach.json`：源路径、副本路径、sha256、标题/DOI、
   父条目 key（若给）、`zotero://select/...` 链接、生成时间、未自动上传的原因；
3. 打印在 Zotero 里选中条目后的两步操作：

> 右键 → **添加附件 → 添加文件副本**（Attach Stored Copy of File）→ 选该 PDF；
> 或把 PDF 直接拖到条目上，Zotero 会自动建成子附件。

若给了 `--parent-key`，还会打印 `zotero://select/library/items/<KEY>`，
在浏览器/系统里打开可直接跳到该条目。

**强制只用这条路**：`--prepare-only`。**只看不写**：`--dry-run`。

---

## 三、配置后：自动创建子附件

需要 Zotero Web API：

1. 在 <https://www.zotero.org/settings/keys> 建一个 API key，勾「Allow library access」（写入还要勾 write）；
2. 用户 ID 在 Zotero 设置的 Feeds/API 页（`Use this user ID for API calls`）；
3. 安装可选依赖 `pip install pyzotero`（**只有自动上传这一步需要**，其余流程全标准库）；
4. 配置任选其一：

```bash
set ZOTERO_API_KEY=xxxxxxxx
set ZOTERO_USER_ID=1234567
```

或写 `~/.workbuddy/zotero.json`：

```json
{"api_key": "xxxxxxxx", "user_id": "1234567", "library_type": "user", "inbox": ""}
```

配置好后直接跑上面的命令即可；`--auto` 表示**必须**自动上传，做不到就返回 1。

自动流程：按 DOI（优先）或标题做 quick search 找父条目 → 检查该条目下是否已有
同名附件（有则跳过，幂等）→ 把 PDF 复制到短的无空格临时名 → 用
`attachment_both` 建子附件并上传 → 重新拉一次子项列表复验 → 打印 `zotero://select/...`。

**Windows 长路径坑**：路径里带空格/中文时 `attachment_simple` 可能不抛异常、
只返回空的 `success` 列表。脚本先把文件复制成 `zot_upload.pdf` 再上传，并显式
检查 `failure` / `success`，不把"看起来没报错"当成成功。

---

## 四、安全约束

- **绝不直接读写 `zotero.sqlite`**：Zotero 运行时数据库被锁，手工插 item 会破坏同步，
  也可能损坏整个文献库。写入只走官方 Web API 或 Zotero 自己的界面。
- 不移动、不删除、不覆盖用户文件；只往 `zotero_inbox/` 复制一份副本。
- 同名附件已存在就跳过，不重复挂、不覆盖原附件。
- `--dry-run` 不复制、不上传、不写清单。

---

## 五、版本与故障排查

| 现象 | 原因 / 处理 |
|---|---|
| 「未配置 ZOTERO_API_KEY / ZOTERO_USER_ID」 | 没配置就走零配置待挂，这是正常路径，不是错误 |
| 「没装 pyzotero」 | `pip install pyzotero`，或继续用待挂副本手动挂 |
| 「没找到父条目」 | 给 `--parent-key`（Zotero 里选中条目，右键可复制 URI/Key），或补 `--title` / `--doi` |
| 上传返回成功但复验没看到子项 | 同步延迟或权限问题，等同步完在 Zotero 里看一眼；脚本会返回 `attached-unverified` |
| 想用 Zotero 本地 API 写 | Zotero 7 的本地 API **只读**；写支持要 Zotero 10 且需弹窗授权。本脚本走 Web API，不依赖本地端口 |
| Zotero 没运行 / 本地端口不通 | 不影响 Web API 路径；本地 API 只在 Zotero 桌面端开启「Allow other applications…」后才可用 |

清单 `_work/zotero_attach.json` 随交付一起留着，日后要核对"挂的是哪一版 PDF"
看 `sha256` 即可；重新出 PDF 后重跑脚本会生成新副本与新 sha256。
