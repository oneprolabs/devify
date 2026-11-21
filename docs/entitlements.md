# 订阅权益接口（entitlements）

桌面客户端在每次登录成功后请求 `GET /api/v1/me/entitlements`，把结果缓存到本地
`devify-entitlements.json`，用于判断当前账号能使用哪些功能、以及是否属于内部账号。

## 请求

```http
GET /api/v1/me/entitlements HTTP/1.1
Authorization: Bearer <access token>
```

未登录返回 401/403。响应沿用全局包装：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "plan": {
      "slug": "pro",
      "name": "Pro",
      "status": "active",
      "current_period_end": "2026-12-16T00:00:00+00:00"
    },
    "features": ["ingest.upload", "cloud.ask", "bridge.agent_cli", "cloud.chat_summary"],
    "limits": {"limits.ingest.conversations": 500},
    "quotas": {"quotas.cloud.ask_per_day": 100},
    "usage": {},
    "enforced": true,
    "fallback_features": ["local.wechat_read"],
    "expires_at": null,
    "internal": false
  }
}
```

没有生效订阅时 `plan` 为 `null`、`internal` 为 `false`；活跃账号的
`features` 仍包含免费基线能力 `cloud.chat_summary`。

## 数据来源

套餐权益来自 `Plan.metadata`，另有上述免费基线能力；服务端不硬编码套餐名：

| 键 | 类型 | 说明 |
| --- | --- | --- |
| `features` | `string[]` | 能力键，如 `ingest.upload`、`ai.local_agent`；支持 `ingest.*` 与 `*` 通配 |
| `limits` | `{string: int}` | 数值上限，键需带 `limits.` 前缀，如 `limits.ingest.conversations` |
| `quotas` | `{string: int}` | 周期配额，键需带 `quotas.` 前缀 |
| `fallback_features` | `string[]` | 快照过期后仍然保留的能力 |
| `enforced` | `bool` | 是否启用限制。只有当该套餐同时提供 `features` 时才会生效 |

`enforced` 按套餐原始功能列表判断，服务端追加的免费基线能力不会触发限制。
它是显式开关：在套餐的 `features` 尚未列全之前不要打开，否则客户端会把
未列出的能力判为「不在套餐内」。未开启时客户端保持「全部允许」的旧行为。

## 内部账号

`internal` 只由「存在 `status=active` 且 `Plan.is_internal=True` 的订阅」决定，
与 Django 的 `is_staff` 无关；`is_staff` 但没有内部套餐订阅的账号仍然是普通账号。

桌面端用它来控制**工具接入**（`devify-desktop` 的 Agent 集成 → 工具接入）：

- 非内部账号看不到该分区；
- `agent_access_status` / `agent_access_prompt` 直接返回错误；
- 本机 `/agent/*` 下载路由（`wxq`、`SKILL.md`、`install.sh`、`manifest`）返回 403。

能力键 `ai.local_agent`（本地总结）与 `bridge.agent_cli`（工具接入）已在客户端
注册表中定义，后续可直接放进套餐的 `features`。

## 缓存与降级

客户端 6 小时后刷新、窗口获得焦点时刷新；`fallback_features` 与内置免费基线在快照
超过 7 天后接管。服务端未部署该接口时返回 404，客户端按「未启用订阅控制」处理。
