from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from spaces.services import SpaceBootstrapService


class Command(BaseCommand):
    help = "Create a personal space and owner membership for every user."

    def handle(self, *args, **options):
        user_model = get_user_model()
        processed = 0
        for user in user_model.objects.order_by("pk").iterator():
            SpaceBootstrapService.ensure_personal_space(user)
            processed += 1
        message = f"Ensured personal spaces for {processed} users."
        self.stdout.write(self.style.SUCCESS(message))
