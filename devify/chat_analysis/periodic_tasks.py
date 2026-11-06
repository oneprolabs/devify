"""
Register chat analysis periodic tasks with the project registry.
"""

from celery.schedules import crontab

from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="chat-analysis-sweep-stale-tasks",
        task="chat_analysis.tasks.sweep_stale_async_tasks",
        schedule=crontab(minute="*/5"),
    )
