from core.periodic_registry import TASK_REGISTRY


def register_periodic_tasks():
    TASK_REGISTRY.add(
        name="purge-feedback-attachments",
        task="feedback.tasks.purge_feedback_attachments",
        schedule=86400.0,
    )
