from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from spaces.services import SpaceBootstrapService


@receiver(post_save, sender=User)
def create_personal_space(sender, instance, created, **kwargs):
    if created:
        SpaceBootstrapService.ensure_personal_space(instance)
