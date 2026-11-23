"""Recover viewer identities from already completed imports."""

from zipfile import BadZipFile

from django.core.management.base import BaseCommand

from chat_domain.models import Conversation, ConversationIdentity
from chat_domain.services import build_identity_key
from chat_ingestion.models import UploadBatch
from chat_ingestion.package import (
    CONVERSATIONS_MEMBER,
    ChatPackage,
    PackageError,
)
from chat_ingestion.services import archive_path


def _archive_identities(batch):
    item = batch.items.filter(path=CONVERSATIONS_MEMBER).first()
    if not item or not item.sha256:
        raise PackageError("Missing the imported conversation listing digest.")

    identities = {}
    with ChatPackage(archive_path(batch)) as package:
        if package.manifest.platform != batch.source_type:
            raise PackageError("The archive platform does not match.")
        digest, _ = package.digest(CONVERSATIONS_MEMBER)
        if digest != item.sha256:
            raise PackageError("The conversation listing digest changed.")
        for _, record in package.iter_jsonl(CONVERSATIONS_MEMBER):
            sender = str(record.get("self_sender_key") or "").strip()
            source_id = str(record.get("conversation_id") or "").strip()
            scope = str(record.get("scope_key") or "").strip()
            if not sender or len(sender) > 255 or not (source_id or scope):
                continue
            key = build_identity_key(
                platform=batch.source_type,
                source_conversation_id=source_id,
                scope_key=scope,
            )
            identities[key] = sender
    return identities


class Command(BaseCommand):
    help = "Restore viewer identities from completed chat backups."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--space-id", type=int)
        parser.add_argument("--conversation-id", type=int)

    def handle(self, *, apply, space_id, conversation_id, **options):
        batches = UploadBatch.objects.filter(
            status=UploadBatch.Status.COMPLETED,
        ).order_by("pk")
        if space_id is not None:
            batches = batches.filter(space_id=space_id)
        if conversation_id is not None:
            batches = batches.filter(
                items__chat_message_origins__message__conversation_id=(
                    conversation_id
                ),
            ).distinct()

        seen = set()
        scanned = skipped = added = 0
        for batch in batches.iterator(chunk_size=100):
            try:
                keys = _archive_identities(batch)
            except (OSError, BadZipFile, RuntimeError, ValueError):
                skipped += 1
                self.stderr.write(f"Skipped unavailable archive {batch.pk}.")
                continue
            scanned += 1
            conversations = Conversation.objects.filter(
                space_id=batch.space_id,
                platform=batch.source_type,
                identity_key__in=keys,
            )
            if conversation_id is not None:
                conversations = conversations.filter(pk=conversation_id)
            for pk, key in conversations.values_list("pk", "identity_key"):
                sender = keys.get(key)
                identity = (pk, batch.uploaded_by_id, sender)
                if not sender or identity in seen:
                    continue
                seen.add(identity)
                lookup = {
                    "conversation_id": pk,
                    "user_id": batch.uploaded_by_id,
                    "sender_key": sender,
                }
                if apply:
                    _, created = ConversationIdentity.objects.get_or_create(
                        **lookup
                    )
                    added += created
                else:
                    added += not ConversationIdentity.objects.filter(
                        **lookup
                    ).exists()
        self.stdout.write(
            f"scanned={scanned} skipped={skipped} "
            f"{'created' if apply else 'would_create'}={added}"
        )
