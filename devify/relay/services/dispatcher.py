"""Relay event dispatcher."""

from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import uuid4

from agentcore_task.adapters.django import TaskStatus
from agentcore_task.adapters.django.models import TaskExecution
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
                if task_id:
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
    def enqueue_retry(cls, delivery):
        """Reserve one explicit retry before making it visible to a worker."""
        from relay.tasks import process_relay_delivery

        with transaction.atomic():
            EmailMessage.objects.select_for_update().get(
                pk=delivery.event.email_message_id
            )
            delivery.refresh_from_db()
            if (
                delivery.status
                in {
                    RelayDelivery.Status.PENDING,
                    RelayDelivery.Status.PROCESSING,
                }
                and delivery.agentcore_task_id
            ):
                active = TaskExecution.objects.filter(
                    task_id=delivery.agentcore_task_id,
                    status__in=[TaskStatus.PENDING, TaskStatus.STARTED],
                ).exists()
                if active:
                    return delivery.agentcore_task_id
            request_id = str(uuid4())
            TaskExecution.objects.create(
                task_id=request_id,
                task_name="RELAY_DELIVERY",
                module="relay",
                status=TaskStatus.PENDING,
                created_by_id=delivery.event.user_id,
                metadata={
                    "dispatch_reserved": True,
                    "delivery_id": str(delivery.pk),
                    "event_id": str(delivery.event_id),
                },
            )
            delivery.status = RelayDelivery.Status.PENDING
            delivery.error_message = ""
            delivery.agentcore_task_id = request_id
            delivery.metadata = {
                **(delivery.metadata or {}),
                "relay_retry_requested": True,
            }
            delivery.save(
                update_fields=[
                    "status",
                    "error_message",
                    "agentcore_task_id",
                    "metadata",
                    "updated_at",
                ]
            )
            RelayEvent.objects.filter(pk=delivery.event_id).update(
                status=RelayEvent.Status.PROCESSING,
            )

        def dispatch():
            try:
                process_relay_delivery.apply_async(
                    args=[str(delivery.pk)],
                    task_id=request_id,
                )
            except Exception as exc:
                with transaction.atomic():
                    EmailMessage.objects.select_for_update().get(
                        pk=delivery.event.email_message_id
                    )
                    pending = TaskExecution.objects.filter(
                        task_id=request_id,
                        status=TaskStatus.PENDING,
                    ).update(
                        status=TaskStatus.FAILURE,
                        error=str(exc),
                        finished_at=timezone.now(),
                    )
                    if pending:
                        RelayDelivery.objects.filter(
                            pk=delivery.pk,
                            agentcore_task_id=request_id,
                        ).update(
                            status=RelayDelivery.Status.FAILED,
                            error_message=str(exc),
                            updated_at=timezone.now(),
                        )
                        RelayEvent.objects.filter(pk=delivery.event_id).update(
                            status=RelayEvent.Status.FAILED,
                        )
                raise

        transaction.on_commit(dispatch)
        return request_id

    @classmethod
    def retry_delivery(
        cls,
        delivery: RelayDelivery,
        *,
        task_id: str | None = None,
    ) -> Dict[str, Any]:
        with transaction.atomic():
            EmailMessage.objects.select_for_update().get(
                pk=delivery.event.email_message_id
            )
            delivery = RelayDelivery.objects.select_related(
                "event",
                "event__user",
                "event__email_message",
                "subscription",
            ).get(id=delivery.id)
            previous_id = delivery.agentcore_task_id
            previous_task = (
                TaskExecution.objects.filter(
                    task_id=previous_id,
                ).first()
                if previous_id
                else None
            )
            request = TaskExecution.objects.filter(task_id=task_id).first()
            if (
                request and request.metadata.get("dispatch_reserved")
                and previous_id != task_id
            ):
                return {"created": 0, "success": 0, "failed": 0, "skipped": 1}
            repeated = task_id and (
                delivery.metadata.get("relay_retry_task_id") == task_id
                or (
                    previous_id == task_id
                    and delivery.status == RelayDelivery.Status.SUCCESS
                )
            )
            busy = (
                delivery.status
                in {
                    RelayDelivery.Status.PENDING,
                    RelayDelivery.Status.PROCESSING,
                }
                and previous_task
                and previous_task.status
                in {
                    TaskStatus.PENDING,
                    TaskStatus.STARTED,
                }
                and previous_id != task_id
            )
            if repeated or busy:
                return {"created": 0, "success": 0, "failed": 0, "skipped": 1}
            delivery.status = RelayDelivery.Status.PROCESSING
            delivery.error_message = ""
            delivery.metadata = {
                **(delivery.metadata or {}),
                "relay_retry_requested": True,
                "relay_retry_task_id": task_id,
            }
            if task_id:
                delivery.agentcore_task_id = task_id
                TaskExecution.objects.filter(
                    task_id=task_id, status=TaskStatus.PENDING,
                ).update(status=TaskStatus.STARTED, started_at=timezone.now())
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
                    RelayEvent.Status.FAILED
                    if failed_count
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
