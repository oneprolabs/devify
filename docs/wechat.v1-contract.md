# wechat.v1 上传契约

> 状态：**部分冻结**（2026-11-03）。时间语义已定稿（见 §2.1）；附件缺口与重复 origin
> 两处仍待确认，其余条款与实现一致，可作为双端对齐依据。
>
> 事实来源：`devify/chat_ingestion/package.py`、`parsing.py`、`services.py`、
> `models.py`、`devify/chat_domain/services.py`，以及 `tests/test_package_contract.py`、
> `tests/test_parsing.py`、`tests/test_uploads.py`。

## 1. 包结构

| 成员 | 必填 | 作用 |
| --- | --- | --- |
| `manifest.json` | 是 | 版本、平台、来源命名空间、时区、范围、计数、白名单快照 |
| `conversations.jsonl` | 是 | 会话：稳定 ID、标题、类型、时区、self sender |
| `messages.jsonl` | 是 | 消息：消息键、来源 ID、时间、方向、来源字段 |
| `message_parts.jsonl` | 否 | 类型化内容（文本 / 图片 / 文件 / 引用 / 转发） |
| `origins.jsonl` | 否 | 原始定位与 parser_version；缺省时按 messages 行自动记录 |
| `media/...` | 否 | 附件文件；**当前客户端不生成**，服务端按「缺失」保留 |

归档本身是 zip。任何一条契约违例都让**整批失败**，不会留下半套数据。

## 2. manifest.json

```jsonc
{
  "schema_version": "wechat.v1",
  "platform": "wechat",
  "source_namespace": "account:local-account-1",
  "timezone": "Asia/Shanghai",
  "scope": { "conversation_ids": ["group-a"] },
  "whitelist_snapshot": ["group-a", "group-b"],
  "counts": { "conversations": 1, "messages": 2 },
  "client": { "name": "AIMyChats", "version": "0.1.0" }
}
```

| 字段 | 必填 | 规则 |
| --- | --- | --- |
| `schema_version` | 是 | 必须等于 `<platform>.v1`，长度不限但需匹配 |
| `platform` | 是 | `wechat` / `whatsapp` / `line`；必须等于批次 `source_type` |
| `source_namespace` | 是 | ≤255 字符；与 `platform` 一起构成来源身份 |
| `timezone` | 否 | IANA 名称；仅作展示默认值，**不参与时间戳解释** |
| `scope.conversation_ids` | 否 | 字符串数组；必须是 `whitelist_snapshot` 的子集，且与实际会话集合完全一致 |
| `counts.conversations` / `counts.messages` | 是 | 非负整数，必须与实际行数完全一致 |
| `whitelist_snapshot` | 否 | 字符串数组 |
| `client` | 否 | 仅用于诊断，服务端不据此授权 |

`scope` / `counts` 必须是对象；传数组或标量直接拒绝（空数组也算错误）。

### 2.1 时间语义（已定稿）

- `occurred_at` 必须是**带偏移的绝对时间**：`2026-10-20T09:00:00+08:00` 或
  `2026-10-20T01:00:00Z`。
- 服务端接收后统一换算成 UTC 存储；API 输出带明确偏移（当前按服务端 `TIME_ZONE`
  渲染为 `+08:00`，仍是绝对时间，不存在歧义）。
- 无偏移的时间戳直接拒绝（422），不使用 manifest 时区、也不使用服务端时区兜底：
  任何猜测都会让导入的消息整体偏移数小时。
- manifest 的 `timezone` 仅作为展示默认值保留；**客户端按用户本地时区渲染**，
  服务端不做本地化。

## 3. JSONL 通用规则

- UTF-8（允许 BOM），一行一个 JSON 对象，空行忽略。
- 非 JSON、非对象、超过记录数上限 → 整批失败。
- 字符串字段有长度上限；整数字段不接受布尔；枚举字段必须在取值集合内。

### conversations.jsonl

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` | 二选一 | ≤255；与会话身份绑定 |
| `scope_key` | 二选一 | 无稳定 ID 时使用；同一包内两行身份相同即视为重复 |
| `title` | 否 | ≤500 |
| `kind` | 否 | `group` / `direct` / `unknown` |
| `timezone` | 否 | ≤64 |
| `self_sender_key` | 否 | ≤255 |
| `metadata` | 否 | 对象 |

### messages.jsonl

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` | 是 | 必须在本次包的会话集合内 |
| `message_key` | 否 | ≤500；缺省时由来源 ID / 定位键生成 |
| `source_message_id` | 否 | ≤255；优先作为去重身份 |
| `revision` | 否 | ≤100；参与去重键，用于区分编辑后版本 |
| `record_locator_key` | 否 | ≤255；无来源 ID 时的定位键 |
| `occurred_at` | 否 | ISO-8601 绝对时间，必须带偏移；见 §2.1 |
| `sender_key` / `sender_name` | 否 | ≤255 |
| `direction` | 否 | `incoming` / `outgoing` / `unknown` |
| `source_order` | 否 | 非负整数 |
| `record_kind` | 否 | `message` / `system` 等模型枚举 |
| `source_fields` | 否 | 对象，原样保留供排查 |

### message_parts.jsonl

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `part_key` | 是 | ≤255；同一消息内唯一 |
| `kind` | 否 | `text` / `image` / `video` / `audio` / `file` / … |
| `ordinal` | 否 | 非负整数，缺省 0 |
| `parent_part_key` | 否 | 父 part 必须先出现 |
| `upload_item_path` | 否 | 指向包内文件；不存在时媒体 part 降级为 `missing` |
| `binding_state` | 否 | 显式覆盖推导结果 |

### origins.jsonl

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `locator_key` | 是 | ≤255 |
| `parser_version` | 否 | 缺省取 manifest 的 `schema_version` |
| `upload_item_path` | 否 | 缺省指向 `messages.jsonl`；必须存在于包内 |

## 4. 幂等与去重

- **批次幂等键**：`(space, uploaded_by, idempotency_key)`。重复创建返回原批次；
  同一键配不同 `source_type` 视为冲突。
- **会话**：`(space, platform, source_namespace, 源会话 ID 或 scope_key)`。
- **消息**：会话内 `message_key`；无 `message_key` 时按
  `src:<来源 ID>[@<revision>]`，无来源 ID 时按 `loc:<定位键>+<文件哈希>`。
- **重复导入**只追加 `MessageOrigin` 与缺失的 part，不新增消息；批次的
  `duplicate_count` 反映命中数，`messages.jsonl` 上传项标为 `duplicate`。
- 同一包内重复的 `message_key` 计为 duplicate，不报错；重复的会话记录报错。

## 5. 状态机

```text
created ──> uploading ──> processing ──> completed
   │            │             └───────> failed ──> uploading（替换归档后重试）
   └────────────┴──────────────────────> cancelled（终态）
```

- `completed` / `cancelled` 是终态；重复 `complete` 幂等返回当前状态。
- 归档上传后校验声明的 SHA-256 与大小（仅首次上传时比对），失败批次可用修正包重传。
- 解析失败写入 `error_message`，错误文案是给用户看的原文，不再二次包装。

## 6. HTTP 语义

| 场景 | 状态码 |
| --- | --- |
| 创建 / 读取 / 幂等重复创建 | 201 / 200 |
| 归档上传成功、`complete` 已受理（异步） | 200 / 202 |
| 归档缺失或参数非法 | 400 |
| 非成员 | 404 |
| 成员但无写权限 | 403 |
| 归档空间写操作 | 409 |
| 状态跃迁非法、归档大小/校验和不符 | 409 |
| 包契约违例（整批失败） | 422 |
| 超出归档或展开大小上限 | 413 |

## 7. 限额（可用 settings 覆盖）

| 项 | 默认 |
| --- | --- |
| 单个归档 | 512 MB（`CHAT_UPLOAD_MAX_ARCHIVE_BYTES`） |
| 压缩包内单成员 | 256 MB（`CHAT_IMPORT_MAX_FILE_BYTES`） |
| 压缩包内总大小 | 2 GB（`CHAT_IMPORT_MAX_TOTAL_BYTES`） |
| 展开后总大小 | 2 GB（`CHAT_UPLOAD_MAX_EXPANDED_BYTES`） |
| 成员数 | 5000（`CHAT_IMPORT_MAX_MEMBERS`） |
| 单个 JSONL 记录数 | 50000（`CHAT_IMPORT_MAX_RECORDS`） |

## 8. 待决策（冻结前必须确认）

1. ~~无偏移时间戳的语义~~ **已决定（2026-11-03）**：统一使用绝对时间戳，客户端负责
   转成本地时间展示。实现：`parse_occurred_at` 拒绝无偏移值，服务端不再回退到
   manifest 或服务端时区；测试
   `test_naive_timestamp_is_rejected_whatever_the_manifest_says`。
2. **附件缺口的表达**。当前客户端不产 `media/`，服务端把媒体 part 记为
   `binding_state=missing` 并继续导入。需要确认：首版是否允许「只有文本、附件缺失」
   视为成功导入，还是必须有附件才算完整（影响客户端打包与验收口径）。
3. **重复上传的 origin 保留**。当前同一消息重复导入会追加一条 origin。多人重复上传
   同一段聊天时，是保留全部来源（可追溯，但行数增长）还是按来源账号只保留最新一次，
   需要确定后再补去重策略。

## 9. 双端职责

| 能力 | 客户端 | 服务端 |
| --- | --- | --- |
| 读取与解密 | 只读本机库，白名单在 Rust 层强制 | 不接收数据库、密钥、解密缓存 |
| 范围选择 | 账号 / 会话 / 日期 / 逐条 | 只信任批次与登录身份，不信任 manifest 授权字段 |
| 规范化 | 产出 `wechat.v1` 包与预览指纹 | 整包校验，任一不一致整批失败 |
| 时间 | 产出带偏移的绝对时间戳，按用户本地时区展示 | 统一换算 UTC 存储，输出带偏移；不做本地化 |
| 去重 | 生成稳定 `message_key` / `revision` | 按空间 + 会话 + 消息键去重 |
| 分析 | 只做本机预览 | 正式 Note / Event / Report / 主题 / 问答 |
