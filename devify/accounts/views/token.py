"""
Token-related auth views.

Handles JWT token refresh for the frontend refresh flow.
"""

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import DesktopDevice


@method_decorator(csrf_exempt, name="dispatch")
class CustomTokenRefreshView(TokenRefreshView):
    """
    Refresh a JWT access token using a valid refresh token.

    The frontend stores the refresh token and posts it here when an access
    token expires.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            self._touch_device(request)
        return response

    @staticmethod
    def _touch_device(request):
        """Keep the desktop device row alive when its token is refreshed.

        Older clients can hold a refresh token with a device claim but no
        device row (for example after a cleanup). Re-creating it here means the
        device reappears in 设备与设置 without forcing a new sign-in.
        """
        try:
            refresh = RefreshToken(request.data.get("refresh", ""))
            device_id = refresh.get("device_id")
            user_id = refresh.get("user_id")
        except Exception:
            return
        if not device_id or not user_id:
            return
        device = DesktopDevice.objects.filter(
            user_id=user_id, device_id=device_id
        ).first()
        if device is None:
            DesktopDevice.objects.create(
                user_id=user_id,
                device_id=device_id,
                label="桌面客户端",
                status=DesktopDevice.Status.ACTIVE,
                last_seen_at=timezone.now(),
            )
        elif device.status == DesktopDevice.Status.ACTIVE:
            device.last_seen_at = timezone.now()
            device.save(update_fields=("last_seen_at",))
