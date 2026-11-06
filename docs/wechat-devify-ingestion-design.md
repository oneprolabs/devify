# WeChat → Devify 采集与事件工作台设计

## 结论

`wechat-devify-tauri` 是本机采集器和上传客户端，`devify` 是远端的聊天资料库、分析服务、事件工作台和报告出口。

**多渠道与空间补充提案**：同一个桌面客户端登录一次 Devify，在客户端内按需扩展微信、WhatsApp、LINE 等本地采集器，统一规范化并上传；用户每次选择目标空间，不需要为每个渠道或空间单独申请 Devify token。所有本地聊天软件都由客户端读取、处理和上报，Devify 不直接读取本地聊天软件数据；邮箱仍由 Devify 服务端接收。一个登录会话在技术上可能包含 access token 与 refresh token；渠道自身的本机读取权限、密钥或授权另行处理，不上传至 Devify。目前仅有微信本地采集，Devify 上传和其他渠道均待实现，WhatsApp/LINE 的实际可用性及授权限制须先验证。

本文下文如出现旧的 `tenant` / `tenant_id` 术语，实施时统一以空间 TODO 的 `space` / `space_id` 为准，不引入第二套隔离边界。上传或复制到空间的数据对空间有效成员可见；个人空间默认仅本人。去重必须隔离空间，不能因同源数据合并而扩大访问范围。

实施清单见 [`docs/wechat-devify-space-todo.md`](wechat-devify-space-todo.md)，覆盖空间权限、邮箱 AI 总结、多渠道来源适配、微信上传和后续 WhatsApp/LINE 扩展。

Tauri 不上传微信数据库、密钥或本机解密缓存，也不把本地 AI 总结当作服务端事实。它只在用户明确选择的白名单、会话和时间范围内读取微信记录，将记录规范化为可幂等导入的数据包，上传到 Devify。Devify 保存来源证据，生成 `Note`，组织 `Event`，再生成冻结的 `Report`。

```text
微信 4.x 本地数据库
        │ 只读；Full Disk Access + 用户提供的 key
        ▼
wechat-devify-tauri
  扫描 / 解密 / 白名单 / 选择范围 / 规范化 / 上传队列
        │ HTTPS；用户主动触发；可恢复、可重试
        ▼
Devify API
  upload_batch / upload_item / source records
        ▼
Devify 数据与任务层
  conversation → message → note → event → report
        ▼
Devify Web
  收件与导入 → 整理 → 持续事件 → 报告
```

## 1. 三份材料分别解决什么问题

### `chat-analysis`

这是服务端的持久化和证据模型，重点是“以后能不能回到原文、能不能解释为什么这样归类”。其中最重要的分层是：

- `conversation` / `message` / `message_part` / `message_origin`：不可变来源层。
- `note` / `note_message`：一段阶段性摘要及其原文依据。Note 可以暂时没有事件归属。
- `event` / `event_note` / `event_tag`：持续跟踪的业务对象；一个事件可以跨会话、跨多段 Note。
- `report` / `report_section` / `report_item` / `report_item_source`：某次生成时的冻结结果，不随之后的事件移归而改写。
- `upload_batch` / `upload_item` / `analysis_job`：导入和分析的可恢复任务状态。

`v0.19` 是逻辑设计，不是已经迁移到 Devify 的生产模型。它已经验证了幂等、消息来源、人工归属保护和报告快照这些关键语义，但没有实现上传 API、数据库迁移或任务调度。

### `event-workspace-prototype`

这是人审交互模型，重点是“人如何从一批消息整理出可追踪的事情”：

1. **采集**：看来源、时间覆盖、条数、附件和历史缺口。
2. **整理**：从消息中保留请求、承诺、决定、进展、结果和不确定性，并展示保留/排除理由。
3. **持续事件**：给事件设置状态、标签、关注方式和下一步。
4. **关联审查**：对“同一事件、有关联、保持独立、待确认”做显式判断。

它是脱敏的离线原型，数据和修改保存在浏览器 `localStorage`，不代表服务端已经有这些能力。它的“事件”数据应作为 Web 工作台的交互参考，不直接复制为 Tauri 的本地数据结构。

### `wechat-devify-tauri`

它已经有本机采集链路：

- 扫描微信账号和数据库、导入并验证 key、解密到应用自己的缓存。
- 在 Rust 查询层执行白名单过滤，提供会话、分页消息和搜索。
- 在本机进行消息选择、规则整理、Agent 总结和总结历史保存。
- 可通过本地 MCP/HTTP 只读服务供本机 Agent 使用。
- 当前 Devify 交付主要是 SMTP 日报，不是聊天资料上传 API。

因此 Tauri 目前拥有“采集前半段”，缺少“上传到 Devify”的网络客户端和上传状态界面；Devify 目前也没有对应的聊天导入领域模块。

## 2. 责任边界

| 能力 | Tauri | Devify |
| --- | --- | --- |
| 读取微信数据库 | 负责；只读、只在本机 | 不负责，也不接收微信 key |
| 白名单和范围限制 | 第一层强制执行，位于 Rust | 第二层按用户和上传批次校验 |
| 会话/消息规范化 | 负责产生稳定的来源字段 | 负责校验、去重和持久化 |
| 原始来源定位 | 生成文件/数组位置、源消息 ID、顺序等 metadata | 保存 `message_origin`，支持反查 |
| 摘要 Note | 可做本地预览，不作为服务端事实 | 正式生成、编辑、保存和关联原文 |
| 事件归属 | 仅可显示上传前预览 | 服务端建议、人工确认、持续追踪 |
| 报告 | 可保留本地旧版总结 | 正式生成、冻结快照、历史版本 |
| 上传重试 | 队列、断点、进度、重试 | 幂等接收、批次状态和错误信息 |
| 凭据 | API token 放系统凭据存储 | 认证、授权、限流、审计 |

### 空间归属与可见性

这里必须拆开两个维度：

- **空间归属**回答“数据属于哪一个空间”。每个用户默认有一个个人空间，可以只使用个人空间，也可以加入多个团队空间；聊天来源、Note、Event 和 Report 都必须属于一个空间。
- **可见性**由空间决定：上传或复制到空间的数据对空间所有有效成员可见；个人空间默认只有本人。首版不提供空间内仅上传者可见的数据，也不等于互联网公开。
- **删除权**属于资源上传者和空间管理员；`maintainer` 是空间管理员，可以删除空间数据，`owner` 继承 `maintainer` 的全部权限。全局 `admin` 读取或删除空间业务数据前必须先接管空间，并记录审计；无上传者数据的处理待确认。
- **真正公开**（跨空间或匿名访问）不适用于原始聊天消息。以后如需公开，只能从已脱敏的 Note/Report 生成独立的发布快照，经过人工确认，不改变原始来源的权限。

上传时用户选择目标空间，但这只是请求意图，不是授权依据。服务端必须从认证身份校验空间成员关系、角色和上传权限，并将最终的 `space_id` 和上传者写入批次；不能信任 manifest 中的用户 ID、空间 ID 或计数。

权限分为全局 `admin` 与空间 `owner`、`maintainer`、`user`、`guest`；`maintainer` 是空间管理员，`owner` 继承 `maintainer` 的全部权限并额外负责空间所有权和生命周期。建议 `user` 可上传和创建分析任务，`guest` 可读取空间数据。个人空间可以只有 `owner`，团队空间再启用成员协作。

权限沿来源向下继承：

- `upload_batch` 记录 `space_id` 和上传者，空间成员关系是数据访问边界。
- `conversation` 继承批次的空间归属；去重除来源身份外还须隔离空间，不能跨空间合并。
- `message`、`message_part`、`message_origin` 不单独扩大权限，查询时沿 `conversation` / `upload_batch` 做空间成员过滤。
- Note、Event、Report 及其来源必须属于同一空间；访问时检查有效成员关系，不能跨空间引用导致泄露。
- 任何查询、下载附件、启动分析和事件关联都必须先通过当前空间成员关系检查，不能只按对象 ID 查库。

因此，个人上传属于个人空间，团队上传属于团队空间；跨空间操作只复制资源，不修改源空间或目标空间属性，复制出的资源对目标空间有效成员可见。复制出的资源上传者归属、附件和衍生结果处理须在实现前明确。

### 关键边界

- Tauri 不上传 `.db`、`-wal`、解密 key、微信安装包、完整解密缓存或本机 Agent 凭据。
- Tauri 不上传白名单之外的会话，即使 UI 请求了它们；Rust 查询层必须是最终门禁。
- Devify 不信任客户端传来的用户 ID、空间 ID、范围计数或 `source_namespace`，全部从认证用户和服务端校验结果派生/校验。
- Tauri 的本地总结和 Devify 的 Note 是两个不同层次：前者是本机产物，后者必须能回到 Devify 保存的消息来源。
- 用户点击“上传”意味着聊天内容离开本机；客户端必须在上传前显示来源、会话、日期和消息数量，并在 Devify 侧保存批次记录。

## 3. 上传对象与格式

### 推荐的 v1 传输方式

首版使用**规范化压缩数据包**，而不是逐条 API 写入。原因是微信读取是本机重型操作，压缩包更容易展示确认摘要、计算哈希、断点重试和保留导入快照。

建议包结构：

```text
manifest.json
conversations.jsonl
messages.jsonl
message_parts.jsonl
origins.jsonl
media/                       # 可选；仅用户选择上传附件时存在
```

`manifest.json` 至少包含：

```json
{
  "schema_version": "wechat.v1",
  "platform": "wechat",
  "source_namespace": "account:<stable-local-account-id>",
  "timezone": "Asia/Shanghai",
  "scope": {
    "conversation_ids": ["group-a"],
    "since": "2026-10-20T00:00:00+08:00",
    "until": "2026-10-27T00:00:00+08:00"
  },
  "whitelist_snapshot": ["group-a"],
  "counts": {"conversations": 1, "messages": 120},
  "client": {"name": "Wechatify", "version": "0.0.1"},
  "idempotency_key": "<client-generated-key>"
}
```

目标空间放在创建批次的 API 请求中，而不是由 manifest 决定：

```json
{
  "space_id": "<space-selected-by-user>",
  "platform": "wechat",
  "idempotency_key": "<client-generated-key>"
}
```

其中 `space_id` 只表示用户在客户端选择的目标，服务端必须检查当前用户是否属于该空间以及是否有上传权限；响应中的空间和上传者归属才是最终结果。个人空间也使用同一套协议，不另设个人上传旁路。

### 规范化 JSONL 字段（`wechat.v1`）

四个 JSONL 文件均为“每行一个 JSON 对象、UTF-8 编码”。`manifest.json` 的 `counts` 必须与 `conversations.jsonl` / `messages.jsonl` 的实际记录数一致，否则整个批次失败；`message_parts.jsonl` 与 `origins.jsonl` 可省略。

`conversations.jsonl`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` | 二选一 | 来源会话稳定 ID，写入 `source_conversation_id` |
| `scope_key` | 二选一 | 来源无稳定会话 ID 时使用的确定性范围键 |
| `title` | 否 | 展示名，可变化，不参与会话去重 |
| `kind` | 否 | `group` / `direct` / `unknown` |
| `timezone` | 否 | IANA 时区；缺省用 manifest 或服务端默认 |
| `self_sender_key` | 否 | 本机账号在来源中的稳定发送人标识 |
| `metadata` | 否 | 渠道扩展对象 |

`messages.jsonl`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` | 是 | 引用本包内的会话，必须是 `conversation_id` 或 `scope_key` |
| `message_key` | 否 | 来源生成的稳定消息键；缺省时服务端按 `source_message_id` 生成 |
| `source_message_id` | 否 | 来源消息 ID，大整数必须用字符串 |
| `revision` | 否 | 编辑/撤回等来源修订标识，参与消息键 |
| `record_kind` | 否 | `message` / `system` / `edit` / `revoke` / `unknown` |
| `sender_key` / `sender_name` | 否 | 发送人稳定标识和展示名 |
| `direction` | 否 | `incoming` / `outgoing` / `unknown` |
| `occurred_at` | 否 | ISO-8601；无时区时按 manifest 时区解释 |
| `source_order` | 否 | 来源内排序号 |
| `target_source_id` / `relation_kind` | 否 | 引用、编辑或撤回的目标消息 |
| `source_fields` | 否 | 渠道原始类型等受版本控制字段 |
| `normalization_state` | 否 | `waiting` / `ready` / `partial` / `failed` |

`message_parts.jsonl`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` / `message_key` | 是 | 引用本包内已出现的消息 |
| `part_key` | 是 | 消息内部稳定的部件键 |
| `kind` | 是 | `text` / `image` / `video` / `audio` / `file` / `quote` / `forwarded_item` / `unknown` |
| `ordinal` | 否 | 部件顺序 |
| `text` | 否 | 文本内容，仅 `text` / `quote` 等类型使用 |
| `parent_part_key` | 否 | 父部件，父部件必须先于子部件出现 |
| `upload_item_path` | 否 | 指向包内文件（通常是 `media/...`）；文件不存在时保留为“未上传”缺口 |
| `binding_state` | 否 | `available` / `missing` / `omitted` / `unsupported` / `unresolved` |
| `source_locator` / `source_header` | 否 | 原始定位和头部信息 |

`origins.jsonl`：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `conversation_id` / `message_key` | 是 | 引用本包内已出现的消息 |
| `locator_key` | 是 | 同一文件内的原始位置键 |
| `parser_version` | 否 | 缺省为 `wechat.v1` |
| `upload_item_path` | 否 | 来源文件，缺省为 `messages.jsonl` |
| `record_locator` | 否 | 行号、JSON Pointer 等原始定位 |

服务端会为每条消息自动记录一条 `messages.jsonl` 行级来源；重复导入同一范围只新增来源、不新增消息。manifest 中的 `space_id`、用户 ID 等字段不参与授权，目标空间和上传者始终取自批次。

微信的大整数消息 ID必须保持字符串，不能先转换成 JavaScript `Number`。`message_key` 由 Tauri 生成并在服务端再次规范化；`source_message_id`、`source_order`、发生时间、发送人稳定标识和消息类型都应保留。正文不应复制原始 XML，图片/文件/引用等内容用 `message_part` 的类型化字段表达。

附件遵循显式选择：v1 可以只上传文字和结构化消息，附件作为可选的 `media/` 条目上传；未上传的附件必须显示为“存在但未上传”，不能被分析器当作已读取内容。

### 不采用的方式

- **直接上传微信数据库**：泄露范围不可控，服务端无法可靠解释来源，也会把平台私有格式和 key 带出本机。
- **只上传 Tauri 生成的 Markdown 总结**：丢失原始消息、时间和可追溯关系，无法支持后续事件移归。
- **逐条实时写入作为首版协议**：弱化用户确认、导入快照和断点恢复；可以作为后续增量同步协议。

## 4. Devify API 契约（提案）

路径沿用 Devify 的 `/api/v1/` 约定；具体命名在实现前以 OpenAPI 定稿。

### 创建导入批次

`POST /api/v1/chat/uploads`

请求包含目标空间、平台、客户端版本、来源命名空间、用户选择的会话/时间范围、消息计数、压缩包大小和幂等键。服务端先校验当前用户对目标空间的上传权限，再返回 `upload_batch_id`、允许的最大分片大小和上传状态。用户身份和空间归属由服务端确定，不接受客户端覆盖。

### 上传数据包

`PUT /api/v1/chat/uploads/{batch_id}/archive`

- 支持分片或可恢复上传。
- 服务端计算 SHA-256，不信任客户端哈希。
- 上传未完成前不创建可见的 `conversation`、`message` 或 `event`。
- 重复提交相同幂等键返回原批次，不重复导入；幂等键至少在 `(space_id, uploaded_by_user_id, idempotency_key)` 范围内唯一。

### 完成并校验

`POST /api/v1/chat/uploads/{batch_id}/complete`

服务端检查：压缩包路径安全、manifest 与文件内容一致、空间与用户归属、schema 版本、消息 ID 格式、会话范围、重复记录和附件引用。完成后进入 `queued` / `processing`，返回每个文件项的处理状态。

### 查询导入进度

`GET /api/v1/chat/uploads/{batch_id}`

返回当前用户在目标空间内可见的 `upload_batch` 整体状态、`upload_item` 的阶段、计数、缺口和可重试错误。Tauri 的上传队列以该接口为最终状态，不能只依赖本地 HTTP 成功。

### 启动分析

`POST /api/v1/chat/analysis-jobs`

请求引用已完成的批次和消息窗口，可选择“只提取 Note”“提取并建议事件关联”或“生成报告”。分析任务使用 `analysis_job` 的 checkpoint、lease 和 fencing token，自动重试不得覆盖人工锁定的 Note 或事件归属。

## 5. 服务端数据语义

### 不可变来源

`conversation`、`message` 和 `message_part` 表示来源事实。重新上传同一范围时，使用空间、来源身份和 `message_key` 去重；重复导入只增加 `message_origin`，不产生重复消息。原 v0.19 设计中的旧隔离术语在实现时统一替换为 `space`，并保留 `uploaded_by_user_id` 作为上传者审计字段，不允许两套隔离边界并存。

来源时间和入库时间分开：业务排序优先使用 `occurred_at` / `source_order`，不能用上传时间代替。会话展示名可以变化，不能用群名作为跨账号合并键。

### Note 是中间层

一份 Note 是一段有意义的阶段摘要，不是每条消息的复制，也不是事件本身。它必须通过 `note_message` 指向实际消息或消息部件；图片、文件未读取时不能写成已验证结论。

多人重复上传的推荐处理（待确认）：来源消息在同一空间内仅在稳定来源身份一致时去重，保留每次上传和上传者的来源记录；内容相同或语义相似的 Note 不自动合并，先保留独立记录并提示人工审查。不能因为去重而让一个上传者删除其他人的 Note 或来源贡献；人工合并、撤销与派生报告的删除规则须先确认。当前客户端上传的是规范化聊天记录，服务端生成正式 Note，直接上传 Note 是后续待定能力。

- `origin=auto`：模型/规则生成，后续自动任务可以提出替代建议。
- `origin=manual`：人工编辑或新增，自动任务不得覆盖。
- `assignment_mode=manual`：人工确认当前完整事件归属，空集合也表示明确决定“暂不归属”。

### Event 是持续追踪入口

事件聚合 Note，而不是聚合原始消息数组。事件可以跨会话；`conversation_id` 只作主要来源提示，真实证据沿 `event_note → note_message → message` 查询。

事件状态只表达完成进度：`open`、`in_progress`、`done`；没有完成进度要求的事件使用 `NULL`，不能把“没有状态”当成已完成。

原型里的 `follow` / `advance` 是用户的关注视角，不应混入事件状态。首版可作为用户视图偏好；以后若要跨设备同步，再单独建 `event_follow_preference`。

### Report 是冻结快照

报告保存正文、栏目、条目和来源，以及生成时的事件/Note 快照。之后人工把 Note 移到另一个事件时，只影响当前事件查询，不重写旧报告。报告中的“建议”“原文明确”“状态说明”仍要区分，不能把 LLM 推断升级为来源事实。

## 6. 原型与 schema 需要补齐的地方

### 增加事件关系表

原型支持 5 对事件的“合并/拆开/有关联/保持独立/待确认”，但 `v0.19` 只有 `event_tag`，没有持久化事件对之间的判断。建议新增 `event_relation`：

```text
event_relation
- user_id
- left_event_id / right_event_id       # 规范排序，避免 A-B / B-A 重复
- relation_kind                         # same / related / separate / depends_on
- decision                              # pending / accepted / rejected
- reason
- source_note_ids 或 result_ref
- decided_by / decided_at
```

事件关系是“当前判断”，不是强制把两个 Event 物理合并。这样可以保留独立状态和历史，并允许以后撤销判断。

### 把人工结果表示成 Note

原型中的“补充一个明确结果”不应只写前端 localStorage。服务端应创建 `origin=manual` 的 Note，再通过 `note_message` 关联聊天原文（如果有），或允许无来源的人工 Note，并将它关联到 Event。这样“人工确认完成”仍然可追溯。

### 需要最小审计能力

`v0.19` 明确把完整审计/任意时点回放放在范围外，但从 Tauri 上传后进入多人/多设备服务端，至少应记录：

- Note 的人工编辑和归属确认。
- Event 的状态、标题和内容变更。
- Event relation 的接受、拒绝和恢复。
- Report 生成时使用的输入版本。

可以先采用追加式 `event_activity` / `note_activity`，不必首版实现完整 diff 或回放；但不能让人工判断只存在浏览器状态。

## 7. 两端用户体验

### Tauri：采集与上传

现有“聊天记录”页保留浏览和选择能力，新增一个明确的上传流程：

1. 选择微信账号、白名单会话、时间范围和是否包含附件。
2. 展示上传前确认卡：来源、会话、消息数、日期、附件数、数据将离开本机的提示。
3. 在 Rust 层生成规范化包，前端展示打包进度。
4. 上传队列显示 `待上传 / 上传中 / 服务端处理中 / 可整理 / 失败可重试`。
5. 上传完成后提供 Devify 工作台链接；不在 Tauri 内复制完整事件工作台。

现有本机“规则整理 / AI 总结 / 总结记录”可以保留为离线预览和兼容能力，但文案必须标成“本机总结”，不能与 Devify 的正式 Report 混淆。现有 SMTP 日报可以继续工作，直到 Devify 聊天报告交付链路稳定。

### Devify：事件工作台

将 `event-workspace-prototype` 的三阶段扩展为四阶段：

1. **收件与导入**：批次、来源、覆盖范围、缺口、处理状态。
2. **整理**：Note 列表、原文证据、保留/排除理由、待确认内容。
3. **持续事件**：事件列表、状态、标签、时间线、下一步和跨会话证据。
4. **报告**：按专题/周期生成 Report，显示来源和生成时快照。

原型的“关联审查”作为事件页的独立审查入口保留，不要隐藏在自动合并里。默认只提出建议，用户确认后才修改当前事件关系。

## 8. 安全与失败处理

- Tauri 上传使用 HTTPS 和专用 Devify API 凭据；凭据存 macOS Keychain / Windows Credential Manager，不写入 `settings.json`。
- 上传包不包含微信 key、数据库文件、解密缓存、系统路径或本机 Agent token。
- 服务端拒绝路径穿越、超大单文件、未知 schema、越权会话和不一致的消息计数。
- 上传失败可重试；导入解析失败要显示具体 `upload_item`、阶段和下一步，不使用无限 spinner。
- 原始消息导入和分析任务分开：导入成功但分析失败时，消息仍可查、任务可重试。
- 服务端已保存的消息不能因为客户端删除本地解密缓存而消失；删除/保留策略应由 Devify 的数据设置控制。
- “本机可见”不再等于“永不离开本机”。启用上传后，产品说明和隐私文案必须改为“仅在用户确认上传后离开本机”。

## 9. 分阶段实施

### Phase 0：契约和样本

- 在 Devify 增加聊天导入领域的 OpenAPI 草案和脱敏 fixture。
- 固定 `wechat.v1` manifest、JSONL 字段、ID/时间/类型规范。
- 用一批真实结构但不含正文的样本验证幂等、重复导入和错误返回。

### Phase 1：Devify 接收层

- 先新增 `space`、`space_membership`（角色：`owner` / `maintainer` / `user` / `guest`）及空间选择/切换接口；个人空间和团队空间走同一模型。
- 再新增 `upload_batch`、`upload_item`、`conversation`、`message`、`message_part`、`message_origin` 的 Django 模型和迁移；聊天对象按空间隔离，批次额外记录上传者。
- 实现上传、哈希、分片/恢复、解析、去重和进度接口。
- 所有列表、详情、附件下载、分析启动和去重查询先套空间成员过滤；不要只依赖视图层传入的用户 ID。
- 先只提供导入批次和来源浏览，不启动 AI 分析。

### Phase 2：Tauri 上传客户端

- Rust 增加规范化导出器，保证白名单、范围、字符串 ID 和附件边界。
- 增加 Devify 地址/认证/上传队列设置；网络凭据进入系统凭据存储。
- 增加批次确认、进度、重试和“打开 Devify”入口。

### Phase 3：Note 与事件工作台

- 实现 `analysis_job`，先做规则/人工整理，再接 Agent。
- 实现 Note 证据抽屉、人工保护、Event 时间线、标签和 `event_relation`。
- 把原型的 localStorage 操作迁移成服务端 API，并补充权限和审计。

### Phase 4：报告和增量同步

- 按 `topic_subscription` 生成冻结 Report。
- 通过客户端游标和消息幂等键支持后续增量上传，而不是每次重传完整历史。
- 再评估附件 OCR、跨来源（WhatsApp/邮件）和自动日报。

## 10. 暂定决策

- **采集端**：`wechat-devify-tauri`，本机只读、白名单强制、用户确认上传。
- **服务端**：Devify，保存规范化来源、事件关系和报告快照。
- **空间与可见性**：所有数据属于个人或团队空间，对该空间有效成员可见，不支持空间内私人数据或跨空间/匿名公开。
- **传输**：v1 使用规范化压缩包；以后再增加增量流式接口。
- **分析位置**：正式 Note/Event/Report 在 Devify；Tauri 的本机总结只做预览或兼容。
- **数据模型**：以 `chat-analysis/schema-design.json` v0.19 为基线，补充 `event_relation` 和最小活动审计。
- **交互模型**：以 `event-workspace-prototype` 的证据优先、人工确认和跨会话事件为基线，不照搬其浏览器存储实现。
- **权限实现**：以空间成员关系为查询前置条件；不通过客户端传入的 `user_id` 或 `space_id` 实现隔离。

## 当前不应做的事

- 不要先把 `wechat-devify-tauri` 改成一个完整的事件工作台。
- 不要在 Devify 中直接解析微信 SQLCipher 数据库。
- 不要把 Tauri 的 AI Markdown 输出直接写成 Devify 的 `event.content`。
- 不要在没有证据或人工确认时自动合并两个 Event。
- 不要在 API 未定稿前同时改两边的业务模型，先用脱敏 fixture 固定跨仓库契约。
- 不要把“空间可见”实现成原始微信消息的匿名或跨空间公开；如有公开需求，另建脱敏发布快照和审批流程。
