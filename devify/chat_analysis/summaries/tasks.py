"""Generate standalone conversation snapshots through the configured LLM."""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from billing.entitlements import can_use_chat_summary
from chat_analysis.models import ChatSummary
from chat_analysis.summaries.input import summary_content
from chat_analysis.summaries.prompts import cloud_prompt
from chat_analysis.token_budget import request_budget
from core.tracking import LLMTracker
from spaces.services import SpacePermissionService

logger = logging.getLogger("chat_analysis.summary_tasks")


# Preserve the wire name for queued messages and mixed-version workers.
@shared_task(
    name="chat_analysis.summary_tasks.generate_chat_summary",
    bind=True,
    max_retries=0,
    soft_time_limit=270,
    time_limit=300,
)
def generate_chat_summary(self, summary_id, token):
    scope = ChatSummary.objects.filter(pk=summary_id, dispatch_token=token)
    if not scope.filter(status="queued").update(
        status="running", updated_at=timezone.now()
    ):
        return {"summary_id": summary_id, "claimed": False}
    record = scope.select_related("space", "created_by").get()
    try:
        if not can_use_chat_summary(
            record.created_by
        ) or not SpacePermissionService.can_upload(
            record.created_by, record.space
        ):
            raise PermissionError("Summary access is no longer available.")
        content = summary_content(record)
        prompt = cloud_prompt(record.prompt_snapshot)
        budget, count = request_budget(
            int(getattr(settings, "CHAT_ANALYSIS_MODEL_INPUT_TOKENS", 12000))
        )
        if count(prompt, content) > budget:
            scope.filter(status="running").update(
                status="failed",
                error="本次内容超过单次总结的处理上限，请缩小时间范围后重新生成。",
                updated_at=timezone.now(),
            )
            return {"summary_id": summary_id, "status": "failed"}
        output, usage = LLMTracker.call_and_track(
            prompt=prompt,
            content=content,
            json_mode=False,
            node_name="chat_conversation_summary",
            **(
                {"model_uuid": settings.CHAT_ANALYSIS_MODEL_UUID}
                if settings.CHAT_ANALYSIS_MODEL_UUID
                else {}
            ),
        )
        if not isinstance(output, str) or not output.strip():
            raise ValueError("Model returned an empty summary.")
        output = output.strip()
        if len(output) > 20000:
            raise ValueError("Model returned an oversized summary.")
        updated = scope.filter(status="running").update(
            status="ready",
            body=output,
            input_messages=[],
            model=str((usage or {}).get("model", ""))[:160],
            error="",
            updated_at=timezone.now(),
        )
        return {
            "summary_id": summary_id,
            "status": "ready",
            "persisted": bool(updated),
        }
    except Exception:
        logger.exception("Chat summary %s failed", summary_id)
        scope.filter(status="running").update(
            status="failed",
            error="总结生成失败，请重试。",
            updated_at=timezone.now(),
        )
        return {"summary_id": summary_id, "status": "failed"}
