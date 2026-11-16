"""Relay event publishing service."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from datetime import timezone as datetime_timezone
from typing import Any, Dict

from dateutil import parser as date_parser
from django.db import transaction
from django.utils import timezone

from relay.models import RelayEvent
from threadline.models import EmailMessage

logger = logging.getLogger(__name__)


def workflow_result_key(snapshot):
    """Identify business content independently of retries and event IDs."""
    content = {
        key: value for key, value in (snapshot or {}).items()
        if key != "trigger_source"
    }
    if isinstance(content.get("todos"), list):
        todos = []
        for todo in content["todos"]:
            if not isinstance(todo, Mapping):
                todos.append(todo)
                continue
            deadline = todo.get("deadline_processed") or todo.get("deadline")
            if deadline:
                try:
                    parsed = date_parser.parse(str(deadline))
                    if timezone.is_naive(parsed):
                        parsed = timezone.make_aware(parsed)
                    deadline = parsed.astimezone(
                        datetime_timezone.utc
                    ).isoformat()
                except (ValueError, TypeError, OverflowError):
                    pass
            todos.append({
                **{key: todo.get(key) or "" for key in (
                    "content", "owner", "priority", "location"
                )},
                "deadline": deadline or None,
                "is_completed": bool(todo.get("is_completed", False)),
            })
        content["todos"] = todos
    payload = json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class RelayEventPublisher:
    """Create relay events and enqueue asynchronous processing."""

    @staticmethod
    def _build_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
        keys = (
            "summary_title",
            "summary_content",
            "summary_data",
            "llm_content",
            "metadata",
            "todos",
            "attachments",
            "language",
            "scene",
            "subject",
            "trigger_source",
        )
        snapshot = {
            key: state.get(key) for key in keys
            if state.get(key) is not None
        }
        attachments = state.get("attachments")
        if attachments:
            snapshot["attachments"] = [
                dict(attachment)
                if isinstance(attachment, Mapping)
                else attachment
                for attachment in attachments
            ]
            snapshot["attachment_count"] = len(attachments)
        snapshot["source_state"] = {
            "email_id": state.get("id"),
            "user_id": state.get("user_id"),
        }
        return snapshot

    @classmethod
    def publish_workflow_completed(
        cls, *, email, state: Dict[str, Any]
    ) -> RelayEvent:
        snapshot = cls._build_snapshot(state)
        # Serialize by the durable business object, including against
        # events created before result-based deduplication was deployed.
        key = workflow_result_key(snapshot)
        with transaction.atomic():
            EmailMessage.objects.select_for_update().get(pk=email.pk)
            previous = RelayEvent.objects.filter(
                email_message=email, user=email.user,
                event_type=RelayEvent.EventType.WORKFLOW_COMPLETED,
            ).order_by("id")
            event = next((
                candidate for candidate in previous
                if workflow_result_key(candidate.artifact_snapshot) == key
            ), None)
            if event is None:
                event = RelayEvent.objects.create(
                    user=email.user,
                    email_message=email,
                    event_type=RelayEvent.EventType.WORKFLOW_COMPLETED,
                    artifact_snapshot=snapshot,
                    status=RelayEvent.Status.PENDING,
                )
            elif event.status in {
                RelayEvent.Status.PROCESSING, RelayEvent.Status.COMPLETED
            }:
                return event

        def _enqueue():
            from relay.tasks import process_relay_event

            try:
                process_relay_event.delay(str(event.id))
                logger.info("Queued relay event %s for delivery", event.id)
            except Exception:
                logger.exception(
                    "Failed to enqueue relay event %s; event remains PENDING",
                    event.id,
                )

        transaction.on_commit(_enqueue)
        return event
