"""Celery tasks for LLM-backed report generation."""

import json

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from chat_analysis.models import (
    Report,
    ReportItem,
    ReportItemSource,
    ReportSection,
)
from core.tracking import LLMTracker

MAX_SECTIONS = 20
MAX_ITEMS_PER_SECTION = 50

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


def _text(value, limit):
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _section_key(raw_key, used):
    base = _text(raw_key, 100) or "section"
    key = base
    suffix = 2
    while key in used:
        key = f"{base}-{suffix}"[:100]
        suffix += 1
    used.add(key)
    return key


def _normalize_sections(sections):
    """Keep only well-formed sections so a bad payload cannot wipe a report."""

    normalized = []
    for raw_section in sections:
        if not isinstance(raw_section, dict):
            continue
        title = _text(raw_section.get("title"), 500)
        if not title:
            continue
        raw_items = raw_section.get("items")
        if not isinstance(raw_items, list):
            raw_items = []
        items = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item_title = _text(raw_item.get("title"), 500)
            if not item_title:
                continue
            items.append(
                {
                    "title": item_title,
                    "summary": _text(raw_item.get("summary"), 20000),
                    "label": _text(raw_item.get("label"), 2000),
                    "time_text": _text(raw_item.get("time_text"), 500),
                    "contact_text": _text(raw_item.get("contact_text"), 2000),
                    "followup_text": _text(
                        raw_item.get("followup_text"), 2000
                    ),
                    "followup_kind": _text(raw_item.get("followup_kind"), 40),
                    "display_kind": _text(raw_item.get("display_kind"), 80),
                }
            )
        normalized.append(
            {
                "section_key": _text(raw_section.get("section_key"), 100),
                "title": title,
                "items": items[:MAX_ITEMS_PER_SECTION],
            }
        )
        if len(normalized) >= MAX_SECTIONS:
            break
    return normalized


def _existing_sources(report):
    """Index the rule-based snapshot so generated items keep their evidence."""

    by_title = {}
    by_summary = {}
    for section in report.sections.prefetch_related("items__sources"):
        for item in section.items.all():
            sources = list(item.sources.all())
            if not sources:
                continue
            by_title.setdefault(item.title.strip(), sources)
            if item.summary.strip():
                by_summary.setdefault(item.summary.strip(), sources)
    return by_title, by_summary


def _persist_sections(report, sections):
    """Replace stored sections, carrying the rule snapshot's sources over."""

    if not sections or not any(section["items"] for section in sections):
        return None
    by_title, by_summary = _existing_sources(report)
    report.sections.all().delete()
    used_keys = set()
    section_count = 0
    item_count = 0
    for section_index, section in enumerate(sections):
        stored = ReportSection.objects.create(
            report=report,
            section_key=_section_key(section["section_key"], used_keys),
            title=section["title"],
            position=section_index,
        )
        section_count += 1
        for item_position, item in enumerate(section["items"]):
            stored_item = ReportItem.objects.create(
                section=stored,
                position=item_position,
                title=item["title"],
                summary=item["summary"],
                label=item["label"],
                time_text=item["time_text"],
                contact_text=item["contact_text"],
                followup_text=item["followup_text"],
                followup_kind=item["followup_kind"],
                display_kind=item["display_kind"],
            )
            item_count += 1
            sources = by_title.get(item["title"]) or by_summary.get(
                item["summary"]
            )
            for source in sources or []:
                ReportItemSource.objects.create(
                    item=stored_item,
                    reference_key=source.reference_key,
                    source_kind=source.source_kind,
                    event=source.event,
                    note=source.note,
                    reference_url=source.reference_url,
                    display_text=source.display_text,
                    event_snapshot=source.event_snapshot,
                    note_snapshot=source.note_snapshot,
                )
    return section_count, item_count


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

    model = usage.get("model") if isinstance(usage, dict) else None
    with transaction.atomic():
        persisted = _persist_sections(report, _normalize_sections(sections))
        if persisted:
            section_count, item_count = persisted
        else:
            section_count = report.sections.count()
            item_count = ReportItem.objects.filter(
                section__report=report
            ).count()
        report.body = body
        report.content = {
            **(report.content or {}),
            "section_count": section_count,
            "item_count": item_count,
            "llm_section_count": len(sections),
            "llm_persisted": bool(persisted),
            "llm_model": model,
        }
        report.status = Report.Status.READY
        report.generated_at = timezone.now()
        report.processing = {
            **(report.processing or {}),
            "generator": "llm",
            "version": "report.llm.v1",
            "model": model,
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
