"""Rebuild automatic Events for one space from existing Notes.

Earlier builds created one Event per chunk from a free-form LLM key, so the
same matter could appear several times and events had no message-level
evidence. Re-running the full analysis would also rewrite Notes, which is
unnecessary: the Notes are fine, only their event extraction was poor.

This command drops the space's automatic Events, Suggestions, Relations and
Tags, then re-runs only event extraction for every automatic Note. Report
sources keep their frozen snapshots but lose the live event link.

Dry-run by default; pass ``--apply`` to persist.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chat_analysis.execution import (
    _extract_events,
    _message_payload,
    _output_language,
)
from chat_analysis.models import (
    Event,
    EventEvidence,
    EventRelation,
    EventSuggestion,
    EventTag,
    EventTagAssignment,
    Note,
    ReportItemSource,
)
from spaces.models import Space

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild automatic chat events from existing notes for one space."

    def add_arguments(self, parser):
        parser.add_argument("--space", type=int, required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without it the command only reports.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Re-extract at most this many notes (0 means no limit).",
        )

    def handle(self, *args, **options):
        space = Space.objects.filter(pk=options["space"]).first()
        if space is None:
            raise CommandError("Space not found.")
        notes = list(
            Note.objects.filter(space=space, origin=Note.Origin.AUTO)
            .select_related("analysis_job")
            .order_by("id")
        )
        event_count = Event.objects.filter(space=space).count()
        self.stdout.write(
            f"space={space.pk} events={event_count} notes={len(notes)}"
        )
        if not options["apply"]:
            self.stdout.write("dry-run: pass --apply to persist.")
            return

        with transaction.atomic():
            ReportItemSource.objects.filter(event__space=space).update(
                event=None
            )
            EventSuggestion.objects.filter(space=space).delete()
            EventRelation.objects.filter(space=space).delete()
            EventEvidence.objects.filter(event__space=space).delete()
            EventTagAssignment.objects.filter(event__space=space).delete()
            EventTag.objects.filter(space=space).delete()
            Event.objects.filter(space=space).delete()

        language = _output_language(space)
        processed = 0
        empty = 0
        failed = 0
        for note in notes:
            if options["limit"] and processed >= options["limit"]:
                break
            if note.analysis_job_id is None:
                continue
            messages = [
                evidence.message
                for evidence in note.evidence.select_related(
                    "message"
                ).order_by("message__ingest_seq")
            ]
            if not messages:
                empty += 1
                continue
            try:
                ok = _extract_events(
                    note.analysis_job,
                    note,
                    messages,
                    _message_payload(messages),
                    language,
                )
            except Exception:
                logger.exception("Event rebuild failed for note %s", note.pk)
                failed += 1
                continue
            if not ok:
                failed += 1
            processed += 1
            self.stdout.write(
                f"note={note.pk} processed={processed} failed={failed}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"rebuilt_notes={processed} empty={empty} failed={failed} "
                f"events={Event.objects.filter(space=space).count()}"
            )
        )
