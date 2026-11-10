# Devify 邮箱来源与空间共享测试用例集

> 对应提交：`3e3ea75 Share email sources across spaces`
> 覆盖功能：`EmailMailbox.source_key`、`EmailMailboxShare`、`EmailMessage.mailbox`、空间共享/转移、团队 AI gate、迁移 `0044/0045`
> 整理日期：2026-11-10

## 1. 变更范围与风险

| 变更 | 影响面 | 风险 |
|---|---|---|
| `EmailMailbox.source_key` 全局唯一 | 所有 IMAP 邮箱创建/编辑 | 旧库重复邮箱需要合并 |
| `EmailMailboxShare` | 个人/团队空间可见性 | 共享撤销、转移、ACL |
| `EmailMessage.mailbox` + `(mailbox, message_id)` | 收信去重 | 旧 `(user, message_id)` 约束被移除 |
| 抓取传入 mailbox | IMAP 收信与入库 | 团队邮件归属、旧 Haraka 兼容 |
| 团队 AI gate | merge/workflow/Relay | `EMAIL_TEAM_AI_ENABLED` 默认 false |
| 迁移 `0044/0045` | 存量数据 | 重复邮箱合并、凭据选择、全表回填 |

## 2. 测试环境

- 后端：`devify-api-dev` 容器，MariaDB 11.x，Redis broker
- 前端：`http://localhost:8001`（开发栈）
- 测试库：`devify_migcheck`（threadline integration/unit 直接复用）
- 浏览器：ego-browser
- 关键配置：
  - `EMAIL_TEAM_AI_ENABLED=false`（默认）
  - 团队空间首版只读原文

## 3. 自动化覆盖与覆盖率

### 3.1 本次执行结果

| 测试集 | 结果 |
|---|---|
| `test_email_mailbox_sharing.py`（新增） | 15 passed |
| 邮箱聚焦集（sharing + mailboxes + boundaries + services + fetch + settings） | 110 passed |
| `threadline` unit + integration（含 broker） | 422 passed |
| `manage.py check` | 通过 |
| `makemigrations --check` | No changes detected |
| isort / flake8 | 通过 |

### 3.2 模块覆盖率（聚焦测试）

| 模块 | 语句 | 未覆盖 | 覆盖率 | 说明 |
|---|---:|---:|---:|---|
| `threadline/models.py` | 431 | 103 | **76%** | 新增模型逻辑已覆盖；未覆盖多为历史分支 |
| `threadline/serializers/email_mailbox.py` | 66 | 5 | **92%** | |
| `threadline/serializers/space_email.py` | 20 | 0 | **100%** | |
| `threadline/services/space_email.py` | 9 | 1 | **89%** | 无 space 的防御分支未覆盖 |
| `threadline/tasks/email_fetch.py` | 163 | 68 | **58%** | mailbox 传参已覆盖，其余为旧抓取分支 |
| `threadline/tasks/email_merge.py` | 70 | 44 | **37%** | 团队 gate 已覆盖；旧合并主体未覆盖 |
| `threadline/utils/email/service.py` | 154 | 18 | **88%** | |
| `threadline/views/email_mailbox.py` | 267 | 94 | **65%** | 共享/转移已覆盖，旧 CRUD 分支较多 |
| `threadline/views/space_email.py` | 66 | 12 | **82%** | 删除分支未覆盖 |

> 覆盖率口径：整个模块的行覆盖率，因而被大量历史 CRUD/合并代码稀释；本次新增的关键路径（source_key、share、mailbox 去重、团队 AI gate、share/transfer）均有对应用例。
>
> 迁移 `0044/0045` 不由 pytest 覆盖，已在一次性 MariaDB scratch 库中单独验证重复邮箱合并场景。

## 4. 单元测试用例

| ID | 用例 | 预期 | 自动化 |
|---|---|---|---|
| U-01 | `compute_mailbox_source_key` 相同配置生成相同 key | key 一致 | `test_the_source_key_follows...` |
| U-02 | 修改 folder/host 后 source_key 更新 | key 变化 | 同上 |
| U-03 | 两个用户创建同一 IMAP 来源 | `IntegrityError`，全局唯一 | `test_a_mailbox_source_is_globally_unique` |
| U-04 | 新建邮箱自动生成 owner `manage` share | share 存在且为 manage | `test_creating_a_space_source...` |
| U-05 | `EmailMessage` 只传 mailbox、不传 space | space 自动取 mailbox.space | `test_message_with_mailbox_but_no_space...` |
| U-06 | 附件不传 space，随消息继承 | attachment.space = message.space | `test_attachment_inherits_the_team_space` |
| U-07 | 同一 mailbox + message_id 重复保存 | 第二次返回 None，只存一条 | `test_a_shared_mailbox...` |
| U-08 | 两个 mailbox 使用相同 message_id | 各存一条 | `test_the_same_message_id_from_two_mailboxes...` |
| U-09 | `email_ai_allowed` 团队 false / 个人 true | 符合预期 | `test_team_mail_skips_merge...` |
| U-10 | `EMAIL_TEAM_AI_ENABLED=true` | 团队邮件允许 AI | `test_team_ai_can_be_enabled_by_setting` |
| U-11 | `_queue_merge_for_saved_email` 团队邮件 | 不调用 merge.delay | `test_team_mail_skips_merge...` |
| U-12 | `process_email_merge` 团队邮件 | 返回 `team_ai_disabled`，不派发 workflow | `test_process_email_merge_skips_team_space` |
| U-13 | `fetch_user_imap_emails` 传入 mailbox | `save_email(..., mailbox=mailbox)` | `test_fetch_user_imap_emails_passes...` |
| U-14 | 历史消息 `mailbox=NULL` | 仍可按 `space` 读取 | `test_a_legacy_message_without_a_mailbox...` |
| U-15 | 个人设置接口 | 只返回个人邮箱 | `test_the_personal_mailbox_api_does_not_expose...` |

## 5. 团队兼容性用例

| ID | 场景 | 前置 | 预期 |
|---|---|---|---|
| T-01 | 在团队空间创建邮箱 | owner 权限 | 邮箱 `space=团队`，owner share=`manage` |
| T-02 | 同一邮箱共享给个人空间 | 团队邮箱 + share | 团队/个人都可见同一 `EmailMessage.uuid`，只存一份 |
| T-03 | 团队普通成员读取 | ACTIVE member | `/spaces/{team}/emails` 200 |
| T-04 | 非成员读取 | 无 membership | 404 |
| T-05 | 被移除成员读取 | membership=removed | 404 |
| T-06 | 创建者离开团队空间 | 移除 membership | 邮箱仍可被调度器抓取；剩余管理员可管理来源 |
| T-07 | 创建者账号停用/删除 | `user.is_active=False` / 删除用户 | **当前会停止抓取/级联删除邮箱**，属已知第二阶段问题 |
| T-08 | 转移来源 个人 → 团队 | 双侧 `can_manage` | 归属改为团队；个人保留 `read`；历史消息仍可见 |
| T-09 | 转移来源 团队 → 个人 | 同上 | 归属改为个人；团队保留 `read` |
| T-10 | 重复创建同一来源 | 来源已存在 | 409，返回已有 `mailbox_uuid` |
| T-11 | 普通 `user` 创建团队来源 | 非 owner/maintainer | 403 |
| T-12 | 团队邮件 AI/合并/Relay | `EMAIL_TEAM_AI_ENABLED=false` | 全部跳过 |
| T-13 | 个人邮件 AI/合并 | 个人空间 | 保持原有链路 |
| T-14 | 撤销个人空间 share | 团队 owner 操作 | 个人空间邮件数变为 0，团队仍可读 |
| T-15 | 重新 share | 同上 | 个人空间恢复可见 |
| T-16 | 旧 `/chats` 列表 | 创建者本人 | 仍能看到共享邮件 |
| T-17 | staff 管理员访问团队空间 | 未 takeover | 404（既有产品约定，需 runbook 说明） |
| T-18 | 归档团队空间 | `status=archived` | 只读，不能删除/修改 |
| T-19 | 团队附件 | 消息详情 | 返回附件元数据；文件下载接口尚未实现 |
| T-20 | 个人邮箱上限 | 团队来源不计数 | 只统计个人来源 |

## 6. 线上兼容性 / 迁移用例

| ID | 场景 | 预期 | 级别 |
|---|---|---|---|
| P-01 | 存量库无重复邮箱，执行 `0044/0045` | 迁移成功，`source_key` 回填，owner share 生成 | 高 |
| P-02 | 存量库存在同源重复邮箱 | 保留最早 canonical，重复行 `merged:<id>` 并禁用，双方 space 获得 share | 高 |
| P-03 | 重复邮箱凭据不同 | canonical 使用最近一次成功抓取的凭据 | 高 |
| P-04 | 历史 `EmailMessage.mailbox=NULL` | `(mailbox, message_id)` 允许多个 NULL，旧邮件仍按 space 可读 | 高 |
| P-05 | 旧个人邮箱收信/AI | 抓取、解析、AI、合并行为不变 | 高 |
| P-06 | 旧 `/settings/mailboxes` | 只返回个人来源；团队来源详情 404 | 中 |
| P-07 | 线上重复创建来源 | 409，提示申请共享 | 中 |
| P-08 | `0045` 全表回填 | 先备份、评估行数/锁时间；必要时维护窗口 | 高 |
| P-09 | 部署顺序 | 先 `migrate`，再重启 API/worker/scheduler；worker 无 autoreload | 高 |
| P-10 | 回滚 | `0045` 反向 noop；`0044` 反向重建旧唯一约束可能失败；以备份恢复为主 | 高 |
| P-11 | 删除来源 | `EmailMessage.mailbox` SET_NULL，邮件留在 primary space | 中 |
| P-12 | 创建者账号删除 | `EmailMailbox.user` CASCADE 会删除来源；第二阶段改 `SET_NULL` | 高 |
| P-13 | 同一邮箱个人+团队 | 只抓取一次、只存一份；日志应只有一条 source 抓取 | 高 |
| P-14 | Celery 队列 | 邮件任务仍在默认队列；`chat_ingestion` 独立队列不影响邮件 | 中 |
| P-15 | 旧附件接口 | 个人附件仍可读；团队附件文件下载待补 | 中 |
| P-16 | 线上 staff 账号 | 无 takeover 时读不到自己的邮件（既有行为）；需运营说明 | 高 |
| P-17 | 迁移与前一 PR 的 squash 组合 | 干净检出 `migrate` 通过，`makemigrations --check` 无变更 | 高 |
| P-18 | 环境变量 | 默认 `EMAIL_TEAM_AI_ENABLED=false`，无新增必填变量 | 中 |

## 7. 浏览器 / E2E 用例（本次已执行）

| ID | 场景 | 结果 |
|---|---|---|
| E-01 | 登录 `admin` | 通过 |
| E-02 | 团队空间邮件列表 | 200，1 条「Shared inbox test」 |
| E-03 | 个人空间邮件列表 | 200，同一 `uuid`、同一 `mailbox_uuid` |
| E-04 | 重复创建团队来源 | 409，返回已有 `mailbox_uuid` |
| E-05 | 撤销个人空间 share | 200，个人空间邮件 1→0 |
| E-06 | 重新 share | 201，个人空间邮件 0→1 |
| E-07 | 来源转移 个人→团队→个人 | 200 / 200，列表正确 |
| E-08 | 设置 → 邮件设置 | 只显示个人邮箱 |
| E-09 | 旧接口访问团队来源详情 | 404 |
| E-10 | `/chats` 旧列表 | 显示共享邮件，无报错 |
| E-11 | 概览/会话/事件/主题/同步记录/设置 | 无前端报错 |

## 8. 未覆盖 / 待补

| 项 | 状态 | 建议 |
|---|---|---|
| 团队来源前端页面 | 未实现 | 补 UI 后再做完整浏览器 E2E |
| 团队附件文件下载 | 未实现 | 增加空间级下载接口 |
| 团队虚拟地址（Haraka） | 未实现 | 后续空间级 alias 设计 |
| `EmailMailbox.user` 可空化 | 未实现 | 第二阶段改 `SET_NULL`/服务账号 |
| 团队 AI / 计费 / Relay | 未实现 | 计费确定后开启 `EMAIL_TEAM_AI_ENABLED` |
| 迁移自动化测试 | 手工 scratch 验证 | 建议增加 migration test fixture |
| `process_email_merge` 主体分支 | 未覆盖（37%） | 旧逻辑，非本次改动 |
| staff 无 takeover 行为 | 既有产品决策 | 上线 runbook 说明 |

## 9. 发布前检查清单

1. 备份生产数据库；记录 `EmailMessage` / `EmailMailbox` / `EmailAttachment` 行数。
2. 在 staging 用真实重复邮箱数据演练 `0044/0045`，核对 canonical/share/凭据。
3. 部署顺序：`migrate` → 重启 API/worker/scheduler → 验证抓取。
4. 验证同一邮箱只抓取一次、只存一份。
5. 验证个人邮箱收信/AI 无回归。
6. 验证团队空间只读原文，无 merge/AI/Relay。
7. 验证 `EMAIL_TEAM_AI_ENABLED=false`。
8. 准备回滚：备份恢复 + 保留 `merged:` 重复行供审计。
9. 运营说明：staff 账号需 takeover；团队来源通过空间 API 管理。

## 10. 结论

- 本次新增 15 个自动化用例，邮箱聚焦集 **110 passed**，`threadline` 全量 unit+integration **422 passed**。
- 新增关键路径均有测试覆盖；模块覆盖率被历史 CRUD 稀释，关键分支已覆盖。
- 最大上线风险是**存量重复邮箱合并**和**创建者账号删除导致来源级联删除**，需要在 staging 演练并在发布说明中明确。
- 建议先以 `EMAIL_TEAM_AI_ENABLED=false` 发布团队接收/共享能力，AI/计费/虚拟地址后续再开。
