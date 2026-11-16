# 桌面客户端问题反馈

反馈使用当前 Devify 实例的登录身份，独立于聊天导入、空间和 AI 分析。
客户端提交前显示接收服务地址。自部署实例的反馈由本实例管理员处理；
当前没有跨实例转发、匿名提交或向官方实例复用私有实例 Token 的行为。

## 部署

1. 执行 `python manage.py migrate` 创建 `feedback` 表。
2. 按新版 Compose 重建 API 与 worker，使 `/opt/feedback` 使用专用持久卷。
   蓝绿 API 继承基础 Compose 的相同挂载。此目录不挂载给 Nginx。
3. 执行 `python manage.py register_periodic_tasks` 登记每日附件清理任务。
4. 管理员打开 `/management/feedback` 查看、分派、回复和更新处理状态。

非 Compose 环境可通过 `FEEDBACK_STORAGE_ROOT` 环境变量指定私有持久目录，
API 与 worker 必须能访问同一目录，禁止配置到任何公开静态文件目录。

## API

以下接口不使用末尾斜杠，沿用平台 JWT / session 认证及
`{code, message, data}` 响应包装。

| 接口 | 权限与行为 |
| --- | --- |
| `POST /api/v1/feedbacks` | 当前用户提交；multipart `payload` JSON 和重复的 `screenshots` 文件字段 |
| `GET /api/v1/feedbacks?page=1` | 当前用户的反馈，20 条/页，返回 `count/next/previous/results` |
| `GET /api/v1/feedbacks/{uuid}` | 仅反馈提交人 |
| `GET /api/v1/feedbacks/{uuid}/attachments/{uuid}` | 提交人或 staff；鉴权下载，禁止缓存 |
| `GET /api/v1/admin/feedbacks?status=received&page=1` | 仅 staff，可按状态筛选 |
| `PATCH /api/v1/admin/feedbacks/{uuid}` | 仅 staff；修改 `status/reply/fix_version/assigned_to` |

提交示例：

```json
{
  "client_id": "77d31076-8e6c-4afe-80ce-7fe010cb6296",
  "category": "upload",
  "description": "点击上传后显示服务不可用",
  "context": {
    "app_version": "0.1.0",
    "platform": "macos",
    "arch": "aarch64",
    "os_version": "macOS 14.5 (23F79)",
    "wechat_version": "4.1.15",
    "page": "chat",
    "related_batch_ids": [42]
  },
  "diagnostics": {
    "schema_version": 1,
    "generated_at": "2026-11-13T09:00:00Z",
    "events": [{"at": "2026-11-13T09:00:00Z", "module": "upload", "operation": "failure", "code": "COMMAND_FAILED", "duration_ms": 37}]
  }
}
```

- 分类：`wechat/backup/upload/login/interface/other`。
- 状态：`received/processing/needs_info/resolved`。
- 提交人由登录身份确定，反馈记录与管理员界面使用用户名（`submitted_by`）标识。
  客户端不再填写 `contact`；字段保留给旧客户端，最长 200 字。
- `context.os_version` / `context.wechat_version` 由客户端自动采集
  （操作系统版本、微信安装版本），均为可选、最长 64 字；
  旧客户端不发送时按空字符串保存。
- `client_id` 在用户范围内唯一；同内容重放返回原反馈（200），
  同编号不同内容返回 409，新建返回 201。服务端自行计算内容摘要。
- 描述最长 5000 字；诊断 JSON 最多 512 KiB、
  1000 条事件；最多 3 张 PNG/JPEG，每张输入不超过 3 MiB，
  总请求不超过 10 MiB。截图实际解码、去元数据并重新编码。
- 截图 30 天后拒绝下载，每日清理字节并保留过期标记和反馈处理结果。
- 诊断字段采用白名单；客户端不扫描应用数据目录，不采集聊天正文、
  解密数据库、密钥、登录凭据或 Agent 原始输入输出。

## 客户端离线行为

反馈入口在登录页、服务不可用页和页面渲染异常时仍可使用。
草稿按服务地址与登录用户隔离，截图和诊断保存于本机私有文件。
用户可以保存 ZIP 诊断包到下载目录。

首次尝试提交前冻结内容、环境版本和提交编号；超时后以相同内容重试，
不会因刷新日志或应用升级悄悄改变原提交。编辑未保存的截图不能提交。
没有登录时可以整理材料与保存诊断包，在线提交需先登录接收实例。

## 验证

### 请求关联

客户端对每一次 Devify HTTP 调用生成独立 `X-Request-ID`，并在本地诊断中
记录同一 ID 的开始和结果事件。结果包含 HTTP 状态、到响应头的耗时或安全的
网络错误分类；不记录请求体、响应体、完整 URL 或凭据。服务器回传了不同的
合法 ID 时，额外记录 `server_request_id`，便于检查网关是否改写。

Devify 中间件接受 1–80 位 ASCII 字母、数字及 `._-`（首字符为字母或数字），
缺失或不合法时重新生成，并通过响应头回传。请求期间的应用日志带
`[request_id=...]`，请求摘要包含方法、路由模板、状态和耗时。
可使用诊断中的 ID 检索 API 日志，定位同一次请求。

HTTP 请求 ID 每次重试都会变化；反馈 `client_id` 等业务幂等键保持不变。
这次接入覆盖客户端到 Django 的 HTTP 请求，不代表 Celery 后台任务已传递该 ID；
后台任务继续使用现有 `task_id`。网关在 Django 之前拒绝的请求没有应用日志。

### 回归检查

`feedback/tests/test_api.py` 覆盖数据库层幂等、用户隔离、私有附件、
管理员回复与附件清理；`test_validation.py` 覆盖诊断白名单、图片重编码
与未登录访问。执行方式遵循 `docs/test-gate.md`，使用 MariaDB。

2026-11-13 本次开发验证：前后端构建、Django check、迁移一致性、
后端无数据库校验及前端测试通过。现有开发 MariaDB 的数据目录挂载失效，
创建测试库返回 errno 2；数据库集成测试尚待在正常 MariaDB 上补跑。
