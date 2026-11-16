"""
Helpers for triggering the email merge workflow.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from agentcore_task.adapters.django import TaskStatus
from agentcore_task.adapters.django.models import TaskExecution
from django.db import transaction
from django.utils import timezone

from threadline.models import EmailMessage, EmailStatus
from threadline.services.workflow_recovery import child_workflow_id

logger = logging.getLogger(__name__)


def enqueue_merge_workflow(
    message: EmailMessage,
    *,
    force: bool = False,
    language: str | None = None,
    scene: str | None = None,
    trigger_source: str = "unknown",
) -> EmailMessage:
    """
    Enqueue the merge workflow and surface processing status immediately.

    Mark the target record as PROCESSING before queueing the workflow so the
    detail page reflects that work is already in progress instead of waiting
    for the Celery worker to start.
    """
    from threadline.tasks.email_merge import process_email_merge

    parent_id = str(uuid4())
    workflow_id = child_workflow_id(parent_id)
    with transaction.atomic():
        target_message = EmailMessage.objects.select_for_update().get(
            pk=message.pk
        )
        if target_message.status == EmailStatus.PROCESSING.value:
            return target_message
        TaskExecution.objects.create(
            task_id=workflow_id, task_name="EMAIL_WORKFLOW",
            module="threadline", status=TaskStatus.PENDING,
            created_by_id=target_message.user_id,
            metadata={
                "email_id": str(target_message.pk), "force": force,
                "trigger_source": trigger_source, "dispatch_reserved": True,
            },
        )
        target_message.set_status(EmailStatus.PROCESSING.value)
        target_message.set_processing_progress(0)
        target_message.metadata["processing_progress"]["task_id"] = workflow_id
        target_message.save(update_fields=["metadata", "updated_at"])

    def dispatch():
        try:
            process_email_merge.apply_async(
                args=[str(target_message.id)],
                kwargs={
                    "force": force, "language": language, "scene": scene,
                    "trigger_source": trigger_source,
                },
                task_id=parent_id,
            )
        except Exception as exc:
            with transaction.atomic():
                EmailMessage.objects.select_for_update().get(
                    pk=target_message.pk
                )
                pending = TaskExecution.objects.filter(
                    task_id=workflow_id, status=TaskStatus.PENDING,
                ).update(
                    status=TaskStatus.FAILURE, error=str(exc),
                    finished_at=timezone.now(),
                )
                if pending:
                    EmailMessage.objects.filter(
                        pk=target_message.pk,
                        status=EmailStatus.PROCESSING.value,
                    ).update(
                        status=EmailStatus.FAILED.value,
                        error_message=str(exc), updated_at=timezone.now(),
                    )
            logger.error(
                "Failed to enqueue merge workflow email=%s: %s",
                target_message.pk, exc,
            )
            raise

    transaction.on_commit(dispatch)
    return target_message


def enqueue_merge_workflows(
    messages: list[EmailMessage],
    *,
    force: bool = False,
    language: str | None = None,
    scene: str | None = None,
    trigger_source: str = "unknown",
) -> list[dict]:
    """
    Enqueue merge workflows for multiple messages and collect per-item results.
    """
    results: list[dict] = []

    for message in messages:
        try:
            target_message = enqueue_merge_workflow(
                message,
                force=force,
                language=language,
                scene=scene,
                trigger_source=trigger_source,
            )
            results.append(
                {
                    "requested_email_id": str(message.id),
                    "requested_uuid": str(message.uuid),
                    "email_id": str(target_message.id),
                    "uuid": str(target_message.uuid),
                    "status": "success",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "requested_email_id": str(message.id),
                    "requested_uuid": str(message.uuid),
                    "email_id": str(message.id),
                    "uuid": str(message.uuid),
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return results
