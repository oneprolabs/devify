from datetime import datetime, time, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User

from chat_analysis.models import Event, Report, TopicSubscription
from chat_analysis.topic_scheduler import (
    NO_DATA_ERROR,
    run_due_topic_reports,
)
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db

UTC = datetime_timezone.utc


def make_space(owner, slug):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space,
        user=owner,
        role=SpaceMembership.Role.OWNER,
        status=SpaceMembership.Status.ACTIVE,
    )
    return space


def make_topic(space, owner, **overrides):
    values = {
        "space": space,
        "created_by": owner,
        "title": "客户日报",
        "instruction": "汇总客户进展",
        "period": TopicSubscription.Period.DAY,
        "time_local": time(9, 0),
        "timezone": "UTC",
    }
    values.update(overrides)
    return TopicSubscription.objects.create(**values)


def set_created_at(topic, value):
    TopicSubscription.objects.filter(pk=topic.pk).update(created_at=value)
    topic.refresh_from_db()


def add_event(space, owner, *, occurred_at):
    return Event.objects.create(
        space=space,
        created_by=owner,
        event_key=f"event-{occurred_at.isoformat()}",
        title="客户续约",
        content="客户确认下周讨论续约。",
        status=Event.Status.OPEN,
        last_activity_at=occurred_at,
    )


@pytest.mark.parametrize(
    ("period", "occurrence", "expected_start"),
    [
        (
            TopicSubscription.Period.DAY,
            datetime(2026, 11, 10, 9, 0, tzinfo=UTC),
            datetime(2026, 11, 9, 9, 0, tzinfo=UTC),
        ),
        (
            TopicSubscription.Period.WEEK,
            datetime(2026, 11, 9, 9, 0, tzinfo=UTC),
            datetime(2026, 11, 2, 9, 0, tzinfo=UTC),
        ),
        (
            TopicSubscription.Period.MONTH,
            datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
        ),
    ],
)
def test_scheduled_report_uses_the_period_window(
    period, occurrence, expected_start, django_capture_on_commit_callbacks
):
    owner = User.objects.create_user(username=f"schedule-{period}")
    space = make_space(owner, f"schedule-{period}")
    topic = make_topic(space, owner, period=period)
    set_created_at(topic, datetime(2026, 9, 1, tzinfo=UTC))
    now = occurrence + timedelta(minutes=5)
    add_event(space, owner, occurred_at=occurrence - timedelta(hours=1))

    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ) as dispatch, django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(now=now)

    assert stats["created"] == 1
    report = Report.objects.get(space=space)
    assert report.period_start == expected_start
    assert report.period_end == occurrence
    assert report.source_info["trigger"] == "schedule"
    assert report.source_info["subscription_id"] == topic.pk
    assert report.status == Report.Status.QUEUED
    dispatch.assert_called_once()

    topic.refresh_from_db()
    assert topic.last_run_at == occurrence

    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ) as second_dispatch, django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(now=now)

    assert stats["created"] == 0
    assert Report.objects.filter(space=space).count() == 1
    second_dispatch.assert_not_called()


def test_topic_does_not_run_before_its_first_scheduled_time(
    django_capture_on_commit_callbacks,
):
    owner = User.objects.create_user(username="schedule-before")
    space = make_space(owner, "schedule-before")
    topic = make_topic(space, owner)
    set_created_at(topic, datetime(2026, 11, 10, 0, 0, tzinfo=UTC))
    add_event(
        space,
        owner,
        occurred_at=datetime(2026, 11, 10, 8, 45, tzinfo=UTC),
    )

    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ), django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(
            now=datetime(2026, 11, 10, 8, 30, tzinfo=UTC)
        )
    assert stats["skipped"] == 1
    assert Report.objects.count() == 0

    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ), django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(
            now=datetime(2026, 11, 10, 9, 5, tzinfo=UTC)
        )
    assert stats["created"] == 1


def test_topic_schedule_respects_its_timezone(
    django_capture_on_commit_callbacks,
):
    owner = User.objects.create_user(username="schedule-timezone")
    space = make_space(owner, "schedule-timezone")
    topic = make_topic(space, owner, timezone="Asia/Shanghai")
    set_created_at(topic, datetime(2026, 11, 10, 0, 0, tzinfo=UTC))
    add_event(
        space,
        owner,
        occurred_at=datetime(2026, 11, 10, 0, 30, tzinfo=UTC),
    )

    # 00:30 UTC is 08:30 in Shanghai, before the 09:00 local schedule.
    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ), django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(
            now=datetime(2026, 11, 10, 0, 30, tzinfo=UTC)
        )
    assert stats["skipped"] == 1

    # 01:05 UTC is 09:05 in Shanghai.
    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ) as dispatch, django_capture_on_commit_callbacks(execute=True):
        stats = run_due_topic_reports(
            now=datetime(2026, 11, 10, 1, 5, tzinfo=UTC)
        )
    assert stats["created"] == 1
    dispatch.assert_called_once()


def test_topic_without_a_time_is_not_scheduled():
    owner = User.objects.create_user(username="schedule-no-time")
    space = make_space(owner, "schedule-no-time")
    make_topic(space, owner, time_local=None)

    stats = run_due_topic_reports(now=datetime(2026, 11, 10, 9, 5, tzinfo=UTC))

    assert stats["checked"] == 0
    assert Report.objects.count() == 0


def test_empty_period_is_skipped_without_calling_the_model():
    owner = User.objects.create_user(username="schedule-empty")
    space = make_space(owner, "schedule-empty")
    topic = make_topic(space, owner)
    set_created_at(topic, datetime(2026, 11, 1, tzinfo=UTC))

    with patch(
        "chat_analysis.topic_scheduler.dispatch_report_generation"
    ) as dispatch:
        stats = run_due_topic_reports(
            now=datetime(2026, 11, 10, 9, 5, tzinfo=UTC)
        )

    assert stats["empty"] == 1
    assert Report.objects.count() == 0
    dispatch.assert_not_called()
    topic.refresh_from_db()
    assert topic.last_error == NO_DATA_ERROR
    assert topic.last_run_at is not None


def test_topic_without_write_access_records_the_error_and_waits():
    owner = User.objects.create_user(username="schedule-owner")
    space = make_space(owner, "schedule-owner")
    topic = make_topic(space, owner)
    set_created_at(topic, datetime(2026, 11, 1, tzinfo=UTC))
    SpaceMembership.objects.filter(space=space, user=owner).delete()

    stats = run_due_topic_reports(now=datetime(2026, 11, 10, 9, 5, tzinfo=UTC))

    assert stats["failed"] == 1
    assert Report.objects.count() == 0
    topic.refresh_from_db()
    assert topic.last_run_at is not None
    assert "cannot write" in topic.last_error
