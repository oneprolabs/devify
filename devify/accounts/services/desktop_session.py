"""Manage the server-side lifetime of desktop device credentials."""

import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, Token

from accounts.models import DesktopDevice, DesktopSession

SESSION_CLAIM = "desktop_session_id"
INACTIVITY_LIMIT = timedelta(days=7)


def _digest(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _active_sessions(now):
    return DesktopSession.objects.filter(
        revoked_at__isnull=True,
        last_active_at__gt=now - INACTIVITY_LIMIT,
    )


def _access_token(user, session):
    token = AccessToken.for_user(user)
    token["device_id"] = session.device.device_id
    token[SESSION_CLAIM] = session.session_id
    return str(token)


@transaction.atomic
def create_session(user, device_id):
    device = DesktopDevice.objects.select_for_update().filter(
        user=user, device_id=device_id, status=DesktopDevice.Status.ACTIVE
    ).first()
    if device is None:
        return None

    secret = secrets.token_urlsafe(32)
    session, _ = DesktopSession.objects.update_or_create(
        device=device,
        defaults={
            "session_id": uuid4().hex,
            "secret_hash": _digest(secret),
            "last_active_at": timezone.now(),
            "revoked_at": None,
        },
    )
    return {"session": secret, "access": _access_token(user, session)}


def refresh_session(device_id, secret):
    session = (
        _active_sessions(timezone.now())
        .select_related("device__user")
        .filter(
            device__device_id=device_id,
            device__status=DesktopDevice.Status.ACTIVE,
            device__user__is_active=True,
            secret_hash=_digest(secret),
        )
        .first()
    )
    if session is None:
        return None
    return {"access": _access_token(session.device.user, session)}


@transaction.atomic
def revoke_session(device_id, secret):
    secret_hash = _digest(secret)
    device_pk = (
        DesktopSession.objects.filter(
            device__device_id=device_id, secret_hash=secret_hash
        )
        .values_list("device_id", flat=True)
        .first()
    )
    if device_pk is None:
        return
    # Serialize with both session replacement and device revocation.
    if not DesktopDevice.objects.select_for_update().filter(
        pk=device_pk
    ).exists():
        return
    DesktopSession.objects.filter(
        device_id=device_pk,
        secret_hash=secret_hash,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())


@transaction.atomic
def revoke_device(user, device_id):
    device = DesktopDevice.objects.select_for_update().filter(
        user=user, device_id=device_id, status=DesktopDevice.Status.ACTIVE
    ).first()
    if device is None:
        return False
    now = timezone.now()
    device.status = DesktopDevice.Status.REVOKED
    device.revoked_at = now
    device.save(update_fields=("status", "revoked_at"))
    DesktopSession.objects.filter(
        device=device, revoked_at__isnull=True
    ).update(revoked_at=now)
    return True


def session_is_valid(user, token):
    return _active_sessions(timezone.now()).filter(
        session_id=token.get(SESSION_CLAIM),
        device__user=user,
        device__device_id=token.get("device_id"),
        device__status=DesktopDevice.Status.ACTIVE,
    ).exists()


def record_activity(token):
    """Call after a successfully accepted, user-initiated operation."""
    if not isinstance(token, Token) or SESSION_CLAIM not in token:
        return

    now = timezone.now()
    _active_sessions(now).filter(
        session_id=token.get(SESSION_CLAIM), last_active_at__lt=now
    ).update(last_active_at=now)
