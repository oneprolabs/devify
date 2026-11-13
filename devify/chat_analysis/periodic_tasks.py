"""
Register chat analysis periodic tasks with the project registry.
"""

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="chat-ingestion-recover-stale-uploads",
        task="chat_ingestion.tasks.recover_stale_uploads_task",
        schedule=crontab(minute="*/5"),
    )
    TASK_REGISTRY.add(
        name="chat-analysis-sweep-stale-tasks",
        task="chat_analysis.tasks.sweep_stale_async_tasks",
        schedule=crontab(minute="*/5"),
    )
    TASK_REGISTRY.add(
        name="chat-analysis-run-due-topic-reports",
        task="chat_analysis.tasks.run_due_topic_reports_task",
        schedule=crontab(minute="*"),
    )
