from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from chat_analysis.schedule_window import due_slot, parse_schedule
from chat_analysis.scheduled_dispatch import ensure_due_run


def test_schedule_uses_beijing_time_independent_of_input_timezone():
    assert due_slot(datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)) == "2026-11-17T11:00+08:00"
    assert due_slot(datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)) == "2026-11-17T18:00+08:00"
    # A minute late still belongs to 11:00. 10:59 belongs to the previous 18:00.
    assert due_slot(datetime(2026, 11, 17, 11, 1, tzinfo=ZoneInfo("Asia/Shanghai"))) == "2026-11-17T11:00+08:00"
    assert due_slot(datetime(2026, 11, 17, 2, 59, tzinfo=timezone.utc)) == "2026-11-16T18:00+08:00"


def test_schedule_is_configurable_and_validated():
    assert parse_schedule("09:30,18:00") == ((9, 30), (18, 0))
    assert due_slot(datetime(2026, 11, 17, 1, 30, tzinfo=timezone.utc), "09:30,18:00") == "2026-11-17T09:30+08:00"
    for invalid in ("", "24:00", "11:60", "11:00,11:00", "11:0"):
        with pytest.raises(ValueError):
            parse_schedule(invalid)


@pytest.mark.django_db
def test_dispatch_uses_deployment_schedule(settings):
    settings.CHAT_ANALYSIS_SCHEDULE = "09:30,18:00"
    run = ensure_due_run(datetime(2026, 11, 17, 1, 40, tzinfo=timezone.utc))
    assert run.slot == "2026-11-17T09:30+08:00"


def test_naive_datetime_is_not_accepted():
    with pytest.raises(ValueError):
        due_slot(datetime(2026, 11, 17, 11))


@pytest.mark.django_db
def test_one_persistent_run_per_slot_uses_the_slot_clock():
    first = datetime(2026, 11, 17, 3, 0, 10, tzinfo=timezone.utc)
    same_slot = datetime(2026, 11, 17, 3, 40, tzinfo=timezone.utc)
    run = ensure_due_run(first)
    assert run is not None
    assert ensure_due_run(same_slot).pk == run.pk
    run.refresh_from_db()
    assert run.boundary == datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)
    evening = ensure_due_run(datetime(2026, 11, 17, 10, 5, tzinfo=timezone.utc))
    assert evening.pk != run.pk
    assert evening.boundary == datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)
