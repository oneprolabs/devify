"""Avatar image storage for conversations and message senders.

Avatars arrive inside the chat upload package. The bytes are content
addressed by their SHA-256 so the same picture is stored once, and the
database only keeps the digest plus its media type.
"""

import hashlib
import os
from pathlib import Path

from django.conf import settings

from chat_domain.models import ConversationAvatar, SenderAvatar

AVATAR_DIR_SETTING = "CHAT_AVATAR_DIR"
MAX_AVATAR_BYTES = 512 * 1024


def avatar_root():
    root = getattr(settings, AVATAR_DIR_SETTING, "")
    if not root:
        # BASE_DIR points at the core package, so the project root is its
        # parent. Production should set CHAT_AVATAR_DIR to a durable shared
        # volume so blue/green API containers serve the same pictures.
        root = Path(settings.BASE_DIR).parent / "chat_avatars"
    return Path(root)


def avatar_path(sha256):
    return avatar_root() / str(sha256)


def detect_content_type(data):
    """Return the image media type from magic bytes, or an empty string."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def store_avatar(data, content_type):
    """Persist one image and return ``(sha256, byte_size)``."""
    digest = hashlib.sha256(data).hexdigest()
    root = avatar_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / digest
    if not target.is_file():
        temporary = root / f".{digest}.{os.getpid()}.tmp"
        temporary.write_bytes(data)
        temporary.replace(target)
    return digest, len(data)


def save_conversation_avatar(conversation, data):
    content_type = detect_content_type(data)
    if not content_type:
        raise ValueError("Unsupported avatar image.")
    sha256, byte_size = store_avatar(data, content_type)
    avatar, _ = ConversationAvatar.objects.update_or_create(
        conversation=conversation,
        defaults={
            "sha256": sha256,
            "content_type": content_type,
            "byte_size": byte_size,
        },
    )
    return avatar


def save_sender_avatar(space, sender_key, data):
    content_type = detect_content_type(data)
    if not content_type:
        raise ValueError("Unsupported avatar image.")
    sha256, byte_size = store_avatar(data, content_type)
    avatar, _ = SenderAvatar.objects.update_or_create(
        space=space,
        sender_key=sender_key,
        defaults={
            "sha256": sha256,
            "content_type": content_type,
            "byte_size": byte_size,
        },
    )
    return avatar
