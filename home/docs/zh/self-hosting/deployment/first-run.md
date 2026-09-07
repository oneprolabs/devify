# 首次运行

栈跑起来后，完成以下步骤让 Devify 可用。

## 1. 超级用户

超级用户在首次启动时按 `DJANGO_SUPERUSER_*` 自动创建，确认能登录。

## 2. 配置 LLM 提供商

模型提供商在管理控制台里配置——**不是**主要通过 `.env`。打开 `/management/llm/config`，新增一个或多个提供商条目，并运行内置的连接测试。

完整流程见 [模型提供商](/zh/self-hosting/configuration/llm-providers.md)。

## 3. 绑定模型

在 `/management/app-settings` 和 `/management/threadline/config` 中绑定**多模态**模型（图像理解）、**文本**模型（摘要）以及智能投递渠道模型。

见 [应用设置与模型绑定](/zh/self-hosting/configuration/app-settings.md)。

## 4. 健康检查

```bash
# 开发
curl -f http://127.0.0.1:8000/health
# 生产（经 Nginx）
curl -f http://127.0.0.1:10080/health
```

## 5. 端到端验证

把一封邮件转发到你的收信地址（`{用户名}@{AUTO_ASSIGN_EMAIL_DOMAIN}`），观察它被处理。跑通后会在控制台以 **Success** 状态出现，带 AI 摘要、标签和抽取的待办：

![Devify 控制台中已处理的会话](/images/console/chats.png)

接着见 [使用手册](/zh/guide/wechat-backup.md) 了解控制台与完整的 Threadline 流程。
