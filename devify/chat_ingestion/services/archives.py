"""Upload archive storage and integrity validation."""

import hashlib
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from chat_ingestion.models import UploadBatch
from chat_ingestion.services.exceptions import ArchiveMismatch, ArchiveTooLarge
from chat_ingestion.services.state import transition_batch

ARCHIVE_DIR_SETTING = "CHAT_UPLOAD_ARCHIVE_DIR"
MAX_ARCHIVE_BYTES_SETTING = "CHAT_UPLOAD_MAX_ARCHIVE_BYTES"
DEFAULT_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


def archive_root():
    root = getattr(settings, ARCHIVE_DIR_SETTING, "")
    if not root:
        # BASE_DIR points at the core package, so the project root is its
        # parent. Production should set CHAT_UPLOAD_ARCHIVE_DIR to a durable,
        # shared volume so blue/green API containers see the same archives.
        root = Path(settings.BASE_DIR).parent / "chat_upload_archives"
    return Path(root)


def archive_path(batch):
    return archive_root() / f"{batch.uuid}.zip"


def archive_exists(batch):
    return bool(batch.archive_sha256) and archive_path(batch).is_file()


def max_archive_bytes():
    value = getattr(settings, MAX_ARCHIVE_BYTES_SETTING, None)
    if value is None:
        return DEFAULT_MAX_ARCHIVE_BYTES
    return int(value)


def store_archive(batch, uploaded_file):
    """Stream the uploaded archive to disk and record its real hash and size.

    The client hash is never trusted: the checksum is recomputed here. When the
    batch declared a checksum or size at creation time, the stored archive must
    match it, otherwise ``ArchiveMismatch`` is raised and nothing is kept.
    """

    limit = max_archive_bytes()
    # Declared checksums only guard the first upload. Once an archive is
    # stored, ``archive_sha256``/``archive_size`` are the server's own
    # values for that file, so a retry that replaces a rejected archive must
    # not be compared against its predecessor.
    replacing = archive_exists(batch)
    declared_sha256 = "" if replacing else (batch.archive_sha256 or "").lower()
    declared_size = None if replacing else batch.archive_size

    root = archive_root()
    root.mkdir(parents=True, exist_ok=True)
    target = archive_path(batch)

    digest = hashlib.sha256()
    size = 0
    descriptor, temp_name = tempfile.mkstemp(
        dir=root, prefix=f".{batch.uuid}.", suffix=".part"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            for chunk in uploaded_file.chunks():
                size += len(chunk)
                if size > limit:
                    raise ArchiveTooLarge(
                        "The archive exceeds the allowed upload size."
                    )
                digest.update(chunk)
                handle.write(chunk)
        if size == 0:
            raise ArchiveMismatch("The archive is empty.")
        sha256 = digest.hexdigest()
        if declared_sha256 and sha256 != declared_sha256:
            raise ArchiveMismatch(
                "The archive checksum does not match the declared value."
            )
        if declared_size is not None and size != declared_size:
            raise ArchiveMismatch(
                "The archive size does not match the declared value."
            )
        os.replace(temp_name, target)
        temp_name = None
    finally:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)

    if batch.status != UploadBatch.Status.UPLOADING:
        transition_batch(
            batch, UploadBatch.Status.UPLOADING, error_message="", save=False
        )
    else:
        batch.error_message = ""
    batch.archive_sha256 = sha256
    batch.archive_size = size
    batch.archive_received_at = timezone.now()
    batch.save(
        update_fields=(
            "status",
            "error_message",
            "archive_sha256",
            "archive_size",
            "archive_received_at",
            "updated_at",
        )
    )
    return batch
