"""Read-only inventory for the multi-uploader chat union model.

The planned identity change drops the uploading account from the conversation
key, so conversations that currently live side by side can be merged and their
messages counted once. This command reports how large that change is on the
database it runs against. It never writes.

Run it inside the API container::

    python manage.py audit_chat_union
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch, UploadItem


def _pct(part, whole):
    if not whole:
        return "0.0%"
    return f"{(part / whole) * 100:.1f}%"


class Command(BaseCommand):
    help = "Report merge candidates and media duplication for chat union."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space",
            type=int,
            default=0,
            help="Only inspect one space. Defaults to every space.",
        )
        parser.add_argument(
            "--groups",
            type=int,
            default=200,
            help="Inspect at most this many duplicate-conversation groups.",
        )
        parser.add_argument(
            "--examples",
            type=int,
            default=5,
            help="Print this many example groups.",
        )

    def handle(self, *args, **options):
        space_id = options["space"]
        conversations = Conversation.objects.all()
        messages = Message.objects.all()
        origins = MessageOrigin.objects.all()
        batches = UploadBatch.objects.all()
        items = UploadItem.objects.all()
        if space_id:
            conversations = conversations.filter(space_id=space_id)
            messages = messages.filter(conversation__space_id=space_id)
            origins = origins.filter(
                message__conversation__space_id=space_id
            )
            batches = batches.filter(space_id=space_id)
            items = items.filter(batch__space_id=space_id)

        scope = f"space={space_id}" if space_id else "space=all"
        self.stdout.write(f"# chat union audit {scope}")

        total_conversations = conversations.count()
        total_messages = messages.count()
        total_origins = origins.count()
        self.stdout.write(
            f"conversations={total_conversations} "
            f"messages={total_messages} origins={total_origins} "
            f"batches={batches.count()} upload_items={items.count()}"
        )

        # 1. Conversations that collide once the account is dropped from the
        # identity key. Grouping uses the stored source columns, not the
        # encoded identity key.
        groups = list(
            conversations.exclude(source_conversation_id="")
            .values("space_id", "platform", "source_conversation_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("-n")[: options["groups"]]
        )
        group_conversations = sum(group["n"] for group in groups)
        self.stdout.write(
            f"duplicate_conversation_groups={len(groups)} "
            f"conversations_in_groups={group_conversations}"
        )

        mergeable_messages = 0
        mergeable_origins = 0
        examples = []
        for group in groups:
            siblings = list(
                conversations.filter(
                    space_id=group["space_id"],
                    platform=group["platform"],
                    source_conversation_id=group["source_conversation_id"],
                ).values_list("id", flat=True)
            )
            by_key = defaultdict(set)
            for conversation_id, message_key in messages.filter(
                conversation_id__in=siblings
            ).values_list("conversation_id", "message_key"):
                by_key[message_key].add(conversation_id)
            overlapping = [
                key for key, owners in by_key.items() if len(owners) > 1
            ]
            mergeable_messages += len(overlapping)
            if overlapping:
                mergeable_origins += origins.filter(
                    message__conversation_id__in=siblings,
                    message__message_key__in=overlapping,
                ).count()
            if len(examples) < options["examples"]:
                examples.append(
                    (
                        group["space_id"],
                        group["platform"],
                        group["source_conversation_id"],
                        group["n"],
                        len(by_key),
                        len(overlapping),
                    )
                )

        # Origins follow their message, so they are never lost by a merge;
        # count how many of the shared messages carry more than one upload.
        multi_upload_count = (
            origins.values("message_id")
            .annotate(
                uploaders=Count(
                    "upload_item__batch__uploaded_by", distinct=True
                )
            )
            .filter(uploaders__gt=1)
            .count()
        )

        self.stdout.write(
            f"message_keys_shared_across_conversations={mergeable_messages} "
            f"message_rows_to_collapse={mergeable_messages} "
            f"origins_kept_on_merge={mergeable_origins}"
        )
        self.stdout.write(
            f"messages_with_multiple_uploaders={multi_upload_count}"
        )
        for space, platform, source_id, count, keys, overlap in examples:
            self.stdout.write(
                f"  example space={space} platform={platform} "
                f"conversation={source_id} conversations={count} "
                f"messages={keys} overlapping={overlap}"
            )

        # 2. Message key stability. Only srv keys are portable across
        # accounts; src and loc keys are local to one client.
        srv = messages.filter(message_key__startswith="srv:").count()
        src = messages.filter(message_key__startswith="src:").count()
        loc = messages.filter(message_key__startswith="loc:").count()
        other = total_messages - srv - src - loc
        self.stdout.write(
            f"message_keys srv={srv} ({_pct(srv, total_messages)}) "
            f"src={src} ({_pct(src, total_messages)}) "
            f"loc={loc} ({_pct(loc, total_messages)}) "
            f"other={other}"
        )

        # 3. Uploader spread per space, to size who would be merged.
        spread = (
            batches.values("space_id")
            .annotate(
                uploaders=Count("uploaded_by", distinct=True),
                batches=Count("id"),
            )
            .order_by("-uploaders")[:10]
        )
        for row in spread:
            self.stdout.write(
                f"  space={row['space_id']} uploaders={row['uploaders']} "
                f"batches={row['batches']}"
            )

        # 4. Media storage. Every upload keeps its own archive, so the same
        # picture is stored once per uploader until media is content
        # addressed.
        media = items.filter(path__startswith="media/")
        media_total = media.aggregate(total=Sum("size"))["total"] or 0
        media_rows = media.count()
        unique = media.values("sha256").distinct().count()
        archive_total = (
            batches.aggregate(total=Sum("archive_size"))["total"] or 0
        )
        self.stdout.write(
            f"archives total_bytes={archive_total} "
            f"media_rows={media_rows} media_total_bytes={media_total} "
            f"unique_media_digests={unique}"
        )
        if media_rows:
            self.stdout.write(
                f"media_avg_bytes_per_row={media_total // media_rows} "
                f"media_rows_per_digest={media_rows / unique:.2f}"
            )
