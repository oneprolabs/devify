from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from feedback.models import FeedbackAttachment


@shared_task
def purge_feedback_attachments():
    expired = FeedbackAttachment.objects.filter(
        expired=False,
        feedback__created_at__lt=timezone.now() - timedelta(days=30),
    )
    count = 0
    for attachment in expired.iterator():
        attachment.path.unlink(missing_ok=True)
        attachment.expired = True
        attachment.save(update_fields=["expired"])
        count += 1
    return count
