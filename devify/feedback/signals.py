from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from feedback.models import FeedbackAttachment


@receiver(post_delete, sender=FeedbackAttachment)
def delete_attachment_file(sender, instance, **kwargs):
    path = instance.path
    transaction.on_commit(lambda: path.unlink(missing_ok=True))
