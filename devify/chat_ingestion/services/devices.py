"""Devices services for upload batches."""

from django.utils import timezone

from accounts.models import DesktopDevice
from accounts.utils import default_device_label


def _resolve_upload_device(request, values):
    """Bind an upload to its desktop device and refresh that device row.

    The access token may already carry a device id. Newer clients also send
    one explicitly together with their platform, which lets an upload register
    the device without a separate round trip. Returns ``(device_id, platform)``
    and uses ``None`` as the device id when the device was revoked.
    """
    auth = request.auth or {}
    device_id = (
        values.get("device_id") or auth.get("device_id") or ""
    ).strip()[:100]
    platform = (values.get("platform") or "").strip()[:40]
    label = (values.get("device_label") or "").strip()[:120]
    if not device_id:
        return "", platform
    device = DesktopDevice.objects.filter(
        user=request.user, device_id=device_id
    ).first()
    if device is not None:
        if device.status == DesktopDevice.Status.REVOKED:
            return None, platform
        device.label = (
            label
            or device.label
            or default_device_label(platform or device.platform)
        )
        device.platform = platform or device.platform
        device.status = DesktopDevice.Status.ACTIVE
        device.revoked_at = None
        device.last_seen_at = timezone.now()
        device.save(
            update_fields=(
                "label",
                "platform",
                "status",
                "revoked_at",
                "last_seen_at",
            )
        )
    else:
        DesktopDevice.objects.create(
            user=request.user,
            device_id=device_id,
            label=label or default_device_label(platform),
            platform=platform,
            status=DesktopDevice.Status.ACTIVE,
            last_seen_at=timezone.now(),
        )
    return device_id, platform
