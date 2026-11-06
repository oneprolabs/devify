# 聊天分析数据库设计

当前入口：[chat-analysis-design.html](chat-analysis-design.html)，v0.20（2026-10-29）。

核心链路：原始 Message → 阶段摘要 Note → 持续追踪的 Event → Report。N 条消息可以归纳为一份 Note，一条消息也可以支撑多个 Note。Note 可先保存，后确认事件归属。

- `note`：阶段摘要、业务时间、自动/人工内容来源与归属确认模式。
- `note_message`：摘要与原消息/具体部件的多对多来源关联。
- `event_note`：事件与摘要的多对多当前归属；时间线直接查询关联摘要。
- `event`：当前整体总结、状态和业务时间；`event_tag` 用于同类检索。

人工确认的完整归属集合（包括空集合）由 `note.assignment_mode=manual` 保护；自动分析只提出建议。当前人工内容由 `origin=manual` 保护。移归需同时更新受影响事件归纳，原消息与摘要来源不改。首版保存当前决定，没有完整操作审计或任意时点回放。

报告仍采用正文、栏目、条目、来源结构；来源改为事件/Note/note_message/外部引用。保存时的事件上下文不随后续移归改变；新生成报告冻结摘要内容和当时归属。

- [schema-design.json](schema-design.json)：20 张逻辑表（19 张业务表＋AppConfig）、查询路径与 SQL。
- [schema-examples.json](schema-examples.json)：虚构教学数据；文字＋图片共同支撑一份 Note，另有未归属人工 Note。
- [reference-report-data.json](reference-report-data.json)：真实报告 6 栏目、40 条目；四条已有微信原消息设计为两份 Note，再关联两件 Event。主键为拟分配值。
- [reference-report-manifest.json](reference-report-manifest.json)：来源位置、哈希与消息分组。
- [VALIDATION.json](VALIDATION.json)：本版核验范围与结果。
- `database-er-*.svg`：离线 ER 图；`snapshots/v0.18-before-note-layer/`：调整前完整设计。

仅更新本地设计和示例，未修改原报告/原始聊天、执行模型提取、迁移数据库、启用任务或部署。


## v0.20 implementation cross-check

Devify 已实现空间边界下的 Conversation、Message、Note、Event、Report 快照、Source 和上传解析基础模型与 API，并有本地测试覆盖。该设计仍不代表生产 MariaDB 迁移、Tauri 上传客户端、完整 AI 工作流、搜索索引或浏览器验收已经完成；这些继续作为独立交付门槛。
