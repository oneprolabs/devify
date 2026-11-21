"""Expire abandoned summaries and dispatch generation tasks."""

import hashlib
import json
import logging
from datetime import timedelta

from django.utils import timezone

from chat_analysis.models import ChatSummary

logger = logging.getLogger("chat_analysis.summary_views")


def summary_input_hash(values):
    return hashlib.sha256(
        json.dumps(
            values, sort_keys=True, default=str, ensure_ascii=False
        ).encode()
    ).hexdigest()


def expire_stale_summaries(*, now=None):
    now = now or timezone.now()
    return ChatSummary.objects.filter(
        status__in=["queued", "running"],
        updated_at__lt=now - timedelta(minutes=15),
    ).update(status="failed", error="处理超时，请重试。", updated_at=now)


def dispatch(summary):
    from chat_analysis.summaries.tasks import generate_chat_summary

    try:
        generate_chat_summary.apply_async(
            args=[summary.pk, str(summary.dispatch_token)],
            queue="chat_analysis",
        )
    except Exception:
        logger.exception("Failed to enqueue chat summary %s", summary.pk)
        ChatSummary.objects.filter(
            pk=summary.pk,
            status="queued",
            dispatch_token=summary.dispatch_token,
        ).update(
            status="failed",
            error="总结暂时无法开始，请重试。",
            updated_at=timezone.now(),
        )
