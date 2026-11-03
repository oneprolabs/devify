"""Repair event identity and timeline after earlier extraction runs.

Earlier builds derived one Event per chunk from a free-form LLM key, so the
same matter could appear several times, keys changed on every run and events
had no activity window. This command canonicalises keys, merges the resulting
duplicates, derives the entity grouping key and backfills missing windows from
note evidence.

Dry-run by default; pass ``--apply`` to persist.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from chat_analysis.keys import canonical_event_key, entity_from_text
from chat_analysis.models import Event
from chat_analysis.services import merge_events, refresh_event_window
from chat_domain.models import Message
from spaces.models import Space


class Command(BaseCommand):
    help = "Canonicalise, merge and backfill chat events for one space."

    def add_arguments(self, parser):
        parser.add_argument("--space", type=int, required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without it the command only reports.",
        )

    def handle(self, *args, **options):
        space = Space.objects.filter(pk=options["space"]).first()
        if space is None:
            raise CommandError("Space not found.")
        actor = space.owner
        if actor is None:
            raise CommandError("Space has no owner to attribute repairs to.")

        events = list(Event.objects.filter(space=space).order_by("id"))
        groups = defaultdict(list)
        for event in events:
            key = canonical_event_key(event.event_key, title=event.title)
            groups[key or event.event_key].append(event)

        merge_groups = {
            key: rows for key, rows in groups.items() if len(rows) > 1
        }
        duplicate_rows = sum(len(rows) - 1 for rows in merge_groups.values())
        rename_count = sum(
            1
            for key, rows in groups.items()
            if len(rows) == 1 and rows[0].event_key != key
        )

        self.stdout.write(
            f"space={space.pk} events={len(events)} "
            f"merge_groups={len(merge_groups)} "
            f"duplicate_rows={duplicate_rows} rename={rename_count}"
        )
        for key, rows in merge_groups.items():
            self.stdout.write(
                f"  merge -> {key}: "
                + ", ".join(f"#{row.pk} {row.event_key}" for row in rows)
            )

        if not options["apply"]:
            self.stdout.write("dry-run: pass --apply to persist.")
            return

        merged = 0
        for key, rows in merge_groups.items():
            target = rows[0]
            for source in rows[1:]:
                merge_events(actor=actor, source=source, target=target)
                merged += 1
            target.event_key = key
            target.entity_key = (
                target.entity_key
                or entity_from_text(target.title, key)
            )
            target.save(
                update_fields=("event_key", "entity_key", "updated_at")
            )

        renamed = 0
        for key, rows in groups.items():
            if len(rows) != 1:
                continue
            event = rows[0]
            event.refresh_from_db()
            changed = []
            if event.event_key != key:
                event.event_key = key
                changed.append("event_key")
            if not event.entity_key:
                event.entity_key = entity_from_text(event.title, key)
                changed.append("entity_key")
            if changed:
                event.save(update_fields=tuple(changed) + ("updated_at",))
                renamed += 1

        backfilled = 0
        for event in Event.objects.filter(space=space).order_by("id"):
            if event.opened_at and event.last_activity_at:
                continue
            messages = list(
                Message.objects.filter(
                    chat_note_evidence__note__event_links__event=event
                ).distinct()
            )
            if not messages:
                continue
            refresh_event_window(event, messages=messages)
            backfilled += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"merged={merged} renamed={renamed} windows={backfilled}"
            )
        )
