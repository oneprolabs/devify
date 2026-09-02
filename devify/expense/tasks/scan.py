"""Per-user scan task."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from agentcore_task.adapters.django import prevent_duplicate_task
from expense.models import InvoiceScanRun
from expense.services.scanner import execute_scan
from threadline.utils.task_tracer import TaskTracer

logger = logging.getLogger(__name__)


@shared_task
@prevent_duplicate_task(
    "scan_user_invoices",
    lock_param="run_uuid",
    timeout=getattr(settings, "TASK_TIMEOUT_MINUTES", 60) * 60,
)
def scan_user_invoices(
    run_uuid: str, lookback_days=None, email_uuids=None, force=False
) -> dict:
    run = InvoiceScanRun.objects.select_related("user").get(uuid=run_uuid)
    tracer = TaskTracer("INVOICE_SCAN", module="expense")
    task_id = getattr(scan_user_invoices.request, "id", "") or ""
    tracer.set_task_id(task_id)
    tracer.create_task(
        {
            "run_uuid": str(run.uuid),
            "user_id": str(run.user_id),
            "trigger": run.trigger,
            "status": "starting",
        }
    )
    try:
        execute_scan(
            run,
            lookback_days=lookback_days,
            email_uuids=email_uuids,
            force=force,
        )
        tracer.complete_task(
            {
                "run_uuid": str(run.uuid),
                "status": "completed",
                "emails_scanned": run.emails_scanned,
                "candidate_emails": run.candidate_emails,
                "invoices_created": run.invoices_created,
                "credits_consumed": run.credits_consumed,
            }
        )
        return {
            "run_uuid": str(run.uuid),
            "emails_scanned": run.emails_scanned,
            "candidate_emails": run.candidate_emails,
            "invoices_created": run.invoices_created,
            "credits_consumed": run.credits_consumed,
        }
    except Exception as exc:
        logger.exception("Expense scan %s failed", run_uuid)
        tracer.fail_task(
            {
                "run_uuid": str(run.uuid),
                "status": "failed",
                "error": str(exc),
            },
            str(exc),
        )
        raise
