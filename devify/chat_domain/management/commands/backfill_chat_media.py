"""Copy media out of existing upload archives into content-addressed storage.

Older imports kept the only copy of every picture and file inside the
uploader's archive, which ties one message part to one batch. This command
walks those parts, extracts the bytes once per digest and records the digest
on the part. It never deletes the archive.

Dry-run by default; pass ``--apply`` to write files and rows.

Run it inside the API container::

    python manage.py backfill_chat_media --space 46 --apply
"""

from django.core.management.base import BaseCommand

from chat_domain.media import media_exists, store_media
from chat_domain.models import MessagePart
from chat_ingestion.package import ChatPackage, PackageError
from chat_ingestion.services import archive_path


class Command(BaseCommand):
    help = "Extract archive media into content-addressed storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--space",
            type=int,
            default=0,
            help="Only backfill one space. Defaults to every space.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write media files and part rows. Defaults to a dry run.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most this many parts (0 means no limit).",
        )

    def handle(self, *args, **options):
        parts = (
            MessagePart.objects.filter(
                upload_item__isnull=False,
                kind__in=(
                    MessagePart.Kind.IMAGE,
                    MessagePart.Kind.VIDEO,
                    MessagePart.Kind.AUDIO,
                    MessagePart.Kind.FILE,
                ),
            )
            .exclude(upload_item__sha256="")
            .select_related("upload_item", "upload_item__batch")
            .order_by("upload_item__batch_id", "id")
        )
        if options["space"]:
            parts = parts.filter(
                message__conversation__space_id=options["space"]
            )
        # Only parts that still have no digest; a part that already carries
        # one is either new or already backfilled.
        parts = parts.filter(media_sha256="")

        limit = options["limit"]
        if limit:
            parts = parts[:limit]

        pending = list(parts)
        self.stdout.write(
            f"parts_without_media={len(pending)} apply={options['apply']}"
        )
        if not options["apply"]:
            digests = {
                part.upload_item.sha256 for part in pending if part.upload_item
            }
            self.stdout.write(
                f"distinct_digests={len(digests)} "
                f"already_stored={sum(1 for d in digests if media_exists(d))}"
            )
            self.stdout.write("dry-run: pass --apply to persist.")
            return

        stored = 0
        missing = 0
        failed = 0
        current_batch = None
        package = None
        try:
            for part in pending:
                item = part.upload_item
                if item is None or item.batch_id != current_batch:
                    if package is not None:
                        package.close()
                        package = None
                    current_batch = item.batch_id if item else None
                    archive = archive_path(item.batch) if item else None
                    if archive is not None and archive.is_file():
                        try:
                            package = ChatPackage(archive)
                        except (PackageError, OSError) as error:
                            self.stderr.write(
                                f"batch={current_batch} unreadable: {error}"
                            )
                            package = None
                if item is None or package is None:
                    missing += 1
                    continue
                if not media_exists(item.sha256):
                    try:
                        store_media(package, item.path, item.sha256)
                    except (PackageError, OSError) as error:
                        self.stderr.write(
                            f"part={part.pk} item={item.pk} failed: {error}"
                        )
                        failed += 1
                        continue
                part.media_sha256 = item.sha256
                part.media_content_type = part.media_content_type or (
                    item.content_type or ""
                )
                part.save(
                    update_fields=(
                        "media_sha256",
                        "media_content_type",
                        "updated_at",
                    )
                )
                stored += 1
                if stored % 200 == 0:
                    self.stdout.write(f"stored={stored} missing={missing}")
        finally:
            if package is not None:
                package.close()

        remaining = (
            MessagePart.objects.filter(
                media_sha256="",
                kind__in=(
                    MessagePart.Kind.IMAGE,
                    MessagePart.Kind.VIDEO,
                    MessagePart.Kind.AUDIO,
                    MessagePart.Kind.FILE,
                ),
                upload_item__isnull=False,
            ).count()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"stored={stored} missing={missing} failed={failed} "
                f"remaining={remaining}"
            )
        )
