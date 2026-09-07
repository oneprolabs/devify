# 待办与智能投递

## 待办（TODOs）

从对话中抽取的行动项显示在**待办**（`/todos`），包含处理时识别到的截止时间。可作为跨所有对话的轻量跟进清单，支持按时间范围、状态、优先级和负责人筛选。

![跨所有对话的待办](/images/console/todos.png)

## 智能投递（Relay）

Relay 把完成的工作流结果投递到外部系统。从**应用中心** → **Relay**（`/apps/relay`）打开。

![Relay 智能投递渠道](/images/console/relay.png)

### 添加投递渠道

1. 在 Relay 中新建渠道并选择**目标类型**：
   - **飞书多维表格**——向飞书多维表格写入一条记录。
   - **Jira**——创建一个 issue。
2. 填写目标的连接信息（见下）。
3. 保存前用**测试投递**，以样例数据和附件验证配置。

### 飞书多维表格渠道

| 字段 | 说明 |
|------|------|
| App ID / App Secret | 飞书自建应用凭据 |
| App Token 类型 | `多维表格`（填链接里的 App Token）或 `Wiki`（填 Wiki 节点 token，后端自动解析出可写 token） |
| App Token / Wiki 节点 token | 按上面的类型填 |
| 表名 | 必须与飞书表名完全一致 |
| 字段映射 | 左侧飞书列名 → 右侧系统内部字段 |
| 附件字段名 | 接收附件的飞书列 |

常用内部字段：`summary_title`、`summary_content`、`llm_content`、`title`、`description`。若只需数量而非文件，用 `attachment_count`。

> **权限：** 飞书应用必须对目标表有**写/编辑**权限（附件还需 drive 上传权限）。如果读成功、写却报 *forbidden*，请检查应用在该 Wiki 节点 / 多维表格上的协作者权限。

### Jira 渠道

提供 Jira 地址、凭据（用户名 + API token），以及字段配置（项目 key、issue 类型、优先级、摘要前缀、描述处理方式）。

### 投递记录与重试

Relay 页面列出近期投递及其状态。失败的投递可从其记录**重试**。
