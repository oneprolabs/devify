"""Backfill portable fingerprints and merge cross-account message duplicates.

Messages uploaded by two accounts keep two rows until a fingerprint proves
they are the same message. This command computes the missing fingerprints and
then folds each conversation's duplicates into one row, moving origins, parts
and analysis evidence to the survivor.

Fingerprints are only computed for messages that have a timestamp; an
undated message is left alone rather than guessed.

Dry-run by default; pass ``--apply`` to write.

Run it inside the API container::

    python manage.py merge_chat_messages --space 46 --apply
"""

from django.core.management.base import BaseCommand

from chat_domain.models import Conversation, Message
from chat_domain.services import (
    apply_message_fingerprints,
    consolidate_conversation_messages,
)


class Command(BaseCommand):
    help = "Merge messages that two accounts uploaded under different ids."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space",
            type=int,
            default=0,
            help="Only process one space. Defaults to every space.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write fingerprints and merge duplicates. Defaults to a run.",
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Messages fingerprinted per query batch.",
        )

    def handle(self, *args, **options):
        messages = Message.objects.filter(content_fingerprint="")
        conversations = Conversation.objects.all()
        if options["space"]:
            messages = messages.filter(
                conversation__space_id=options["space"]
            )
            conversations = conversations.filter(space_id=options["space"])

        pending = messages.count()
        self.stdout.write(
            f"messages_without_fingerprint={pending} "
            f"conversations={conversations.count()} "
            f"apply={options['apply']}"
        )
        if not options["apply"]:
            self.stdout.write("dry-run: pass --apply to backfill and merge.")
            return

        processed = 0
        batch = max(1, options["batch"])
        message_ids = list(messages.values_list("pk", flat=True))
        for start in range(0, len(message_ids), batch):
            end = start + batch
            processed += apply_message_fingerprints(message_ids[start:end])
            if processed and processed % (batch * 10) == 0:
                self.stdout.write(f"fingerprinted={processed}")

        merged = 0
        for conversation in conversations.iterator():
            merged += len(consolidate_conversation_messages(conversation))

        self.stdout.write(
            self.style.SUCCESS(
                f"fingerprinted={processed} merged={merged}"
            )
        )
