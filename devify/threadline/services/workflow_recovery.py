"""Claim email work and inspect recovery without consuming queued tasks."""

import ast
import base64
import json
import logging
from uuid import NAMESPACE_URL, uuid5

from agentcore_task.adapters.django import TaskStatus
from agentcore_task.adapters.django.models import TaskExecution
from celery import current_app
from django.db import transaction
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.state_machine import EmailStatus

logger = logging.getLogger(__name__)
WORKFLOW_TASK = "threadline.tasks.email_workflow.process_email_workflow"
MERGE_TASK = "threadline.tasks.email_merge.process_email_merge"
RETRY_TASK = "threadline.tasks.email_workflow.retry_failed_email_workflow"
EMAIL_TASKS = {WORKFLOW_TASK, MERGE_TASK, RETRY_TASK}


def child_workflow_id(parent_id):
    """A redelivered parent must publish the same child invocation."""
    return str(uuid5(NAMESPACE_URL, f"devify:email-workflow:{parent_id}"))


def claim_workflow(email_id, *, force=False, task_id=None):
    if task_id:
        with transaction.atomic():
            email = EmailMessage.objects.select_for_update().get(pk=email_id)
            reserved = TaskExecution.objects.filter(
                task_id=task_id,
                task_name="EMAIL_WORKFLOW",
                # Compare the string ID as JSON on MariaDB.
                metadata__contains={
                    "email_id": str(email_id),
                    "dispatch_reserved": True,
                },
            )
            if reserved.exists():
                owner = (email.metadata or {}).get("processing_progress", {})
                if (
                    email.status != EmailStatus.PROCESSING.value
                    or owner.get("task_id") != task_id
                ):
                    return False
                claimed = reserved.filter(status=TaskStatus.PENDING).update(
                    status=TaskStatus.STARTED, started_at=timezone.now(),
                )
                if claimed:
                    EmailMessage.objects.filter(pk=email.pk).update(
                        updated_at=timezone.now(),
                    )
                return bool(claimed)
    candidates = EmailMessage.objects.filter(pk=email_id)
    if force:
        candidates = candidates.exclude(status=EmailStatus.PROCESSING.value)
    else:
        candidates = candidates.filter(
            status__in=(EmailStatus.FETCHED.value, EmailStatus.FAILED.value)
        )
    return bool(candidates.update(
        status=EmailStatus.PROCESSING.value, updated_at=timezone.now()
    ))


def expire_workflow_reservation(email_id):
    """Retire an abandoned queued request before recovery creates a new one."""
    TaskExecution.objects.filter(
        task_name="EMAIL_WORKFLOW",
        status=TaskStatus.PENDING,
        metadata__contains={
            "email_id": str(email_id),
            "dispatch_reserved": True,
        },
    ).update(
        status=TaskStatus.FAILURE,
        finished_at=timezone.now(),
        error="Queued workflow abandoned; replaced by recovery",
    )


def _email_id(request):
    if request.get("name", request.get("task")) not in EMAIL_TASKS:
        return None
    args = request.get("args") or []
    kwargs = request.get("kwargs") or {}
    if isinstance(args, str):
        args = ast.literal_eval(args)
    if isinstance(kwargs, str):
        kwargs = ast.literal_eval(kwargs)
    value = args[0] if args else kwargs.get("email_id")
    if value is None:
        raise ValueError("Workflow task has no email ID")
    return str(value)


def _broker_email_id(message):
    task = message.get("headers", {}).get("task")
    if task not in EMAIL_TASKS:
        return None
    body = message["body"]
    if message.get("properties", {}).get("body_encoding") == "base64":
        body = base64.b64decode(body)
    args, kwargs, _ = json.loads(body)
    return _email_id({"name": task, "args": args, "kwargs": kwargs})


def workflows_in_flight():
    """Return queued/running email IDs, or None when recovery is unsafe.

    Read Redis lists and unacked deliveries without removing messages. The
    worker snapshot also covers early-acknowledged, reserved and ETA tasks.
    A failed inspection postpones recovery instead of guessing tasks lost.
    """
    try:
        found = set()
        with current_app.connection_for_read() as connection:
            if connection.transport.driver_type != "redis":
                raise ValueError("Recovery inspection requires Redis")
            channel = connection.channel()
            for queue in current_app.amqp.queues:
                for priority in channel.priority_steps:
                    key = channel._q_for_pri(queue, priority)
                    for raw in channel.client.lrange(key, 0, -1):
                        email_id = _broker_email_id(json.loads(raw))
                        if email_id is not None:
                            found.add(email_id)
            for raw in channel.client.hvals(channel.unacked_key):
                message, _, _ = json.loads(raw)
                email_id = _broker_email_id(message)
                if email_id is not None:
                    found.add(email_id)
        inspector = current_app.control.inspect(timeout=3)
        queues = inspector.active_queues()
        route = current_app.amqp.router.route({}, WORKFLOW_TASK)
        queue_name = route["queue"].name
        email_workers = {
            worker for worker, consumed in (queues or {}).items()
            if any(queue["name"] == queue_name for queue in consumed)
        }
        if not email_workers:
            raise ValueError("No email workers answered recovery inspection")
        for method in ("active", "reserved", "scheduled"):
            workers = getattr(inspector, method)()
            if not workers or not email_workers.issubset(workers):
                raise ValueError("Incomplete email worker recovery inspection")
            for requests in workers.values():
                for request in requests:
                    email_id = _email_id(request.get("request", request))
                    if email_id is not None:
                        found.add(email_id)
        return found
    except Exception:
        logger.exception("Cannot inspect workflows; postponing recovery")
        return None
