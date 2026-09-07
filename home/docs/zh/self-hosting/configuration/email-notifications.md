# 邮件与通知

Devify 在两个方向用到邮件：**出站** SMTP 用于账户与失败通知；**入站**邮件（经 Haraka）喂给 Threadline 流程。

## 出站 SMTP

在环境文件中配置：

| 变量 | 用途 |
|------|------|
| `EMAIL_BACKEND` | 生产用 `smtp`，开发用 `console`（打到日志） |
| `EMAIL_HOST`、`EMAIL_PORT` | SMTP 服务器与端口 |
| `EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD` | SMTP 凭据 |
| `EMAIL_USE_TLS` | `true` 启用 STARTTLS |
| `DEFAULT_FROM_EMAIL` | 发件地址 |

## 入站邮件

入站邮件由内置的 Haraka 服务处理——见[入站邮件（Haraka）](/zh/self-hosting/deployment/haraka.md)。

## 通知渠道

Threadline 工作流与任务的失败通知通过 **Webhook 渠道**下发。在 **`/management/notifier/channels`** 创建渠道，再到[应用设置](./app-settings.md)里选择失败通知渠道。

![管理控制台中的通知渠道](/images/console/mgmt-notifier.png)
