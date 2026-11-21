"""Queries services for upload batches."""

from django.db.models import Count

from chat_analysis.models import AnalysisJob, EventNote
from chat_domain.models import MessageOrigin, MessagePart


def _conversation_counts(batches):
    """Count the distinct conversations each batch contributed to.

    Counting through the serializer's relations would multiply the origin and
    part joins and took tens of seconds on a real space, so the page is counted
    in one grouped query instead.
    """
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    return dict(
        MessageOrigin.objects.filter(upload_item__batch_id__in=batch_ids)
        .values_list("upload_item__batch_id")
        .annotate(total=Count("message__conversation_id", distinct=True))
    )


def _image_counts(batches):
    """Count distinct image parts each upload batch contributed."""
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    return dict(
        MessagePart.objects.filter(
            upload_item__batch_id__in=batch_ids,
            kind=MessagePart.Kind.IMAGE,
        )
        .values_list("upload_item__batch_id")
        .annotate(total=Count("id", distinct=True))
    )


def _analysis_summaries(batches):
    """Summarise the analysis jobs and events each batch contributed.

    A reused job (same conversation digest uploaded again) can be linked to
    several batches, so event counts are assigned to every linked batch.
    """
    batch_ids = [batch.pk for batch in batches]
    if not batch_ids:
        return {}
    summaries = {
        batch_id: {
            "job_ids": set(),
            "states": [],
            "retried": False,
            "started_at": None,
            "finished_at": None,
        }
        for batch_id in batch_ids
    }
    job_batches = {}
    rows = AnalysisJob.objects.filter(upload_batches__id__in=batch_ids).values(
        "id",
        "state",
        "attempts",
        "created_at",
        "updated_at",
        "upload_batches__id",
    )
    for row in rows:
        batch_id = row["upload_batches__id"]
        summary = summaries[batch_id]
        summary["job_ids"].add(row["id"])
        summary["states"].append(row["state"])
        if row["attempts"] > 1 and row["state"] in (
            AnalysisJob.State.READY,
            AnalysisJob.State.PARTIAL,
        ):
            summary["retried"] = True
        started = summary["started_at"]
        if started is None or row["created_at"] < started:
            summary["started_at"] = row["created_at"]
        finished = summary["finished_at"]
        if finished is None or row["updated_at"] > finished:
            summary["finished_at"] = row["updated_at"]
        job_batches.setdefault(row["id"], set()).add(batch_id)

    events_by_batch = {batch_id: set() for batch_id in batch_ids}
    job_ids = list(job_batches)
    if job_ids:
        event_rows = (
            EventNote.objects.filter(note__analysis_job_id__in=job_ids)
            .values("note__analysis_job_id", "event_id")
            .distinct()
        )
        for row in event_rows:
            for batch_id in job_batches.get(row["note__analysis_job_id"], ()):
                events_by_batch[batch_id].add(row["event_id"])

    result = {}
    for batch_id, summary in summaries.items():
        states = summary["states"]
        queued = any(state == AnalysisJob.State.QUEUED for state in states)
        running = any(state == AnalysisJob.State.RUNNING for state in states)
        failed = any(
            state in (AnalysisJob.State.FAILED, AnalysisJob.State.CANCELLED)
            for state in states
        )
        partial = any(state == AnalysisJob.State.PARTIAL for state in states)
        if running:
            state = "running"
        elif queued:
            state = "queued"
        elif failed:
            state = "failed"
        elif partial:
            state = "partial"
        elif states:
            state = "ready"
        else:
            state = ""
        started = summary["started_at"]
        finished = summary["finished_at"]
        duration_seconds = None
        if started and finished and not running and not queued:
            duration_seconds = max(
                0, round((finished - started).total_seconds())
            )
        result[batch_id] = {
            "state": state,
            "job_count": len(summary["job_ids"]),
            "event_count": len(events_by_batch[batch_id]),
            "queued": queued,
            "running": running,
            "failed": failed,
            "partial": partial,
            "retried": summary["retried"],
            "duration_seconds": duration_seconds,
        }
    return result
