"""Celery tasks for LLM-backed report generation."""

import json

from celery import shared_task
from django.utils import timezone

from chat_analysis.models import Report
from core.tracking import LLMTracker

REPORT_PROMPT = """You generate a concise work report from structured
events and notes.
Return a JSON object with exactly these fields:
- body: markdown report body
- sections: list of objects with section_key, title, and items
Each item must contain title and summary, and may contain label, time_text,
contact_text, followup_text, followup_kind, and display_kind.
Do not invent facts, owners, dates, or commitments not present in the input.
Preserve uncertainty and distinguish suggestions from confirmed facts.
"""


def _report_input(report):
    sections = []
    for section in report.sections.all():
        items = []
        for item in section.items.all():
            items.append(
                {
                    "title": item.title,
                    "summary": item.summary,
                    "label": item.label,
                    "time_text": item.time_text,
                    "contact_text": item.contact_text,
                    "followup_text": item.followup_text,
                    "followup_kind": item.followup_kind,
                    "display_kind": item.display_kind,
                    "sources": [
                        {
                            "kind": source.source_kind,
                            "event": source.event_snapshot,
                            "note": source.note_snapshot,
                        }
                        for source in item.sources.all()
                    ],
                }
            )
        sections.append(
            {
                "section_key": section.section_key,
                "title": section.title,
                "items": items,
            }
        )
    return {
        "title": report.title,
        "period_start": (
            report.period_start.isoformat() if report.period_start else None
        ),
        "period_end": (
            report.period_end.isoformat() if report.period_end else None
        ),
        "sections": sections,
    }


def _validate_output(output):
    if not isinstance(output, dict):
        raise ValueError("The report model did not return an object.")
    body = output.get("body")
    sections = output.get("sections")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("The report model returned an empty body.")
    if not isinstance(sections, list):
        raise ValueError("The report model returned invalid sections.")
    return body.strip(), sections


@shared_task(bind=True, max_retries=2)
def generate_report_task(self, report_id):
    report = Report.objects.prefetch_related("sections__items__sources").get(
        pk=report_id
    )
    if (
        report.status == Report.Status.READY
        and report.processing.get("generator") == "llm"
    ):
        return {"report_id": report.pk, "status": report.status}

    report.status = Report.Status.QUEUED
    report.processing = {
        **(report.processing or {}),
        "generator": "llm_pending",
        "version": "report.llm.v1",
    }
    report.save(update_fields=("status", "processing", "updated_at"))
    try:
        output, usage = LLMTracker.call_and_track(
            prompt=REPORT_PROMPT,
            content=json.dumps(
                _report_input(report), ensure_ascii=False, sort_keys=True
            ),
            json_mode=True,
            max_retries=1,
            node_name="chat_report_generation",
        )
        body, sections = _validate_output(output)
    except Exception as error:
        report.status = (
            Report.Status.PARTIAL if report.body else Report.Status.FAILED
        )
        report.processing = {
            **(report.processing or {}),
            "generator": "llm_failed",
            "error": str(error)[:2000],
        }
        report.save(update_fields=("status", "processing", "updated_at"))
        return {"report_id": report.pk, "status": report.status}

    report.body = body
    report.content = {
        **(report.content or {}),
        "llm_section_count": len(sections),
        "llm_model": usage.get("model") if isinstance(usage, dict) else None,
    }
    report.status = Report.Status.READY
    report.generated_at = timezone.now()
    report.processing = {
        **(report.processing or {}),
        "generator": "llm",
        "version": "report.llm.v1",
        "model": usage.get("model") if isinstance(usage, dict) else None,
    }
    report.save(
        update_fields=(
            "body",
            "content",
            "status",
            "generated_at",
            "processing",
            "updated_at",
        )
    )
    return {"report_id": report.pk, "status": report.status}


def dispatch_report_generation(report):
    return generate_report_task.delay(report.pk)
