# 多人上传并集模型设计说明

- 状态：设计已定稿；S1（媒体内容寻址）、S2（会话归一 + 消息指纹/别名）、S3（撤回与孤儿消息）已实现，S4 待实现
- 日期：2026-11-06
- 涉及：`chat_ingestion` / `chat_domain` / `chat_analysis` / `chat_sources`
- 相关：`docs/wechat.v1-contract.md`（包契约）、`docs/wechat-devify-ingestion-design.md`（导入方向）

## 1. 目标

1. **并集**：同一空间内多个人上传同一个群，数据汇聚成一个会话全集，交集不重复落库、不重复调用模型。
2. **归属**：保留每个上传者贡献了哪些消息。
3. **撤回安全**：某个上传者删除自己的上传，不得删除或破坏其他人上传的记录。

## 2. 现状与阻塞

| # | 阻塞 | 位置 | 实测影响 |
|---|---|---|---|
| B1 | 会话身份含上传者账号 | `chat_domain/services.py:33` `build_identity_key` | 两人两个 `Conversation`，同一群永远无法汇聚 |
| B2 | 消息键跨账号不可比 | 客户端 `devify-desktop/src-tauri/src/lib.rs:1585/1601` | 实测 `srv=0 / src=100%`，`src:<本地ID>` 各账号不同 |
| B3 | 分析单元是上传窗口 | `AnalysisJob.request_key`、Note key `job:{uuid}:{seq}`（`chat_analysis/execution.py:346`） | 窗口不完全相同就重跑模型、重写一份 Note |
| B4 | 媒体挂在批次归档里 | `chat_domain/views.py:402` 直接读 `item.batch` 的 zip | 删任一批次，别人同一条消息的图片 404 |
| B5 | 没有删除/撤回接口 | `chat_ingestion/urls.py` | 需求 3 目前无可执行入口 |

盘点数据（`manage.py audit_chat_union`，开发库全量）：

```
conversations=4  messages=17475  origins=21929  batches=36  upload_items=255
duplicate_conversation_groups=0        # 每个空间只有 1 个上传者，尚未触发合并
message_keys  srv=0 (0.0%)  src=17475 (100.0%)  loc=0 (0.0%)
messages_with_multiple_uploaders=0
archives total_bytes=1802408  media_rows=88  media_total_bytes=598111
unique_media_digests=27  media_rows_per_digest=3.26
```

结论：**消息级稳定键是 P1 的核心**，不是增强项；媒体重复存储已经发生（3.26 倍）。

## 3. 目标模型

### 3.1 身份层

**会话**

```
identity_key = platform : source_conversation_id
```

- 账号（`source_namespace`）降级为来源元数据：`Conversation.source_namespace` 保留“首次来源”，其余账号写入 `metadata.source_namespaces` 列表。
- 源会话 ID（群 chatroom id / 私聊 wxid）跨账号稳定，可直接合并。
- 无 `source_conversation_id` 的包（`scope_key` 模式）保持现有行为，不参与跨账号合并。

**消息（canonical key + alias）**

```
canonical   = 首次创建该消息的客户端键（srv:<id> 或 src:<local_id>）
fingerprint = fp.v1 | occurred_at(秒) | sender_key | record_kind
            | 文本拼接 | 媒体数 | 媒体摘要
alias       = (conversation, source_namespace, alias_key) -> message
```

- 新表 `MessageAlias`，唯一键 `(conversation, source_namespace, alias_key)`；`Message.content_fingerprint` 带索引。
- 摄入顺序：先按 alias 命中 → 再按 `message_key` 命中 → 都没有才新建；命中后登记本次的 alias。
- 指纹在 parts 解析完成后统一计算（文本与媒体摘要此时才齐）；同一会话内指纹相同、且分属不同批次的消息合并为一行，`srv:` 消息优先作为合并目标。
- `fingerprint` **不含 direction**（自己发的消息在对方导出里是 incoming）、不含展示名（各账号备注不同）；**无时间戳**或**无可识别内容**（空文本且无媒体）的消息不计算指纹，避免误合并。
- 合并时 origin、part、`NoteEvidence`、`EventEvidence` 全部改挂到存活消息，来源归属不丢。

### 3.2 归属层

- `MessageOrigin → UploadItem → UploadBatch.uploaded_by` 已是归属链，重复上传只追加 origin，无需改模型。
- `MessagePart.upload_item` 目前会被后一次上传覆盖（`chat_domain/services.py:313`），改为**不覆盖已绑定值**，媒体改走内容寻址后不再依赖批次。
- `MessagePart` 新增 `media_sha256` / `media_content_type`，用于跨批次引用同一份媒体。

### 3.3 媒体存储层

- 新目录 `CHAT_MEDIA_DIR`（默认 `<repo>/chat_media`），按 `<sha256>` 单份存放，复用 `chat_domain/avatars.py` 的写法。
- 解析时把 `media/*` 成员按摘要落盘；`MessagePart.media_sha256` 记录摘要。
- 新增 `GET /v1/spaces/{id}/chat-media/{sha256}`；`MessageMediaSerializer` 在有 `media_sha256` 时使用新地址，否则回退旧的 `/media/{upload_item_id}`，前端无需立即改。
- 存量媒体通过 `backfill_chat_media` 命令从归档中抽取；在该命令完成前，旧消息仍走回退地址。

### 3.4 分析层

- 引入 `AnalysisChunk(conversation, bucket_index, digest, state, lease...)`，`bucket_index = ingest_seq // 200`，唯一键 `(conversation, bucket_index)`。
- `AnalysisJob` 语义改为“确保 `[start_seq, end_seq]` 覆盖的桶都已完成”；真正的模型调用与 Note 写入以桶为单位抢占（行锁 + 租约）。
- 自动 Note 的 key 改为 `chunk:{conversation}:{bucket}`，两个上传者覆盖同一桶 → 命中同一行，只跑一次模型。
- 事件建议仍按 `event_key` 归并，不变。

## 4. 删除语义：撤回贡献

```
DELETE /api/v1/chat/uploads/{id}     # 上传者本人 / 空间管理员
```

事务内：

1. 校验权限与批次归属；写审计 `chat.upload_deleted`。
2. 删除本批次的 `MessageOrigin`（只删自己的）。
3. 受影响消息按剩余 origin 分类：
   - `> 0`：消息保留；`MessagePart.media_sha256` 保证媒体仍可访问。
   - `= 0`：`Message.orphaned_at = now()`，从后续分析、问答、报告取数中排除。
4. 删除批次归档文件、`UploadItem` 与批次行，释放配额；审计 `chat.upload_revoked` 保留消息数、孤儿数与 origin 数。
5. 会话无任何消息时保留空会话（可后续归档），不做级联删除。
6. 重新上传命中同一消息时清除 `orphaned_at`，该消息重新进入分析与问答。

延迟清理命令 `purge_orphaned_messages --days 30 --apply`（默认 dry-run）物理删除超过保留期的 orphaned 消息，连带 CASCADE parts/origins/aliases/证据；Note/Event 不重算，沿用“允许删除 + 快照保底”的既有决策（`ReportItemSource` 的 `SET_NULL` + snapshot）。孤儿消息不进入新的分析窗口，也不进入问答上下文（`question_context` 过滤 `orphaned_at`）。

**语义边界**：A、B 都上传了同一条消息时，A 撤回后 B 仍能看到——这是并集模型的必然结果，不是缺陷。若产品需要“A 撤回后对 A 也不可见”，那属于按贡献者的可见性过滤，另立需求。

## 5. 数据迁移

分三步，前两步可独立回滚：

1. **schema**：新增 `MessageAlias`、`Message.content_fingerprint`、`Message.orphaned_at`、`MessagePart.media_sha256/media_content_type`。纯增量，不改既有列。
2. **身份重写**：迁移 `0004` 把 `Conversation.identity_key` 重算为 `platform:conversation_id`，并把同空间内冲突的会话合并（保留最早 id，消息按 `ingest_seq` 续号迁移，冲突的 `message_key` 改为 `legacy:<旧会话>:<键>` 并登记 alias）。**已实现并已在开发库执行**。
3. **指纹回填**：`merge_chat_messages` 命令按会话计算指纹并合并重复消息（含 NoteEvidence 的 `reference_key` 重算与去重），默认 dry-run。**已实现**；开发库回填 17475 条、合并 63 条重复。

合并消息时注意：

- `MessageOrigin` 直接改 `message_id`（唯一键是 `(upload_item, locator_key, parser_version)`，不冲突）。
- `EventEvidence` 改 `message_id`，唯一键 `(event, message)` 需要 `ignore_conflicts`。
- `NoteEvidence.reference_key = "<message>:<part|whole>"`，改完必须重算；与目标已有证据重复时删掉冗余行。
- 合并后保留 `srv:` 消息优先，其次保留最早创建的一条。

## 6. 接口变更

- 新增 `DELETE /api/v1/chat/uploads/{id}`。
- `UploadBatchSerializer` 增加 `uploader`（昵称/邮箱）与 `contribution` 统计，供前端展示“这是谁传的”。
- 消息序列化增加 `sources`（贡献者列表），用于工作台标注来源。
- `MessageMediaSerializer` 在 `media_sha256` 存在时返回新地址。

## 7. 分阶段任务

| 阶段 | 内容 | 验收 |
|---|---|---|
| S1 | 媒体内容寻址：`CHAT_MEDIA_DIR`、解析落盘、新读取接口、`backfill_chat_media` | 删除批次后，其他批次引用同一张图仍可访问 **（已实现）** |
| S2 | 会话归一 + 消息指纹 + `MessageAlias` + `merge_chat_messages` 命令 | 两个账号先后上传同一个群：`Conversation` 1 条、消息并集、`duplicate_count` 正确 **（已实现）** |
| S3 | 删除/撤回接口 + `orphaned` 状态 + 延迟清理任务 | A 撤回后 B 的消息与媒体完整；`orphaned` 消息不再进入问答/报告 **（已实现）** |
| S4 | `AnalysisChunk` 桶级分析 + Note key 改 `chunk:` | 两组重叠上传只调用一次模型、只产生一份 Note |

S1 → S2 可并行，S3 依赖 S1，S4 依赖 S2。

## 8. 风险与开放问题

1. **指纹碰撞**：同一发送者同一秒发两条相同文本会得到相同指纹；已用出现序号兜底，但仍可能误合并，需要埋点统计命中率。
2. **sender_key 跨账号一致性**：依赖客户端上送 wxid 而非昵称；若某平台使用展示名，需按平台单独定义。
3. **不同账号的可见范围不同**：并集会让 A 看到 B 才有的消息（例如 B 在群里但 A 已退群）。这是产品预期内的“全集”，但需要在界面上标注来源。
4. **存量合并不可逆**：迁移前必须导出候选清单与计数，并支持 `--dry-run`。
5. **配额语义**：撤回后释放归档配额，但并集消息仍占用数据库与媒体空间，计量口径需要产品确认。

## 附录：盘点输出

```
# chat union audit space=all
conversations=4 messages=17475 origins=21929 batches=36 upload_items=255
duplicate_conversation_groups=0 conversations_in_groups=0
message_keys_shared_across_conversations=0 message_rows_to_collapse=0 origins_kept_on_merge=0
messages_with_multiple_uploaders=0
message_keys srv=0 (0.0%) src=17475 (100.0%) loc=0 (0.0%) other=0
  space=46 uploaders=1 batches=35
  space=945 uploaders=1 batches=1
archives total_bytes=1802408 media_rows=88 media_total_bytes=598111 unique_media_digests=27
media_avg_bytes_per_row=6796 media_rows_per_digest=3.26
```
