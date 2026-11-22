# 聊天总结：最终需求与客户端接口

对应 [#160](https://github.com/oneprolabs/devify/issues/160)。本轮只实现控制端，
客户端在 `oneprolabs/devify-desktop` 接入。API 当前在 PR 中，尚未部署。

## 最终需求

- 默认 **综合分析**，包含总结、时间线、待办；三个单项只输出自己的内容。
- 自定义允许用户描述目标、关注点与结构，必须填写要求。
- 公共系统规则统一维护，语言只是每次请求的输出选项，不维护各语言版本的系统提示词。
- 用户只编辑自己的要求。客户端界面显示场景名称和说明，不提供系统模板编辑器。
- 云端和本地 CLI 使用同一目录版本。任务创建后固定模板、场景、语言和用户要求。
- 只生成文本；原有空间权限、订阅权益、配额和消息范围限制继续生效。

| 场景 ID | 名称 | 输出 |
| --- | --- | --- |
| `three_part` | 综合分析（默认） | 总结、时间线、待办三项都有 |
| `summary` | 总结 | 主要内容、结论与当前结果 |
| `action_items` | 待办 | 行动、负责人、期限与待确认项 |
| `timeline` | 时间线 | 按时间整理事情经过 |
| `custom` | 自定义 | 按用户要求组织内容，不强制三段式 |

## 1. 登录后下载配置（新增接口）

登录成功、选定空间后，在后台初始化一次：

```http
GET /api/v1/spaces/{space_id}/chat-summary-config?schema_version=1
Authorization: Bearer <access_token>
```

需要有效登录、活跃账号及空间读取权限。响应使用现有包装
`{"code":0,"message":"success","data":{...}}`，键为 snake_case。
读取 `data` 后保留 HTTP 响应头 `ETag`，包括其引号。

| data 字段 | 用法 |
| --- | --- |
| `schema_version` | 必须为整数 `1`；未知版本保留原缓存 |
| `version` | 整个提示词目录的版本，例如 `chat-summary-v8` |
| `default_scenario` | 初始选择此 ID；当前为 `three_part` |
| `scenarios` | 场景列表，每项字段见下表 |
| `scope` | `server/account_id/space_id/capabilities`，用于隔离缓存 |
| `max_instructions_chars` | 用户要求上限，当前 4000 字符 |
| `output_format` | 结果文本按 Markdown 展示 |
| `min_check_interval_seconds` | 普通条件检查最小间隔，当前 21600 秒 |
| `retry_after_seconds` | 更新失败后自动重试退避，当前 900 秒 |
| `no_cache_behavior` | `require_online_initialization` |

每个 `scenarios[]` 包含：

| 字段 | 用法 |
| --- | --- |
| `id/name/description` | 稳定 ID、显示名称及说明 |
| `requires_instructions` | 是否必须填写用户要求，当前自定义为 true |
| `template` | 已组合好的公共规则与场景规则，供内部执行，不做变量替换 |
| `sha256` | 该项 template 的 UTF-8 SHA-256，小写十六进制 |
| `budgets.cloud/local_cli` | 该场景的预算和模板开销，见第 6 节 |

模板和摘要只在所选场景内取，不另返回一份重复的默认模板。语言选项沿用客户端，
不由这个目录下发。客户端须校验每项模板摘要，不能将不兼容或不完整数据覆盖原缓存。

`scope.capabilities` 只是当前权益的快照，不能作为新增授权。原有
`/api/v1/me/entitlements` 仍是权益来源。本地 CLI 保留内部账号和
`ai.local_agent` 检查，工具接入保留 `internal + bridge.agent_cli` 检查。
接口不分发模型凭据。

菜单文案按客户端现有 i18n 显示；这与模型输出语言、系统模板内容互相独立。
scope.account_id 是字符串，space_id 是 UUID 字符串，server 是含端口且无结尾斜杠的 origin。

## 2. 确定场景与输出语言（客户端）

初始选择 `config.default_scenario`。用户单次选择优先，语言否则使用现有总结语言设置；
“跟随界面”需要先解析成实际语言，不能把这个标签直接发给服务端：

```ts
const scenarioId = chosenScenario ?? config.default_scenario
const selected = config.scenarios.find(item => item.id === scenarioId)
if (!selected) throw new Error('所选场景不可用，请更新配置')

const savedLanguage = settings.language.summary === '跟随界面'
  ? settings.language.ui
  : settings.language.summary
const language = chosenLanguage ?? savedLanguage
```

服务端原样使用传入的语言，接受现有 `中文/English/按原文语言`，也接受
`zh-CN/en-US/es` 等语言代码及 `auto`。原文语言选项由模型识别主要语言。
不传语言时保留旧接口的中文默认值；正常客户端应始终显式发送最终选择。
服务端不会再根据账号偏好或 HTTP 界面语言覆盖它。

当前客户端的“本机总结语言”已经用于本地 CLI；云端入队仍在
`ConversationSummary.tsx` 中从 DOM 界面语言构造 language。接入时应统一为
上面解析出的最终值，在入队时固定，云端和本地使用相同结果。
本地分支也不能无条件覆盖用户明确的单次选择，设置名称和说明需同步。

## 3. 创建云端任务（现有接口扩展）

```http
POST /api/v1/spaces/{space_id}/chat-summaries
Authorization: Bearer <access_token>
Content-Type: application/json
```

沿用现有消息、来源、时间范围等字段，在原 body 上加入以下选择：

```ts
const body = {
  ...existingSummaryRequest,
  scenario: selected.id,
  language,
  instructions: userInstructions.trim(),
  prompt_version: config.version,
  prompt_digest: selected.sha256,
}
```

`existingSummaryRequest` 仍包含 `request_key/platform/source_namespace/`
`source_conversation_id/title/range_label/mode/period_start/period_end/messages`。
`request_key` 是本次意图的新 UUID；网络重发保留它以及完整 body。
自定义要求不能为空，其他场景可以为空；上限取 `max_instructions_chars`。
`scenario` 未传时用综合分析；两个版本字段可以都省略以兼容旧客户端，不能只传一个。
用户要求独立放入模型 user 消息，系统模板始终由控制端选择。

- **202**：已创建 queued 任务，保存返回的 `data.id`。
- **200**：同请求键、相同内容的重发，返回原任务。
- **400**：参数不合法，包括未知场景、自定义要求为空、语言未解析或要求过长。
- **409 + data.error_code=summary_config_changed**：尚未建任务，配置已更新；按第 5 节更新后再提交。
- **其他 409**：同请求键对应不同内容，不要自动改键重跑已有任务。
- **429**：已有三个任务处理，或达到原有配额。
- **401/403/404**：按现有登录、权益与空间权限处理。

消息边界不变：最多 2000 条、8 个会话、7 天，原文总计最多 120000 字符。
用户要求也计入模型输入预算，不静默截断聊天原文。

现有结果接口不变：

| 调用 | 用途 |
| --- | --- |
| GET `.../chat-summaries/{id}` | 读取 queued/running/ready/failed 状态与结果 |
| POST `.../chat-summaries/{id}` | 手动重试原失败任务，保留原场景、语言与要求 |
| DELETE `.../chat-summaries/{id}` | 删除终态任务，处理中不能删除 |

结果增加 `language/scenario/instructions/prompt_version/prompt_digest`，只展示用户自己的要求，
不返回内部系统快照。历史未标注场景的记录返回 scenario=null；不得因此重处理历史记录。
换场景、语言或要求是新意图，使用新的请求键；普通重试不接受新要求。

## 4. 本地 CLI 使用同一模板

无需调用云端任务创建接口。选取有效缓存中的场景，拼接：

```text
所选场景的 template（原样）
+ CLI 执行限制（禁工具、读文件、联网）
+ 最终输出语言
+ 用户要求（独立分区）
+ 统计信息与聊天原文（资料分区）
```

创建本地任务时保存所选模板、目录版本、摘要、场景、语言和用户要求；
重试与执行均读取这份快照，不读取之后更新的配置。
不要改动被其他功能共用的 `agent.rs::build_prompt`；为此次聊天输出使用独立入口。
本地执行需要缓存模板；界面不展示不代表本地模板保密，模板中不得包含凭据。

## 5. 配置更新、缓存与失败

复用已有设备注册/心跳，在原 POST `/api/v1/auth/desktop/devices` body 中加
`"summary_config_schema": 1`，可获得轻量提示：

```json
{
  "schema_version": 1,
  "version": "chat-summary-v8",
  "min_check_interval_seconds": 21600
}
```

提示位于 `data.chat_summary_config`，不含模板正文。未传参数的旧客户端响应不变，
提示失败也不会导致设备注册或心跳失败。不增加高频轮询或新的心跳定时器。

收到已有通知后，普通检查最多每 6 小时一次，带保存的 ETag 调用初始化 GET：

```http
If-None-Match: "<已保存的ETag>"
```

**304 没有 JSON 正文**，继续使用缓存；200 校验整份配置后原子替换。
此调用须保留 HTTP 状态和 ETag，先判断 304 再解析 JSON。当前客户端
lib.rs::devify_json_request 只返回解包后的 JSON，会丢失 ETag 并在空 304 上解析失败，
不能直接原样套用；为目录读取保留原始响应状态和响应头，同时复用原有身份校验与网络限制。
devify_http.rs 的诊断层也应把正常的 304 缓存命中记为成功，避免产生伪错误。
生成请求同样需要保留 409 响应中的 data.error_code；当前 fixed_identity_json 会把
非 2xx 转成通用字符串，需在接入时保留这个错误码，不能把所有 409 都当作配置过期重发。

同一上下文最多一个更新在途，其余通知合并；失败保留原缓存并退避 15 分钟。
明确的 `summary_config_changed` 可以触发一次必要更新，不必等 6 小时，仍须合并和退避。
不要在每次启动、打开聊天、切换页面、生成任务时重新下载。

缓存按规范化服务地址（含部署路径）、账号、空间和能力上下文隔离。
写入正文、版本、摘要与 ETag 的同一个临时文件，刷盘后原子替换；提交前确认登录
和空间上下文未变，丢弃旧上下文的迟到响应。重启后重新校验缓存。
离线或失败时使用同一上下文的有效缓存并遵守原权益过期策略；完全无缓存时提示
联网初始化，只暂停此次本地聊天输出，不影响登录和备份。旧服务返回 404 也按配置不可用处理。

## 6. 预算、实现与发布边界

每项预算包含 `unit=utf8_bytes/max_request_bytes/prompt_bytes/reserved_overhead_bytes/`
`max_content_bytes`；可用内容额度为上限减模板和预留开销，最低为 0。
云端预留 64 字节封装，本地预留 2048 字节给语言、CLI 限制、用户要求和统计；
实际附加内容更长时按实际开销计算，本地还须满足所选 CLI 模型自己的上下文和输出预留。

目录仅提供现有配置的输入上限与实际模板开销，不访问模型 SDK。
云端 Worker 执行前仍按当前模型及输出预留检查完整输入；目录预算不是模型的最终承诺。
云端内容格式见 `summaries/input.py`，用户要求和 JSON 转义也需要计量。

| 模块 | 职责 |
| --- | --- |
| summaries/views.py | HTTP、空间权限、ETag、任务接口 |
| summaries/configuration.py | 目录响应与心跳版本提示，不依赖模型调用 |
| summaries/prompts.py | 读取/验证单份 YAML，组合和校验任务快照 |
| summaries/serializers.py | 校验请求，保留用户选项，输出结果 |
| summaries/input.py / tasks.py | 独立 user 输入、预算检查、单次执行 |
| summaries/services.py | 请求摘要、超时状态、提交后分发 |

维护 `devify/conf/chat_analysis/summary.yaml`，可用 `CHAT_SUMMARY_CONFIG_PATH` 指向部署方文件；
变更模板、默认场景或场景列表时递增 version，并采用原子文件替换。
`chat-summary-v8` 强化所有场景的人物归属：保留明确姓名或昵称，标明上下文推测，
未知身份不编造，并区分发言人、被提及者与行动负责人。云端和本地 CLI 使用同一公共规则。
迁移 0008 仅增加 prompt_snapshot JSON 字段，场景和要求不再加字段；
历史空快照对应随代码冻结的 legacy-cloud-v1.txt，不受新配置影响。

发布先应用迁移，并在新 API 接受任务前升级总结消费者，避免旧 Worker 忽略快照。
配置更新不重新触发任何历史任务。本轮不更改事件分析、报告、备份、模型凭据或客户端代码。
