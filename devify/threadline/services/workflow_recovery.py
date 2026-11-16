"""Claim email work and inspect recovery without consuming queued tasks."""

import ast
import base64
import json
import logging

from celery import current_app
from django.utils import timezone

from threadline.models import EmailMessage
from threadline.state_machine import EmailStatus

logger = logging.getLogger(__name__)
WORKFLOW_TASK = "threadline.tasks.email_workflow.process_email_workflow"


def claim_workflow(email_id, *, force=False):
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


def _email_id(request):
    if request.get("name", request.get("task")) != WORKFLOW_TASK:
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
    if message.get("headers", {}).get("task") != WORKFLOW_TASK:
        return None
    body = message["body"]
    if message.get("properties", {}).get("body_encoding") == "base64":
        body = base64.b64decode(body)
    args, kwargs, _ = json.loads(body)
    return _email_id({"name": WORKFLOW_TASK, "args": args, "kwargs": kwargs})


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
        for method in ("active", "reserved", "scheduled"):
            workers = getattr(inspector, method)()
            if not workers:
                raise ValueError("No workers answered recovery inspection")
            for requests in workers.values():
                for request in requests:
                    email_id = _email_id(request.get("request", request))
                    if email_id is not None:
                        found.add(email_id)
        return found
    except Exception:
        logger.exception("Cannot inspect workflows; postponing recovery")
        return None
