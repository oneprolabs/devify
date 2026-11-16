"""Relay event dispatcher."""

from __future__ import annotations

import logging
from typing import Any, Dict

from django.db import transaction
from django.utils import timezone

from relay.models import RelayDelivery, RelayEvent, RelaySubscription
from relay.services.adapters import RelayAdapterRegistry
from relay.services.delivery_strategy import resolve_delivery_plan
from relay.services.publisher import workflow_result_key
from threadline.models import EmailMessage

logger = logging.getLogger(__name__)


class RelayDispatcher:
    """Dispatch relay events to all enabled subscriptions."""

    @classmethod
    def _delivery_payload(cls, event: RelayEvent) -> Dict[str, Any]:
        return {
            "event_id": str(event.id),
            "email_id": str(event.email_message_id),
            "user_id": str(event.user_id),
            "artifact_snapshot": event.artifact_snapshot or {},
        }

    @classmethod
    def _claim_delivery(cls, event, subscription, task_id):
        key = workflow_result_key(event.artifact_snapshot)
        idempotency_key = (
            f"workflow:{event.email_message_id}:{key}:{subscription.id}"
        )
        with transaction.atomic():
            EmailMessage.objects.select_for_update().get(
                pk=event.email_message_id
            )
            # Recognize historical deliveries that still use event IDs.
            previous = RelayDelivery.objects.filter(
                subscription=subscription,
                event__email_message_id=event.email_message_id,
                event__event_type=event.event_type,
            ).select_related("event").order_by("created_at")
            matching = [
                item for item in previous
                if workflow_result_key(item.event.artifact_snapshot) == key
            ]
            delivery = next((
                item for item in matching
                if item.status in {
                    RelayDelivery.Status.SUCCESS,
                    RelayDelivery.Status.PROCESSING,
                    RelayDelivery.Status.PENDING,
                    RelayDelivery.Status.SKIPPED,
                }
            ), matching[0] if matching else None)
            created = delivery is None
            if created:
                delivery = RelayDelivery.objects.create(
                    idempotency_key=idempotency_key,
                    event=event, subscription=subscription,
                    target_type=subscription.target_type,
                    status=RelayDelivery.Status.PENDING,
                    agentcore_task_id=task_id,
                )
            elif delivery.status in {
                RelayDelivery.Status.SUCCESS,
                RelayDelivery.Status.PROCESSING,
                RelayDelivery.Status.PENDING,
                RelayDelivery.Status.SKIPPED,
            }:
                return delivery, False, False
            else:
                # Claim failed retries inside the same lock as creation.
                delivery.status = RelayDelivery.Status.PENDING
                delivery.error_message = ""
                if task_id and not delivery.agentcore_task_id:
                    delivery.agentcore_task_id = task_id
                delivery.save(update_fields=[
                    "status", "error_message", "agentcore_task_id",
                    "updated_at",
                ])
            return delivery, created, True

    @classmethod
    def dispatch_event(
        cls,
        event: RelayEvent,
        *,
        task_id: str | None = None,
    ) -> Dict[str, Any]:
        subscriptions = (
            RelaySubscription.objects.filter(user=event.user, enabled=True)
            .order_by("created_at")
        )
        summary = {"created": 0, "success": 0, "failed": 0, "skipped": 0}
        delivery_ids = set()

        for subscription in subscriptions:
            delivery, created, claimed = cls._claim_delivery(
                event, subscription, task_id
            )
            delivery_ids.add(delivery.pk)
            if created:
                summary["created"] += 1
            if not claimed:
                summary["skipped"] += 1
                continue

            try:
                cls._dispatch_one(
                    event=event,
                    subscription=subscription,
                    delivery=delivery,
                    task_id=task_id,
                )
                summary["success"] += 1
            except Exception as exc:
                summary["failed"] += 1
                logger.exception(
                    "Relay delivery failed event=%s subscription=%s",
                    event.id,
                    subscription.id,
                )
                delivery.status = RelayDelivery.Status.FAILED
                delivery.error_message = str(exc)
                delivery.metadata = {
                    **(delivery.metadata or {}),
                    "error": str(exc),
                }
                delivery.save(
                    update_fields=[
                        "status",
                        "error_message",
                        "metadata",
                        "updated_at",
                    ]
                )

        with transaction.atomic():
            EmailMessage.objects.select_for_update().get(
                pk=event.email_message_id
            )
            statuses = set(RelayDelivery.objects.filter(
                pk__in=delivery_ids
            ).values_list("status", flat=True))
            if RelayDelivery.Status.FAILED in statuses:
                event.status = RelayEvent.Status.FAILED
            elif statuses & {
                RelayDelivery.Status.PENDING, RelayDelivery.Status.PROCESSING
            }:
                event.status = RelayEvent.Status.PROCESSING
            else:
                event.status = RelayEvent.Status.COMPLETED
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "processed_at"])
        return summary

    @classmethod
    def retry_delivery(
        cls,
        delivery: RelayDelivery,
        *,
        task_id: str | None = None,
    ) -> Dict[str, Any]:
        delivery = (
            RelayDelivery.objects.select_related(
                "event",
                "event__user",
                "event__email_message",
                "subscription",
            )
            .get(id=delivery.id)
        )

        delivery.status = RelayDelivery.Status.PENDING
        delivery.error_message = ""
        delivery.metadata = {
            **(delivery.metadata or {}),
            "relay_retry_requested": True,
        }
        if task_id:
            delivery.agentcore_task_id = task_id
        delivery.save(
            update_fields=[
                "status",
                "error_message",
                "metadata",
                "agentcore_task_id",
                "updated_at",
            ]
        )

        _dispatch_failed = False
        try:
            cls._dispatch_one(
                event=delivery.event,
                subscription=delivery.subscription,
                delivery=delivery,
                task_id=task_id,
            )
        except Exception:
            _dispatch_failed = True
            raise
        finally:
            if _dispatch_failed:
                delivery.event.status = RelayEvent.Status.FAILED
            else:
                failed_count = RelayDelivery.objects.filter(
                    event=delivery.event,
                    status=RelayDelivery.Status.FAILED,
                ).count()
                delivery.event.status = (
                    RelayEvent.Status.FAILED if failed_count
                    else RelayEvent.Status.COMPLETED
                )
            delivery.event.processed_at = timezone.now()
            delivery.event.save(update_fields=["status", "processed_at"])
        return {"created": 0, "success": 1, "failed": 0, "skipped": 0}

    @classmethod
    def _dispatch_one(
        cls,
        *,
        event,
        subscription,
        delivery,
        task_id: str | None = None,
    ) -> None:
        adapter = RelayAdapterRegistry.get_adapter(subscription.target_type)
        plan = resolve_delivery_plan(subscription, event, delivery)
        delivery.metadata = {
            **(delivery.metadata or {}),
            "relay_delivery_plan": plan,
        }
        if (
            plan.get("action") == "update"
            and plan.get("reference_external_id")
            and not delivery.external_id
        ):
            delivery.external_id = plan["reference_external_id"]
        delivery.status = RelayDelivery.Status.PROCESSING
        if task_id and not delivery.agentcore_task_id:
            delivery.agentcore_task_id = task_id
        delivery.save(
            update_fields=[
                "status",
                "external_id",
                "metadata",
                "agentcore_task_id",
                "updated_at",
            ]
        )

        result = adapter.deliver(
            event=event,
            subscription=subscription,
            delivery=delivery,
        )
        delivery.status = RelayDelivery.Status.SUCCESS
        delivery.external_id = result.external_id
        delivery.external_url = result.external_url
        delivery.metadata = {
            **(delivery.metadata or {}),
            **(result.metadata or {}),
        }
        delivery.save(
            update_fields=[
                "status",
                "external_id",
                "external_url",
                "metadata",
                "agentcore_task_id",
                "updated_at",
            ]
        )
