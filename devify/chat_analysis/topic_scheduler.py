"""Run recurring topic subscriptions on the server-side schedule.

The desktop client used to build its daily summary locally and mail it to
Devify. The server already owns the imported chat data, notes, events and
reports, so a topic subscription is the natural place to keep the schedule:
``period``, ``time_local`` and ``timezone`` describe when a report is due,
and ``last_run_at`` records the occurrence that was already handled.

The scheduler only creates the report snapshot and queues the existing LLM
generation task. It never reads the desktop's local database.
"""

import calendar
import logging
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from chat_analysis.models import Report, TopicSubscription
from chat_analysis.report_services import create_report_snapshot
from chat_analysis.report_tasks import dispatch_report_generation
from chat_analysis.services import (
    ChatAnalysisConflict,
    ChatAnalysisPermissionError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = getattr(settings, "TIME_ZONE", "Asia/Shanghai")
NO_DATA_ERROR = "No matching events or notes."


def _zone(name):
    """Return a usable timezone, falling back to the project default."""

    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def _at(local_date, local_time, zone):
    return datetime.combine(local_date, local_time, tzinfo=zone)


def _latest_occurrence(topic, now):
    """Return the newest scheduled time at or before ``now``.

    Weekly topics run on Monday and monthly topics on the first day of the
    month because the model only stores a time of day, not a weekday or day
    of month.
    """

    if topic.time_local is None:
        return None
    zone = _zone(topic.timezone)
    local_now = now.astimezone(zone)
    moment = topic.time_local
    if topic.period == TopicSubscription.Period.DAY:
        occurrence = _at(local_now.date(), moment, zone)
        if occurrence > local_now:
            occurrence = _at(
                local_now.date() - timedelta(days=1), moment, zone
            )
        return occurrence
    if topic.period == TopicSubscription.Period.WEEK:
        monday = local_now.date() - timedelta(days=local_now.weekday())
        occurrence = _at(monday, moment, zone)
        if occurrence > local_now:
            occurrence = _at(monday - timedelta(days=7), moment, zone)
        return occurrence
    first = local_now.date().replace(day=1)
    occurrence = _at(first, moment, zone)
    if occurrence > local_now:
        previous = first - timedelta(days=1)
        occurrence = _at(previous.replace(day=1), moment, zone)
    return occurrence


def _shift_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def period_window(topic, occurrence):
    """Return the reporting window ending at ``occurrence``.

    A daily report covers the previous 24 hours, a weekly report the previous
    seven days and a monthly report the previous calendar month. Using the
    occurrence as the end keeps consecutive reports contiguous.
    """

    if topic.period == TopicSubscription.Period.DAY:
        return occurrence - timedelta(days=1), occurrence
    if topic.period == TopicSubscription.Period.WEEK:
        return occurrence - timedelta(days=7), occurrence
    return _shift_months(occurrence, -1), occurrence


def _is_due(topic, occurrence):
    if occurrence is None or not topic.enabled:
        return False
    # Do not backfill occurrences from before the subscription existed.
    if occurrence < topic.created_at:
        return False
    return topic.last_run_at is None or topic.last_run_at < occurrence


def _report_key(topic, occurrence):
    stamp = occurrence.astimezone(datetime_timezone.utc).strftime(
        "%Y%m%d%H%M%S"
    )
    return f"topic-{topic.pk}-{stamp}"


def _mark_done(topic, occurrence, error=""):
    topic.last_run_at = occurrence
    topic.last_error = error
    topic.save(update_fields=("last_run_at", "last_error", "updated_at"))


def _dispatch(report):
    try:
        dispatch_report_generation(report)
    except Exception:
        # The report is already committed as queued. The stale-task sweep
        # will close it if the broker never accepts the task.
        logger.exception(
            "Failed to dispatch scheduled report %s", report.pk
        )


def _run_topic(topic_id, now):
    with transaction.atomic():
        topic = (
            TopicSubscription.objects.select_for_update(skip_locked=True)
            .select_related("space", "created_by")
            .get(pk=topic_id)
        )
        occurrence = _latest_occurrence(topic, now)
        if not _is_due(topic, occurrence):
            return {"status": "skipped"}

        period_start, period_end = period_window(topic, occurrence)
        report, created = create_report_snapshot(
            actor=topic.created_by,
            space=topic.space,
            request_key=_report_key(topic, occurrence),
            title=topic.title,
            period_start=period_start,
            period_end=period_end,
            filters=topic.filters,
            include_open=topic.include_open,
        )
        if created and not (report.content or {}).get("item_count"):
            # A scheduled report without matching notes or events would just
            # call the model with an empty payload. Skip it until next time.
            report.delete()
            _mark_done(topic, occurrence, NO_DATA_ERROR)
            return {"status": "empty"}

        generator = (report.processing or {}).get("generator")
        needs_generation = not (
            report.status == Report.Status.READY and generator == "llm"
        )
        if created:
            report.source_info = {
                **(report.source_info or {}),
                "kind": "topic_subscription",
                "subscription_id": topic.pk,
                "trigger": "schedule",
                "scheduled_for": occurrence.isoformat(),
            }
            report.status = Report.Status.QUEUED
            report.processing = {
                **(report.processing or {}),
                "generator": "llm_pending",
                "version": "report.llm.v1",
            }
            report.save(
                update_fields=(
                    "source_info",
                    "status",
                    "processing",
                    "updated_at",
                )
            )
        if needs_generation:
            transaction.on_commit(lambda report=report: _dispatch(report))

        _mark_done(topic, occurrence)
        return {
            "status": "created" if created else "reused",
            "report_id": report.pk,
        }


def _record_failure(topic_id, now, error, *, advance):
    topic = TopicSubscription.objects.filter(pk=topic_id).first()
    if topic is None:
        return
    fields = {
        "last_error": str(error)[:2000],
        "updated_at": timezone.now(),
    }
    if advance:
        occurrence = _latest_occurrence(topic, now)
        if occurrence is not None:
            fields["last_run_at"] = occurrence
    TopicSubscription.objects.filter(pk=topic_id).update(**fields)


def run_due_topic_reports(now=None):
    """Create reports for every topic whose scheduled time has passed."""

    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, datetime_timezone.utc)
    topic_ids = list(
        TopicSubscription.objects.filter(
            enabled=True, time_local__isnull=False
        ).values_list("pk", flat=True)
    )
    stats = {
        "checked": len(topic_ids),
        "created": 0,
        "reused": 0,
        "empty": 0,
        "skipped": 0,
        "failed": 0,
    }
    for topic_id in topic_ids:
        try:
            outcome = _run_topic(topic_id, now)
        except (ChatAnalysisPermissionError, ChatAnalysisConflict) as error:
            # The owner cannot write to the space any more, or the request key
            # collides with a different report. Wait for the next period
            # instead of retrying every minute.
            _record_failure(topic_id, now, error, advance=True)
            stats["failed"] += 1
            continue
        except Exception as error:
            # Transient failures (database, dispatch) should be retried on the
            # next tick, so keep last_run_at unchanged.
            logger.exception(
                "Scheduled topic report failed for topic %s", topic_id
            )
            _record_failure(topic_id, now, error, advance=False)
            stats["failed"] += 1
            continue
        stats[outcome["status"]] += 1
    return stats
