"""Permanently delete messages whose every upload was withdrawn.

A withdrawn upload only marks a message orphaned: other members may still
hold an origin for it, and the record stays readable for audit. Once the
grace period passes and no upload backs the message, this command removes it
together with its parts, origins, aliases and analysis evidence.

Dry-run by default; pass ``--apply`` to delete.

Run it inside the API container::

    python manage.py purge_orphaned_messages --days 30 --apply
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from chat_domain.models import Message


class Command(BaseCommand):
    help = "Delete orphaned chat messages after the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Only delete messages orphaned longer than N days.",
        )
        parser.add_argument(
            "--space",
            type=int,
            default=0,
            help="Only purge one space. Defaults to every space.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete the rows. Defaults to a dry run.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=max(0, options["days"]))
        messages = Message.objects.filter(
            orphaned_at__isnull=False, orphaned_at__lt=cutoff
        )
        if options["space"]:
            messages = messages.filter(
                conversation__space_id=options["space"]
            )

        total = messages.count()
        self.stdout.write(
            f"orphaned_messages={total} cutoff={cutoff.isoformat()} "
            f"apply={options['apply']}"
        )
        if not options["apply"]:
            self.stdout.write("dry-run: pass --apply to delete.")
            return

        deleted = 0
        for message in messages.iterator():
            # A re-upload clears orphaned_at; re-check under the row's own
            # value so a message that came back is never deleted.
            if message.orphaned_at is None:
                continue
            message.delete()
            deleted += 1
            if deleted % 200 == 0:
                self.stdout.write(f"deleted={deleted}")

        self.stdout.write(self.style.SUCCESS(f"deleted={deleted}"))
