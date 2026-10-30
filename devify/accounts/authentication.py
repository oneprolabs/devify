from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import DesktopDevice


class DeviceAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        device_id = validated_token.get("device_id")
        if (
            device_id
            and not DesktopDevice.objects.filter(
                user=user,
                device_id=device_id,
                status=DesktopDevice.Status.ACTIVE,
            ).exists()
        ):
            raise AuthenticationFailed(
                "This device authorization was revoked."
            )
        return user
