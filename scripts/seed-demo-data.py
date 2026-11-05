"""One-off demo data seeding for style comparison (space 3).

Run from the repository root:
  docker compose -f docker-compose.dev.yml exec -T devify-api bash -lc \
    'cd /opt/devify && PYTHONPATH=/opt/devify \
     DJANGO_SETTINGS_MODULE=core.settings \
     /opt/venv/bin/python manage.py shell' < scripts/seed-demo-data.py

Every row created here is prefixed with ``demo:`` (or marked with a ``demo``
key inside JSON fields) so it can be removed again. Re-running this script
resets the demo rows first.

Cleanup:
  docker compose -f docker-compose.dev.yml exec -T devify-api bash -lc \
    'cd /opt/devify && PYTHONPATH=/opt/devify \
     DJANGO_SETTINGS_MODULE=core.settings \
     /opt/venv/bin/python manage.py shell -c "
from chat_analysis.models import (
    Event, Report, TopicSubscription, QuestionAnswer
)
from chat_ingestion.models import UploadBatch
Event.objects.filter(space_id=3, event_key__startswith=\"demo:\").delete()
Report.objects.filter(
    space_id=3, request_key__startswith=\"demo:\"
).delete()
UploadBatch.objects.filter(
    space_id=3, idempotency_key__startswith=\"demo:\"
).delete()
[
    o.delete()
    for o in TopicSubscription.objects.filter(space_id=3)
    if (o.filters or {}).get(\"demo\")
]
[
    o.delete()
    for o in QuestionAnswer.objects.filter(space_id=3)
    if (o.usage or {}).get(\"demo\")
]
"'
"""

import datetime as dt

from django.utils import timezone

from chat_analysis.models import (
    Event,
    EventNote,
    EventTag,
    EventTagAssignment,
    QuestionAnswer,
    Report,
    TopicSubscription,
)
from chat_domain.models import Message
from chat_ingestion.models import UploadBatch
from spaces.models import Space

SPACE_ID = 3

space = Space.objects.get(pk=SPACE_ID)
actor = space.owner
now = timezone.now()
notes = {note.pk: note for note in space.chat_notes.all()}
note_ids = sorted(notes)
latest_messages = list(
    Message.objects.filter(conversation__space=space).order_by("-id")[:6]
)

# ---------------------------------------------------------------- reset demo
Event.objects.filter(space=space, event_key__startswith="demo:").delete()
for topic in TopicSubscription.objects.filter(space=space):
    if (topic.filters or {}).get("demo"):
        topic.delete()
Report.objects.filter(space=space, request_key__startswith="demo:").delete()
for question in QuestionAnswer.objects.filter(space=space):
    if (question.usage or {}).get("demo"):
        question.delete()
UploadBatch.objects.filter(
    space=space, idempotency_key__startswith="demo:"
).delete()

# -------------------------------------------------------------------- tags
tag_specs = [
    ("demo:customer", "客户"),
    ("demo:delivery", "交付"),
    ("demo:collab", "内部协作"),
    ("demo:finance", "财务"),
]
tags = {}
for key, label in tag_specs:
    tags[key], _ = EventTag.objects.update_or_create(
        space=space,
        tag_key=key,
        defaults={"created_by": actor, "label": label},
    )

# ------------------------------------------------------------------ events
event_specs = [
    {
        "key": "demo:saas-log-fix",
        "title": "客户追问 SaaS 日志采集故障的修复时间",
        "status": Event.Status.OPEN,
        "opened": now - dt.timedelta(days=3),
        "activity": now - dt.timedelta(minutes=35),
        "tags": ["demo:customer", "demo:delivery"],
        "notes": note_ids[-2:],
        "content": (
            "客户在群里第三次追问日志采集中断的修复时间，上周五的临时绕过方案已经失效。\n\n"
            "当前判断：采集侧连接池被打满，需要在今晚的窗口重启并补发补偿任务；修复窗口定在 20:30。\n\n"
            "下一步：把修复计划拆成「今晚恢复采集」和「本周根治连接池」两件事，先回客户确认窗口。"
        ),
    },
    {
        "key": "demo:review-1730",
        "title": "刘立祥请你 17:30 审一个需求",
        "status": Event.Status.OPEN,
        "opened": now - dt.timedelta(hours=6),
        "activity": now - dt.timedelta(hours=2),
        "tags": ["demo:collab"],
        "notes": note_ids[-1:],
        "content": (
            "刘立祥在群里 @ 你，希望今天 17:30 之前把「导出中心改版」的需求说明过一遍。\n\n"
            "他关心的是权限边界和导出落盘位置，其他部分已经和设计对齐。\n\n"
            "下一步：16:50 前给出结论，需要改动的地方直接批注在文档里。"
        ),
    },
    {
        "key": "demo:agi-overseas",
        "title": "AGIOne 海外方案英文版需在周五前交付",
        "status": Event.Status.IN_PROGRESS,
        "opened": now - dt.timedelta(days=5),
        "activity": now - dt.timedelta(days=1),
        "tags": ["demo:delivery", "demo:customer"],
        "notes": note_ids[-3:-1],
        "content": (
            "海外客户要求周五前拿到英文版方案，目前正文完成约 70%，案例和数据口径还需要统一。\n\n"
            "已确认：定价页沿用上一版结构，不要出现内部代号；案例部分只保留可公开的两个。\n\n"
            "下一步：周四下午出完整初稿，留半天做语言校对。"
        ),
    },
    {
        "key": "demo:latam-quote",
        "title": "LATAM 群内报价口径不一致",
        "status": Event.Status.OPEN,
        "opened": now - dt.timedelta(days=2),
        "activity": now - dt.timedelta(hours=6),
        "tags": ["demo:customer"],
        "notes": note_ids[-4:-2],
        "content": (
            "同一份报价在两个群里出现了不同版本，差额来自是否包含实施服务。\n\n"
            "风险：如果客户先看到低价版本，后续补差价会很被动。\n\n"
            "下一步：今天内统一定稿，明确实施服务单列，并把历史版本在群里撤回说明。"
        ),
    },
    {
        "key": "demo:invoice-oct",
        "title": "发票管家 10 月账单核对完成",
        "status": Event.Status.DONE,
        "opened": now - dt.timedelta(days=9),
        "activity": now - dt.timedelta(days=2),
        "tags": ["demo:finance"],
        "notes": note_ids[-5:-3],
        "content": (
            "10 月账单已逐张核对，差异集中在两张打车发票的税额四舍五入。\n\n"
            "结论：以财务系统为准，差额 0.42 元不做调整，报销单已归档。"
        ),
    },
    {
        "key": "demo:meeting-room",
        "title": "周三例会改用新会议室",
        "status": Event.Status.DONE,
        "opened": now - dt.timedelta(days=6),
        "activity": now - dt.timedelta(days=4),
        "tags": ["demo:collab"],
        "notes": note_ids[-6:-4],
        "content": (
            "原会议室当天被占用，会议已改到 3 楼小会议室，时间不变。\n\n"
            "结论：日程已更新，参会人都已确认收到。"
        ),
    },
]

created_events = []
for spec in event_specs:
    event = Event.objects.create(
        space=space,
        created_by=actor,
        event_key=spec["key"],
        title=spec["title"],
        content=spec["content"],
        status=spec["status"],
        opened_at=spec["opened"],
        last_activity_at=spec["activity"],
    )
    for tag_key in spec["tags"]:
        EventTagAssignment.objects.create(
            event=event, tag=tags[tag_key], created_by=actor
        )
    for note_id in spec["notes"]:
        if note_id in notes:
            EventNote.objects.create(
                event=event, note=notes[note_id], created_by=actor
            )
    created_events.append(event)

events_by_key = {event.event_key: event for event in created_events}

# ------------------------------------------------------------------ topics
topic_specs = [
    (
        "客户交付风险",
        "持续关注客户侧未回复的追问、交付延期和口径冲突，按天汇总。",
        TopicSubscription.Period.DAY,
        dt.time(9, 30),
        now - dt.timedelta(hours=5),
        "",
    ),
    (
        "项目进度周报",
        "每周汇总项目推进情况、阻塞点和下周计划。",
        TopicSubscription.Period.WEEK,
        dt.time(18, 0),
        now - dt.timedelta(days=1, hours=2),
        "",
    ),
    (
        "团队协作提醒",
        "关注需要我确认、审批或回复的内部协作请求。",
        TopicSubscription.Period.WEEK,
        dt.time(9, 0),
        now - dt.timedelta(days=2, hours=3),
        "",
    ),
    (
        "月度回顾",
        "每月整理关键进展、遗留问题和下月重点。",
        TopicSubscription.Period.MONTH,
        dt.time(10, 0),
        now - dt.timedelta(days=5),
        "",
    ),
]
for topic_filters, (
    title,
    instruction,
    period,
    run_time,
    last_run,
    last_error,
) in zip(
    [
        {"demo": True, "tag_keys": ["demo:customer"]},
        {"demo": True},
        {"demo": True, "tag_keys": ["demo:collab"]},
        {"demo": True},
    ],
    topic_specs,
):
    TopicSubscription.objects.create(
        space=space,
        created_by=actor,
        title=title,
        instruction=instruction,
        filters=dict(topic_filters),
        include_open=True,
        period=period,
        time_local=run_time,
        timezone="Asia/Shanghai",
        enabled=True,
        last_run_at=last_run,
        last_error=last_error,
    )

# ----------------------------------------------------------------- reports
report_specs = [
    {
        "key": "demo:report-daily-1101",
        "title": "客户交付日报 · 11/01",
        "start": dt.datetime(2026, 11, 1, 0, 0, tzinfo=dt.timezone.utc),
        "end": dt.datetime(2026, 11, 1, 23, 59, tzinfo=dt.timezone.utc),
        "generated": dt.datetime(2026, 11, 1, 15, 50, tzinfo=dt.timezone.utc),
        "body": (
            "今天的重点仍然在两件客户侧的事情上。\n\n"
            "1. 日志采集中断已经给出恢复窗口，客户确认今晚 20:30 执行；明早需要回传补发结果。\n"
            "2. LATAM 报价口径已完成统一，实施服务单列，历史版本已在群里说明。\n\n"
            "其余事项：AGIOne 英文方案推进到 70%，周四出初稿。"
        ),
    },
    {
        "key": "demo:report-weekly-44",
        "title": "LATAM 项目周报 · 第 44 周",
        "start": dt.datetime(2026, 10, 26, 0, 0, tzinfo=dt.timezone.utc),
        "end": dt.datetime(2026, 11, 1, 23, 59, tzinfo=dt.timezone.utc),
        "generated": dt.datetime(2026, 11, 2, 1, 12, tzinfo=dt.timezone.utc),
        "body": (
            "本周共跟进 6 个事项，其中 3 个仍需要我处理。\n\n"
            "进展：交付节奏整体可控，报价和版本说明已经统一；海外方案进入校对阶段。\n\n"
            "风险：日志采集的根因还没有彻底解决，下周需要安排一次专项复盘。\n\n"
            "下周计划：完成英文方案交付，把连接池问题收敛到可监控的指标上。"
        ),
    },
    {
        "key": "demo:report-monthly-10",
        "title": "10 月工作月报",
        "start": dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc),
        "end": dt.datetime(2026, 10, 31, 23, 59, tzinfo=dt.timezone.utc),
        "generated": dt.datetime(2026, 11, 1, 2, 5, tzinfo=dt.timezone.utc),
        "body": (
            "10 月主要完成了三件事：客户侧交付节奏稳定、账单核对流程跑通、海外方案完成中文定稿。\n\n"
            "遗留问题：跨群口径不一致仍然依赖人工发现，需要沉淀成固定检查项。\n\n"
            "11 月重点：把交付风险做成按天可见的清单，减少临时追问。"
        ),
    },
]
for spec in report_specs:
    Report.objects.create(
        space=space,
        created_by=actor,
        request_key=spec["key"],
        title=spec["title"],
        period_start=spec["start"],
        period_end=spec["end"],
        body_format=Report.BodyFormat.MARKDOWN,
        body=spec["body"],
        status=Report.Status.READY,
        generated_at=spec["generated"],
    )


# --------------------------------------------------------------- questions
def cite_event(key, excerpt):
    event = events_by_key[key]
    return {
        "kind": "event",
        "id": event.pk,
        "title": event.title,
        "excerpt": excerpt,
    }


def cite_message(message, excerpt):
    return {
        "kind": "message",
        "id": message.pk,
        "conversation_id": message.conversation_id,
        "title": message.sender_name or f"消息 #{message.pk}",
        "excerpt": excerpt,
    }


question_specs = [
    {
        "question": "这周客户有哪些没回复的问题？",
        "answer": (
            "这周客户侧有 2 个问题还在等回复。\n\n"
            "第一件是日志采集中断的修复时间，客户已经追问三次，今晚 20:30 的恢复窗口还没得到正式确认。\n"
            "第二件是 LATAM 群的报价口径，两个版本同时存在，需要今天内统一定稿并说明差异。\n\n"
            "建议先处理报价，因为它会直接影响后续签约节奏。"
        ),
        "citations": [
            cite_event(
                "demo:saas-log-fix",
                "客户第三次追问修复时间，临时绕过方案已失效。",
            ),
            cite_event(
                "demo:latam-quote",
                "同一份报价出现两个版本，差额来自实施服务。",
            ),
            cite_message(
                latest_messages[0],
                "麻烦确认一下今晚能不能恢复，我们这边在等。",
            ),
        ],
        "scope": {"event_ids": [], "note_ids": [], "conversation_ids": []},
        "created": now - dt.timedelta(hours=3),
    },
    {
        "question": "最近有哪些事情需要我跟进？",
        "answer": (
            "目前有 3 件事需要你本人推进。\n\n"
            "1. 今天 17:30 前审「导出中心改版」需求，重点看权限边界。\n"
            "2. 确认日志采集的恢复窗口，并在明早回传补发结果。\n"
            "3. 周四下午产出 AGIOne 英文方案完整初稿。\n\n"
            "其余两件事已经完成，不需要再投入时间。"
        ),
        "citations": [
            cite_event(
                "demo:review-1730", "刘立祥希望今天 17:30 前过一遍需求说明。"
            ),
            cite_event(
                "demo:saas-log-fix", "修复窗口定在 20:30，需要客户确认。"
            ),
            cite_event(
                "demo:agi-overseas", "英文版方案周五前交付，正文完成约 70%。"
            ),
        ],
        "scope": {"event_ids": [], "note_ids": [], "conversation_ids": []},
        "created": now - dt.timedelta(days=1, hours=4),
    },
    {
        "question": "哪些事件已经完成但还没有结论？",
        "answer": (
            "已完成的事件里，有一个缺少明确结论。\n\n"
            "「周三例会改用新会议室」只记录了变更结果，没有留下后续影响，可以直接补一句「无需跟踪」结案。\n\n"
            "「发票管家 10 月账单核对」已经有结论，差额 0.42 元不调整，可以归档。"
        ),
        "citations": [
            cite_event(
                "demo:meeting-room", "会议室变更已通知，参会人确认收到。"
            ),
            cite_event(
                "demo:invoice-oct", "账单差异 0.42 元，以财务系统为准。"
            ),
        ],
        "scope": {"event_ids": [], "note_ids": [], "conversation_ids": []},
        "created": now - dt.timedelta(days=3),
    },
]

for spec in question_specs:
    answer = QuestionAnswer.objects.create(
        space=space,
        created_by=actor,
        question=spec["question"],
        scope=spec["scope"],
        answer=spec["answer"],
        citations=spec["citations"],
        usage={
            "demo": True,
            "prompt_tokens": 1840,
            "completion_tokens": 320,
            "total_tokens": 2160,
        },
        status=QuestionAnswer.Status.READY,
    )
    QuestionAnswer.objects.filter(pk=answer.pk).update(
        created_at=spec["created"]
    )

# ----------------------------------------------------------------- uploads
upload_specs = [
    (
        "demo:sync-whatsapp-1102",
        UploadBatch.SourceType.WHATSAPP,
        412,
        UploadBatch.Status.COMPLETED,
        now - dt.timedelta(hours=4),
        "",
    ),
    (
        "demo:sync-wechat-1101",
        UploadBatch.SourceType.WECHAT,
        96,
        UploadBatch.Status.COMPLETED,
        now - dt.timedelta(days=1, hours=6),
        "",
    ),
    (
        "demo:sync-wechat-1030",
        UploadBatch.SourceType.WECHAT,
        0,
        UploadBatch.Status.FAILED,
        now - dt.timedelta(days=3),
        "压缩包缺少会话索引文件，已跳过本次同步。",
    ),
]
for key, source_type, count, status, created, error in upload_specs:
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=actor,
        source_type=source_type,
        idempotency_key=key,
        status=status,
        message_count=count,
        error_message=error,
    )
    UploadBatch.objects.filter(pk=batch.pk).update(created_at=created)

print(
    "demo data seeded:",
    {
        "events": Event.objects.filter(
            space=space, event_key__startswith="demo:"
        ).count(),
        "topics": sum(
            1
            for t in TopicSubscription.objects.filter(space=space)
            if (t.filters or {}).get("demo")
        ),
        "reports": Report.objects.filter(
            space=space, request_key__startswith="demo:"
        ).count(),
        "questions": sum(
            1
            for q in QuestionAnswer.objects.filter(space=space)
            if (q.usage or {}).get("demo")
        ),
        "uploads": UploadBatch.objects.filter(
            space=space, idempotency_key__startswith="demo:"
        ).count(),
    },
)
