from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import DesktopDevice


class DeviceAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        device_id = validated_token.get("device_id")
        if device_id:
            # A missing row means the device was never registered (older
            # clients) or the row was cleaned up; the token can still be used
            # and the client may re-register it. Only an explicit revocation
            # blocks the token.
            device = DesktopDevice.objects.filter(
                user=user, device_id=device_id
            ).first()
            if (
                device is not None
                and device.status != DesktopDevice.Status.ACTIVE
            ):
                raise AuthenticationFailed(
                    "This device authorization was revoked."
                )
        return user
