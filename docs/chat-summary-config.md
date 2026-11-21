# 聊天总结配置：控制端与桌面端接入约定

对应 [#160](https://github.com/oneprolabs/devify/issues/160)。本轮实现控制端；
缓存、初始化编排、并发合并与本地 CLI 拼接由桌面端继续实现。
本接口只管独立聊天总结，不适用于事件抽取、主题订阅或定时报告。

## 初始化与条件更新

登录成功并选定空间后，首次初始化请求：

```http
GET /api/v1/spaces/{space_id}/chat-summary-config?schema_version=1
Authorization: Bearer <access token>
```

需要有效登录、活跃账号及空间读取权限。响应沿用全局
`{"code":0,"message":"success","data":{...}}` 包装，键名为 snake_case。
不支持的或缺失的 `schema_version` 返回 400；无空间权限返回 404。
配置请求失败不影响已经成功的登录，也不阻止备份等其他功能。

`data` 的字段如下：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 当前为整数 `1`；协议兼容能力，不是应用发布版本 |
| `version` | 业务模板版本，首版为 `chat-summary-v1` |
| `sha256` | `template` 原始 UTF-8 字节的 SHA-256，小写十六进制 |
| `template` | 无变量的业务规则全文；三段为结论、详细经过、行动项 |
| `variables` | 当前为空数组；客户端不做字符串变量替换 |
| `languages` | `中文`、`English`、`按原文语言` |
| `output_format` | `markdown` |
| `scope.server` | 当前请求的服务 origin，含协议及端口、不带结尾 `/` |
| `scope.account_id` | 当前账号 ID，字符串 |
| `scope.space_id` | 当前空间 UUID，字符串 |
| `scope.capabilities` | 原权益的 `features`、`enforced`、`internal`，仅用于区分缓存上下文 |
| `budgets.cloud` / `budgets.local_cli` | 下述输入预算 |
| `min_check_interval_seconds` | `21600`，6 小时 |
| `retry_after_seconds` | `900`，失败后至少等待 15 分钟再自动重试 |
| `no_cache_behavior` | `require_online_initialization` |

响应头含 `ETag`（配置及其 scope 的摘要，保留原有引号），以及
`Cache-Control: private, no-cache`、`Vary: Authorization, Cookie`。
模板版本与 ETag 不同：权限或预算变化也会改变 ETag。
后续用同一个 URL、同一身份发送 `If-None-Match: <ETag>`；没有变化时返回
**304，无正文**。权限检查在 ETag 比较之前执行，撤销权限不会被 304 绕过。

现有设备注册/心跳 `POST /api/v1/auth/desktop/devices` 可以额外传入整数
`"summary_config_schema": 1`，响应 `data.chat_summary_config` 包含：

```json
{
  "schema_version": 1,
  "version": "chat-summary-v1",
  "sha256": "<模板的64位小写十六进制摘要>",
  "min_check_interval_seconds": 21600
}
```

这是全局模板更新提示，不是授权或空间配置。未传参数的旧客户端响应不变。
心跳不含模板、模型密钥或完整权益；提示生成失败时仍正常完成设备注册/心跳。
JWT 登录与刷新接口不变，不添加新的轮询任务。

桌面端接收现有心跳/权益刷新通知后，可在距离上次检查至少 6 小时时执行一次
条件 GET，从而发现模板、预算或权益变化；不因打开聊天、切换页面或生成总结
而发请求。不要求增加心跳频率。每个缓存上下文最多一个检查在途，其余通知
合并；未变化时只接收 304。检查失败保留旧缓存，并按 15 分钟退避；退避后的
重试同样由已有通知驱动。首次无缓存的初始化不受 6 小时间隔限制。

## 缓存、兼容与离线

缓存键包括规范化的客户端配置服务地址、账号 ID、空间 ID、schema 及
`scope.capabilities`。服务地址应保留部署路径；校验返回的 origin 与请求地址
一致，不能只按显示名称或模板版本共用缓存。权益变化后先刷新权益，再选择
匹配的缓存。模板本身不授予任何能力；本地总结仍检查现有 `ai.local_agent`
权益，内部工具接入仍检查 `internal` 与 `bridge.agent_cli`。

下载后先校验 schema、scope、支持的语言、空 `variables`、Markdown 格式、
模板非空及 SHA-256、预算字段及其非负关系。遇到不兼容配置时保留有效旧缓存，
不以未知 schema 或变量尝试执行；提示需要升级客户端。

将正文、版本、摘要、ETag、scope 和校验结果写入同一个缓存文件，使用临时文件、
刷盘后原子替换。只有下载完成并通过全部校验后才提交更新；提交前再次确认
账号、服务地址和空间仍为发起请求时的上下文，丢弃切换前的迟到响应。
重启或断电后必须再次校验整份缓存，不单独写版本号。

离线/更新失败时优先使用当前上下文的有效缓存，同时继续遵守原权益缓存及其
过期策略。没有有效缓存时，明确提示“请联网完成总结配置初始化”，只暂停
本地聊天总结；不内置另一份三段式业务模板。服务端未升级而返回 404 时也是
配置不可用，不能据此打开付费能力。

## 输入与任务固定

业务模板不包含云端 JSON 输入解释或本地 CLI 执行封装。桌面端拼接：缓存业务
模板 + 输出语言 + CLI 执行限制（禁止工具、文件读取、联网）+ 用户补充要求
+ 统计信息与选定原文。补充要求不能覆盖事实约束。不要修改仍被事件、报告等
流程共用的 `agent.rs::build_prompt`；为聊天总结使用独立入口。

每项预算包含 `unit=utf8_bytes`、`max_request_bytes`、`prompt_bytes`、
`reserved_overhead_bytes`、`max_content_bytes`，满足：

```text
max_content_bytes = max(0, max_request_bytes
                        - prompt_bytes - reserved_overhead_bytes)
```

云端预算对完整压缩 JSON 模型输入计量，不是原始文字字符数。输入格式见
`summaries/input.py::summary_content`：`title/range/language/speakers/chats`，
其中消息行为 `[带时区时间, speakers索引, 原文]`。云端额度取配置的单次输入
上限与已知模型扣除输出预留后的输入上限之较小值，预留 64 字节封装开销，
提示词开销包含服务端 JSON 解释。代理模型使用 UTF-8 字节保守估算；已知模型
实际执行可能使用 tokenizer。服务端执行前仍会检查当前模型的实际预算。

本地预算沿用单次输入配置上限，额外预留 2048 字节给 CLI 限制、统计、用户要求
和封装。**这不是 CLI 模型上下文容量声明**：客户端还须检查自己的模型容量和
输出预留；实际附加内容超过预留时，按更大的实际开销计算。提示词更新后必须
重新计算可用原文额度，不静默截断原文，不自动拆分或改用 map-reduce。

新客户端创建云端总结时，在现有 POST 请求中同时提交：

```json
{
  "prompt_version": "chat-summary-v1",
  "prompt_digest": "<缓存中的模板 SHA-256 摘要>"
}
```

两字段缺一返回 400；新请求版本/摘要过期返回 409，且响应
`data.error_code=summary_config_changed`，更新配置后再提交。
同一 `request_key` 重发必须保持原请求内容，服务端先查幂等记录，再检查当前
模板，因此配置更新后仍能取回原任务。仅当该错误码明确表明尚未建任务时，
才以刷新后的配置重发新请求；其他 409 是请求内容冲突，勿自动重跑已有任务。
旧客户端可不传这两个字段，由服务端选择当前模板。

服务端将业务规则、版本、摘要与云端输入解释作为一份 `prompt_snapshot` 存储。
Worker 与手动失败重试只读这份快照；结果 API 返回 `prompt_version` 和
`prompt_digest`，不下发内部快照。迁移前记录的空快照固定对应冻结的
`legacy-cloud-v1`，不会在重试时升级为新规则。
本地任务也需在创建时保存模板快照、版本、摘要、scope 和来源（如
`server` / `validated_cache`），执行和重试时沿用，便于结果追溯。

## 维护与发布

初期直接维护 `devify/chat_analysis/summaries/prompts.py` 中的版本化配置，
改规则必须同时递增 `VERSION`；不引入管理平台。`LEGACY_TEMPLATE` 保持冻结。
协议破坏性变化才升级 schema，模板规则修改只升模板版本。

新增迁移 `0008_chatsummary_prompt_snapshot` 仅增加 JSON 字段，默认 `{}`，
不扫描或重跑历史任务。发布先应用迁移；新 API 接受任务前，需停止旧版本总结
消费者并完成 Worker 升级（可先暂停总结入口、排空旧消费者），避免旧 Worker
忽略快照。回滚应用代码也需先暂停并处理新规则任务，不能让旧 Worker 接管。
控制端与桌面端分别发布；控制端上线后，新云端任务开始使用三段式规则，
桌面端完成上述接入后才能对齐本地 CLI 总结。
