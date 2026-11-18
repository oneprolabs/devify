"""Repair duplicate chat events and missing timeline windows in one space."""

import uuid
from collections import defaultdict
from itertools import combinations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chat_analysis.keys import (canonical_event_key, entity_from_text,
                                slugify_key)
from chat_analysis.models import Event, EventEvidence, EventRelation
from chat_analysis.services import (ChatAnalysisConflict,
                                    merge_blocked_by_relation, merge_events,
                                    refresh_event_window)
from chat_domain.models import Message
from spaces.models import Space


def find_duplicate_groups(space, events, keys):
    """Require direct evidence between every pair in a proposed group."""
    candidates = defaultdict(set)
    blocked = set()
    by_key = defaultdict(list)
    by_id = {event.pk: event for event in events}
    for event in events:
        by_key[keys[event.pk]].append(event.pk)

    def add_pair(left, right):
        candidates[left].add(right)
        candidates[right].add(left)

    for event_ids in by_key.values():
        for left, right in combinations(event_ids, 2):
            add_pair(left, right)

    by_message_title = defaultdict(list)
    titles = {
        event.pk: slugify_key(event.title, limit=500) for event in events
    }
    for event_id, message_id in EventEvidence.objects.filter(
        event__space=space
    ).values_list("event_id", "message_id").iterator():
        if titles.get(event_id):
            by_message_title[message_id, titles[event_id]].append(event_id)
    for event_ids in by_message_title.values():
        for left, right in combinations(event_ids, 2):
            add_pair(left, right)

    for relation in EventRelation.objects.filter(space=space):
        pair = (relation.left_event_id, relation.right_event_id)
        if merge_blocked_by_relation(relation):
            blocked.add(pair)
        elif (
            relation.decision == EventRelation.Decision.ACCEPTED
            and relation.relation_kind == EventRelation.RelationKind.SAME
        ):
            add_pair(*pair)

    groups = []
    skipped = []
    visited = set()
    for event in events:
        if event.pk in visited or event.pk not in candidates:
            continue
        pending = [event.pk]
        component = {event.pk}
        while pending:
            neighbors = candidates[pending.pop()] - component
            component.update(neighbors)
            pending.extend(neighbors)
        visited.update(component)
        event_ids = sorted(component)
        if any(
            right not in candidates[left] or (left, right) in blocked
            for left, right in combinations(event_ids, 2)
        ):
            skipped.append(event_ids)
        else:
            groups.append([by_id[event_id] for event_id in event_ids])
    return groups, skipped


class Command(BaseCommand):
    help = "Repair duplicate events and missing timeline dates in one space."

    def add_arguments(self, parser):
        parser.add_argument("--space", type=uuid.UUID, required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes. Without it the command only reports.",
        )

    def handle(self, *args, **options):
        if not options["apply"]:
            self.repair(space_id=options["space"], apply=False)
            return
        try:
            with transaction.atomic():
                self.repair(space_id=options["space"], apply=True)
        except ChatAnalysisConflict as exc:
            raise CommandError(str(exc)) from exc

    def repair(self, *, space_id, apply):
        space = Space.objects.filter(pk=space_id).first()
        if space is None:
            raise CommandError("Space not found.")
        actor = space.owner
        if actor is None:
            raise CommandError("Space has no owner to attribute repairs to.")

        event_query = Event.objects.filter(space=space).order_by("id")
        if apply:
            event_query = event_query.select_for_update()
        events = list(event_query)
        keys = {
            event.pk: canonical_event_key(event.event_key, title=event.title)
            or event.event_key
            for event in events
        }
        groups, skipped = find_duplicate_groups(space, events, keys)
        removed_ids = {source.pk for rows in groups for source in rows[1:]}
        skipped_ids = {
            event_id for event_ids in skipped for event_id in event_ids
        }
        retained = [event for event in events if event.pk not in removed_ids]
        rename_count = sum(
            event.pk not in skipped_ids and event.event_key != keys[event.pk]
            for event in retained
        )
        self.stdout.write(
            f"space={space.pk} events={len(events)} "
            f"merge_groups={len(groups)} duplicate_rows={len(removed_ids)} "
            f"skipped_groups={len(skipped)} rename={rename_count}"
        )
        for rows in groups:
            self.stdout.write(
                f"  keep #{rows[0].pk}: "
                + ", ".join(f"#{row.pk} {row.event_key}" for row in rows[1:])
            )
        for event_ids in skipped:
            self.stdout.write(
                "  review ambiguous or conflicting group: "
                + ", ".join(f"#{event_id}" for event_id in event_ids)
            )

        if not apply:
            self.stdout.write("dry-run: pass --apply to persist.")
            return

        for target, *sources in groups:
            for source in sources:
                target = merge_events(
                    actor=actor, source=source, target=target,
                )

        renamed = 0
        for event in retained:
            if event.pk in skipped_ids:
                continue
            key = keys[event.pk]
            changed = []
            if event.event_key != key:
                event.event_key = key
                changed.append("event_key")
            if not event.entity_key:
                entity_key = entity_from_text(event.title, key)
                if entity_key:
                    event.entity_key = entity_key
                    changed.append("entity_key")
            if changed:
                event.save(update_fields=changed + ["updated_at"])
                renamed += 1

        backfilled = 0
        for event in Event.objects.filter(space=space).order_by("id"):
            if event.opened_at and event.last_activity_at:
                continue
            refresh_event_window(event)
            if not (event.opened_at and event.last_activity_at):
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
                f"merged={len(removed_ids)} renamed={renamed} "
                f"windows={backfilled}"
            )
        )
