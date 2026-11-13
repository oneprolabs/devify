"""Structure existing automatic Notes and create their event suggestions."""

from django.core.management.base import BaseCommand

from chat_analysis.execution import _enrich_note_with_llm
from chat_analysis.models import Note


class Command(BaseCommand):
    help = (
        "Run LLM note structuring for existing automatic Notes in one space. "
        "Use this to backfill events after CHAT_ANALYSIS_LLM_ENABLED is "
        "turned on."
    )

    def add_arguments(self, parser):
        parser.add_argument("--space", type=int, required=True)
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Re-run notes that already have structured data or "
                "suggestions."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most this many notes (0 means no limit).",
        )

    def handle(self, *args, **options):
        notes = (
            Note.objects.filter(
                space_id=options["space"],
                origin=Note.Origin.AUTO,
            )
            .select_related("analysis_job")
            .order_by("id")
        )
        processed = 0
        skipped = 0
        for note in notes.iterator():
            if options["limit"] and processed >= options["limit"]:
                break
            if note.analysis_job_id is None:
                skipped += 1
                continue
            if not options["force"] and (
                note.structured_data or note.event_suggestions.exists()
            ):
                skipped += 1
                continue
            messages = [
                evidence.message
                for evidence in note.evidence.select_related(
                    "message"
                ).order_by("message__ingest_seq")
            ]
            if not messages:
                skipped += 1
                continue
            _enrich_note_with_llm(note.analysis_job, note, messages)
            processed += 1
        self.stdout.write(
            self.style.SUCCESS(f"enriched={processed} skipped={skipped}")
        )
