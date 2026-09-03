"""
The numbers the app centre draws on the Todos card.
"""

from django.utils import timezone

from .models import EmailTodo


def todo_stats(user) -> dict:
    """Open items, how many are already late, and the completion rate."""
    todos = EmailTodo.objects.filter(user=user)
    total = todos.count()
    completed = todos.filter(is_completed=True).count()
    open_todos = todos.filter(is_completed=False)

    return {
        "incomplete": total - completed,
        "overdue": open_todos.filter(
            deadline__isnull=False, deadline__lt=timezone.now()
        ).count(),
        "completion_rate": round(completed / total * 100) if total else 0,
    }
