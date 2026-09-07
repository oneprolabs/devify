# 应用设置与模型绑定

添加 [LLM 提供商](./llm-providers.md) 只是让模型可用；应用设置决定**每个阶段用哪个模型**，并集中管理 Threadline、智能投递渠道和失败通知的运行时设置。

## 应用设置

打开 **`/management/app-settings`**，它分为：

- **全局设置**——运行时参数，如失败通知渠道（选择在[通知渠道](./email-notifications.md)里创建的 webhook 渠道）。
- **会话列表设置**——图像理解与文本处理所用的 LLM：
  - **图像识别 / 多模态模型**——对图片附件与图片意图做直接多模态理解。
  - **文本处理模型**——邮件正文处理、摘要与元数据抽取。
- **智能渠道**——绑定到智能投递（Relay）渠道的模型。

![应用设置与模型绑定](/images/console/mgmt-app-settings.png)

## Threadline 工作流配置

`/management/threadline/config` 保存 Threadline 工作流的模型设置及相关选项。

![Threadline 工作流配置](/images/console/mgmt-threadline.png)

## 其他管理页面

| 路径 | 用途 |
|------|------|
| `/management/llm/config` | 提供商凭据、模型、默认值、连接测试 |
| `/management/threadline/periodic-tasks` | 定时任务 |
| `/management/notifier/channels` | Webhook 与通知渠道 |
| `/management/notifier/settings` | 通知设置 |
| `/management/billing/settings` | 计费运行时设置 |

Django Admin 仍可用于底层检查与历史遗留操作。
