"""Seed four example topic subscriptions and their reports for space 46.

Run from the repository root:
  docker compose -f docker-compose.dev.yml exec -T devify-api bash -lc \
    'cd /opt/devify && PYTHONPATH=/opt/devify DJANGO_SETTINGS_MODULE=core.settings \
     /opt/venv/bin/python manage.py shell' < scripts/seed-topic-examples.py

Every row is demo-marked (request_key ``demo:topic:*``, ``filters.demo``,
``processing.demo``) so it can be removed again. Re-running resets the demo
rows first.

Cleanup:
  Report.objects.filter(space_id=46, request_key__startswith="demo:topic:").delete()
  [t.delete() for t in TopicSubscription.objects.filter(space_id=46)
   if (t.filters or {}).get("demo")]
"""

import datetime as dt
from zoneinfo import ZoneInfo

from django.utils import timezone

from chat_analysis.models import (
    Event,
    Report,
    ReportItem,
    ReportItemSource,
    ReportSection,
    TopicSubscription,
)
from spaces.models import Space

SPACE_ID = 46
SHANGHAI = ZoneInfo("Asia/Shanghai")
space = Space.objects.get(pk=SPACE_ID)
actor = space.owner
now = timezone.now()

# ---------------------------------------------------------------- reset demo
Report.objects.filter(
    space=space, request_key__startswith="demo:topic:"
).delete()
for topic in TopicSubscription.objects.filter(space=space, created_by=actor):
    if (topic.filters or {}).get("demo"):
        topic.delete()

events = {event.pk: event for event in Event.objects.filter(space=space)}


def at_local(day, hour=0, minute=0):
    return dt.datetime(
        day.year, day.month, day.day, hour, minute, tzinfo=SHANGHAI
    )


def snapshot(event):
    return {
        "id": event.pk,
        "uuid": str(event.uuid),
        "title": event.title,
        "content": event.content,
        "status": event.status,
        "opened_at": event.opened_at.isoformat() if event.opened_at else None,
        "last_activity_at": (
            event.last_activity_at.isoformat()
            if event.last_activity_at
            else None
        ),
    }


def build_report(topic, spec):
    report = Report.objects.create(
        space=space,
        created_by=actor,
        request_key=f"demo:topic:{spec['key']}",
        title=spec["title"],
        period_start=spec["period_start"],
        period_end=spec["period_end"],
        body_format=Report.BodyFormat.MARKDOWN,
        body=spec["body"],
        status=Report.Status.READY,
        generated_at=now,
        content={
            "section_count": len(spec["sections"]),
            "item_count": sum(len(s["items"]) for s in spec["sections"]),
            "event_count": len(
                {i["event_id"] for s in spec["sections"] for i in s["items"] if i.get("event_id")}
            ),
            "note_count": 0,
        },
        snapshot_ref={
            "schema_version": "report.v1",
            "generated_at": now.isoformat(),
            "event_ids": sorted(
                {
                    i["event_id"]
                    for s in spec["sections"]
                    for i in s["items"]
                    if i.get("event_id")
                }
            ),
        },
        source_info={
            "kind": "topic_subscription",
            "subscription_id": topic.pk,
            "demo": True,
        },
        processing={
            "generator": "example",
            "version": "example.v1",
            "demo": True,
        },
    )
    for index, section_spec in enumerate(spec["sections"]):
        section = ReportSection.objects.create(
            report=report,
            section_key=section_spec["key"],
            title=section_spec["title"],
            position=index,
        )
        for position, item_spec in enumerate(section_spec["items"]):
            item = ReportItem.objects.create(
                section=section,
                position=position,
                title=item_spec["title"],
                summary=item_spec["summary"],
                label=item_spec.get("label", ""),
                time_text=item_spec.get("time_text", ""),
                contact_text=item_spec.get("contact_text", ""),
                followup_text=item_spec.get("followup_text", ""),
                followup_kind=item_spec.get("followup_kind", ""),
                display_kind="event",
            )
            event = events.get(item_spec.get("event_id"))
            if event:
                ReportItemSource.objects.create(
                    item=item,
                    reference_key=f"event:{event.pk}",
                    source_kind=ReportItemSource.SourceKind.EVENT,
                    event=event,
                    event_snapshot=snapshot(event),
                )
            else:
                ReportItemSource.objects.create(
                    item=item,
                    reference_key=f"demo:reference:{item.pk}",
                    source_kind=ReportItemSource.SourceKind.REFERENCE,
                    display_text=item_spec.get("reference", ""),
                )
    topic.last_run_at = now
    topic.save(update_fields=("last_run_at", "updated_at"))
    return report


TOPICS = [
    {
        "key": "imss-weekly",
        "title": "IMSS 交付周报",
        "instruction": (
            "只列未闭环事项；按项目分组；标出客户在等我们回复的；"
            "已闭环的只留一行；每条注明最近进展时间和负责方向。"
        ),
        "filters": {"demo": True, "tag_keys": ["imss"]},
        "period": TopicSubscription.Period.WEEK,
        "time_local": dt.time(9, 0),
        "report": {
            "key": "imss-weekly",
            "title": "IMSS 交付周报 · 2026-10-27 ~ 11-02",
            "period_start": at_local(dt.date(2026, 10, 27)),
            "period_end": at_local(dt.date(2026, 11, 3)),
            "body": """# IMSS 交付周报 · 2026-10-27 ~ 11-02
范围：标签 IMSS · 未闭环 6 项 / 已闭环 1 项

## 需要你决策 / 回复（2）
- HCS 虚拟机访问华为云 lite-server 异常 — 进行中 4 天，客户在等方案（10-30）
- 剩余 A10 纳管方案与客户材料准备 — 客户材料待确认（10-30）

## 本周有进展（2）
- 每月 DR 报告发送与报告模板优化 — 模板调整中（10-30）
- AICoding 材料与 DeepSeek/GLM 昇腾 PoC — 测试计划推进（10-23）

## 停滞风险（2）
- HCS 存储 License 到期影响扩容升级 — 42 天无更新（09-22）
- 紧急 WhatsApp Chatbot 需求配合 — 10 天无更新（10-24）

## 已闭环（1）
- AGIOne 环境扩容与调优模型部署压测 — 11-02 完成""",
            "sections": [
                {
                    "key": "decide",
                    "title": "需要你决策 / 回复",
                    "items": [
                        {
                            "event_id": 313,
                            "title": "HCS 虚拟机访问华为云 lite-server 异常",
                            "summary": "进行中 4 天，客户在等方案。",
                            "label": "IMSS",
                            "time_text": "10-30",
                            "followup_text": "确认方案并回复客户",
                            "followup_kind": "reply",
                        },
                        {
                            "event_id": 312,
                            "title": "IMSS 剩余 A10 纳管方案与客户材料准备",
                            "summary": "客户材料待确认。",
                            "label": "IMSS",
                            "time_text": "10-30",
                            "followup_text": "确认材料后发出",
                            "followup_kind": "reply",
                        },
                    ],
                },
                {
                    "key": "progress",
                    "title": "本周有进展",
                    "items": [
                        {
                            "event_id": 310,
                            "title": "IMSS 每月 DR 报告发送与报告模板优化",
                            "summary": "模板调整中。",
                            "label": "IMSS",
                            "time_text": "10-30",
                        },
                        {
                            "event_id": 305,
                            "title": "IMSS AICoding 材料与 DeepSeek/GLM 昇腾 PoC",
                            "summary": "测试计划推进。",
                            "label": "IMSS",
                            "time_text": "10-23",
                        },
                    ],
                },
                {
                    "key": "risk",
                    "title": "停滞风险",
                    "items": [
                        {
                            "event_id": 295,
                            "title": "IMSS HCS 存储 License 到期影响扩容升级",
                            "summary": "42 天无更新，需确认是否仍有效。",
                            "label": "IMSS",
                            "time_text": "09-22",
                        },
                        {
                            "event_id": 307,
                            "title": "IMSS 紧急 WhatsApp Chatbot 需求配合",
                            "summary": "10 天无更新。",
                            "label": "IMSS",
                            "time_text": "10-24",
                        },
                    ],
                },
                {
                    "key": "done",
                    "title": "已闭环",
                    "items": [
                        {
                            "event_id": 306,
                            "title": "IMSS AGIOne 环境扩容与调优模型部署压测",
                            "summary": "11-02 完成。",
                            "label": "IMSS",
                            "time_text": "11-02",
                        },
                    ],
                },
            ],
        },
    },
    {
        "key": "support-daily",
        "title": "未闭环客户问题日报",
        "instruction": (
            "只列 open/in_progress；超过 3 天没更新标为停滞；按客户归组；"
            "不要写已闭环内容。"
        ),
        "filters": {
            "demo": True,
            "tag_keys": ["客户"],
            "keywords": ["INC"],
        },
        "period": TopicSubscription.Period.DAY,
        "time_local": dt.time(9, 0),
        "report": {
            "key": "support-daily",
            "title": "未闭环客户问题日报 · 2026-11-03",
            "period_start": at_local(dt.date(2026, 11, 2)),
            "period_end": at_local(dt.date(2026, 11, 3)),
            "body": """# 未闭环客户问题日报 · 2026-11-03
范围：标签 客户 + 关键词 INC · 停滞 3 / 进行中 2

## 停滞 > 3 天（3）
- 博枫客户 Ubuntu 22.04 内核升级后同步失败 — 138 天无更新（06-18）
- 博枫客户腾讯云上海对象存储上传镜像报网络慢 — 133 天无更新（06-23）
- 博枫环境网络中断后全量重跑与 VSS 快照异常 — 126 天无更新（06-30）

## 进行中（2）
- IMSS 备份项目 Agentless 版本适配 — 14 天无更新（10-20）
- IMSS 紧急 WhatsApp Chatbot 需求配合 — 10 天无更新（10-24）

## 今日新增（0）""",
            "sections": [
                {
                    "key": "stalled",
                    "title": "停滞 > 3 天",
                    "items": [
                        {
                            "event_id": 332,
                            "title": "博枫客户 Ubuntu 22.04 内核升级后同步失败",
                            "summary": "138 天无更新，建议确认是否已关闭。",
                            "label": "博枫",
                            "time_text": "06-18",
                        },
                        {
                            "event_id": 333,
                            "title": "博枫客户腾讯云上海对象存储上传镜像报网络慢",
                            "summary": "133 天无更新。",
                            "label": "博枫",
                            "time_text": "06-23",
                        },
                        {
                            "event_id": 338,
                            "title": "博枫环境网络中断后全量重跑与 VSS 快照异常",
                            "summary": "126 天无更新。",
                            "label": "博枫",
                            "time_text": "06-30",
                        },
                    ],
                },
                {
                    "key": "active",
                    "title": "进行中",
                    "items": [
                        {
                            "event_id": 286,
                            "title": "IMSS 备份项目 Agentless 版本适配",
                            "summary": "14 天无更新。",
                            "label": "IMSS",
                            "time_text": "10-20",
                        },
                        {
                            "event_id": 307,
                            "title": "IMSS 紧急 WhatsApp Chatbot 需求配合",
                            "summary": "10 天无更新。",
                            "label": "IMSS",
                            "time_text": "10-24",
                        },
                    ],
                },
            ],
        },
    },
    {
        "key": "business-weekly",
        "title": "商务与报价周报",
        "instruction": (
            "列报价阶段、待客户确认项、需要内部审批的折扣和下一步动作。"
        ),
        "filters": {
            "demo": True,
            "tag_keys": ["报价"],
            "keywords": ["合同", "折扣", "license"],
        },
        "period": TopicSubscription.Period.WEEK,
        "time_local": dt.time(17, 0),
        "report": {
            "key": "business-weekly",
            "title": "商务与报价周报 · 2026-10-27 ~ 11-02",
            "period_start": at_local(dt.date(2026, 10, 27)),
            "period_end": at_local(dt.date(2026, 11, 3)),
            "body": """# 商务与报价周报 · 2026-10-27 ~ 11-02
范围：标签 报价 + 关键词 合同/折扣/license

## 待客户确认（2）
- Bafar VMware 到阿里云容灾方案确认 — 62 天无更新（09-02）
- Antel 项目商务与合同推进 — 合同/SOW/服务责任矩阵待确认（10-16）

## 待内部审批（1）
- KIO HyperMotion 授权与折扣沟通 — 折扣口径待定（09-14）

## 本周变化（1）
- Antel 新渠道演示与交付维护责任沟通 — 演示后责任边界待明确（10-01）""",
            "sections": [
                {
                    "key": "customer",
                    "title": "待客户确认",
                    "items": [
                        {
                            "event_id": 287,
                            "title": "Bafar VMware 到阿里云容灾方案确认",
                            "summary": "62 天无更新，建议确认客户是否仍在推进。",
                            "label": "Bafar",
                            "time_text": "09-02",
                        },
                        {
                            "event_id": 283,
                            "title": "Antel 项目商务与合同推进",
                            "summary": "合同/SOW/服务责任矩阵待确认。",
                            "label": "Antel",
                            "time_text": "10-16",
                            "followup_text": "确认合同与服务责任矩阵",
                            "followup_kind": "reply",
                        },
                    ],
                },
                {
                    "key": "approval",
                    "title": "待内部审批",
                    "items": [
                        {
                            "event_id": 292,
                            "title": "KIO HyperMotion 授权与折扣沟通",
                            "summary": "折扣口径待定。",
                            "label": "KIO",
                            "time_text": "09-14",
                        },
                    ],
                },
                {
                    "key": "changes",
                    "title": "本周变化",
                    "items": [
                        {
                            "event_id": 300,
                            "title": "Antel 新渠道演示与交付维护责任沟通",
                            "summary": "演示后责任边界待明确。",
                            "label": "Antel",
                            "time_text": "10-01",
                        },
                    ],
                },
            ],
        },
    },
    {
        "key": "my-actions-daily",
        "title": "等我处理",
        "instruction": (
            "只列需要我回复或决策的；写清对方在等什么；别人负责的不要列。"
        ),
        "filters": {
            "demo": True,
            "tag_keys": ["客户"],
            "keywords": ["确认", "回复", "待"],
        },
        "period": TopicSubscription.Period.DAY,
        "time_local": dt.time(8, 30),
        "report": {
            "key": "my-actions-daily",
            "title": "等我处理 · 2026-11-03",
            "period_start": at_local(dt.date(2026, 11, 2)),
            "period_end": at_local(dt.date(2026, 11, 3)),
            "body": """# 等我处理 · 2026-11-03
范围：标签 客户 + 关键词 确认/回复/待

## 对方在等我（3）
- HCS 虚拟机访问华为云 lite-server 异常 — 客户在等方案（10-30）
- Infotec 客户高层汇报材料与 Demo 录屏准备 — 待你确认口径（11-01）
- Antel 项目商务与合同推进 — 合同与服务责任矩阵待你确认（10-16）

## 今天最好处理（1）
- IMSS 剩余 A10 纳管方案与客户材料准备 — 客户材料待发（10-30）

## 可以放一放（2）
- 博枫三条历史问题 — 长期停滞，建议确认是否已关闭""",
            "sections": [
                {
                    "key": "waiting",
                    "title": "对方在等我",
                    "items": [
                        {
                            "event_id": 313,
                            "title": "HCS 虚拟机访问华为云 lite-server 异常",
                            "summary": "客户在等方案。",
                            "label": "IMSS",
                            "time_text": "10-30",
                            "followup_text": "回复客户方案",
                            "followup_kind": "reply",
                        },
                        {
                            "event_id": 308,
                            "title": "Infotec 客户高层汇报材料与 Demo 录屏准备",
                            "summary": "待你确认口径。",
                            "label": "Infotec",
                            "time_text": "11-01",
                            "followup_text": "确认汇报口径",
                            "followup_kind": "decide",
                        },
                        {
                            "event_id": 283,
                            "title": "Antel 项目商务与合同推进",
                            "summary": "合同与服务责任矩阵待你确认。",
                            "label": "Antel",
                            "time_text": "10-16",
                            "followup_text": "确认合同与服务责任矩阵",
                            "followup_kind": "decide",
                        },
                    ],
                },
                {
                    "key": "today",
                    "title": "今天最好处理",
                    "items": [
                        {
                            "event_id": 312,
                            "title": "IMSS 剩余 A10 纳管方案与客户材料准备",
                            "summary": "客户材料待发。",
                            "label": "IMSS",
                            "time_text": "10-30",
                            "followup_text": "发出客户材料",
                            "followup_kind": "reply",
                        },
                    ],
                },
                {
                    "key": "later",
                    "title": "可以放一放",
                    "items": [
                        {
                            "event_id": 332,
                            "title": "博枫三条历史问题",
                            "summary": "长期停滞，建议确认是否已关闭。",
                            "label": "博枫",
                            "time_text": "06-18",
                            "reference": "博枫 Ubuntu 内核升级、对象存储上传慢、VSS 快照异常",
                        },
                    ],
                },
            ],
        },
    },
]

for spec in TOPICS:
    topic = TopicSubscription.objects.create(
        space=space,
        created_by=actor,
        title=spec["title"],
        instruction=spec["instruction"],
        filters=spec["filters"],
        include_open=True,
        period=spec["period"],
        time_local=spec["time_local"],
        timezone="Asia/Shanghai",
        enabled=True,
    )
    report = build_report(topic, spec["report"])
    print(
        f"topic={topic.pk} {topic.title} -> report={report.pk} "
        f"{report.title}"
    )

print(
    "done: topics=%s reports=%s"
    % (
        TopicSubscription.objects.filter(
            space=space, filters__demo=True
        ).count(),
        Report.objects.filter(
            space=space, request_key__startswith="demo:topic:"
        ).count(),
    )
)
