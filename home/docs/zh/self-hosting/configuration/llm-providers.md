# 模型提供商（LLM）

Devify 不绑定任何单一 LLM 厂商。模型提供商在**管理控制台**里配置（不是主要通过 `.env`）。Devify 至少需要一个**多模态**模型用于图像理解和意图识别。

## 添加提供商

打开 **`/management/llm/config`** 点击 **Add config**。每个 `LLMConfig` 条目填写 `api_key`、`api_base`、`model`、`deployment`（Azure），以及可选的 `max_tokens`、`temperature`、`top_p`、请求超时。用内置的**连接测试**验证每一项。

![管理控制台中的 LLM 提供商配置](/images/console/mgmt-llm-config.png)

## 调优

> 对推理型模型，`max_tokens` 要给足——它是**输出**预算且包含推理 token，设得太小会截断 JSON 输出并静默丢字段（如标签）。

如果分析完成但缺少标签或摘要且无报错，几乎都是 `max_tokens` 过小导致的输出截断。调高它，并查看已记录的 token 用量（`completion_tokens` 是否顶到上限）来确认。

## 绑定模型

添加提供商只是让模型可用；具体每个阶段用哪个模型（多模态、文本、智能投递渠道），仍在[应用设置与模型绑定](./app-settings.md)里绑定。
