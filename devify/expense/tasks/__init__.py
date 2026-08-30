"""Expense Celery tasks."""

from expense.tasks.scheduler import schedule_invoice_scan  # noqa: F401
