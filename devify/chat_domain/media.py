"""Content-addressed storage for chat media.

Media arrives inside the upload archive, which is per uploader: the same
picture sent by two people is packed twice. Keeping the only copy inside one
batch also means deleting that batch breaks every other batch that points at
the same message part.

Files are therefore copied out of the archive once, addressed by their
SHA-256, and shared by digest. The database keeps the digest on the part; the
archive stays as the audit copy of the upload.
"""

import os
from pathlib import Path

from django.conf import settings

MEDIA_DIR_SETTING = "CHAT_MEDIA_DIR"


def media_root():
    root = getattr(settings, MEDIA_DIR_SETTING, "")
    if not root:
        # BASE_DIR points at the core package, so the project root is its
        # parent. Production should set CHAT_MEDIA_DIR to a durable, shared
        # volume so every API container serves the same files.
        root = Path(settings.BASE_DIR).parent / "chat_media"
    return Path(root)


def media_path(sha256):
    sha256 = str(sha256 or "")
    if len(sha256) != 64:
        raise ValueError("A media digest must be a SHA-256 hex string.")
    # Two levels keep the directory small when a space holds many files.
    return media_root() / sha256[:2] / sha256


def media_exists(sha256):
    if not sha256 or len(sha256) != 64:
        return False
    return media_path(sha256).is_file()


def store_media(package, member, sha256):
    """Copy one archive member into content-addressed storage.

    ``sha256`` comes from the member digest that was taken while the package
    was validated; the copy re-hashes and refuses to replace a different file.
    The write is atomic, so a crashed import never leaves a truncated file
    behind a valid digest.
    """

    if not sha256 or len(sha256) != 64:
        raise ValueError("A media digest must be a SHA-256 hex string.")
    target = media_path(sha256)
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{sha256}.{os.getpid()}.tmp"
    try:
        package.extract_to(member, temporary, expected_sha256=sha256)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return target
