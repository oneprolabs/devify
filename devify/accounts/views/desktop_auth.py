import base64
import hashlib
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import DesktopAuthorizationCode, DesktopDevice
from accounts.utils import default_device_label

CLIENT_ID = os.getenv("DESKTOP_OAUTH_CLIENT_ID", "desktop-client")
REDIRECT_URI = os.getenv(
    "DESKTOP_OAUTH_REDIRECT_URI",
    "http://127.0.0.1:47832/auth/callback",
)


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _valid_client(client_id, redirect_uri):
    return client_id == CLIENT_ID and redirect_uri == REDIRECT_URI


class DesktopAuthorizeAPIView(APIView):
    """Issue a short-lived, one-time code after the browser session logs in."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        client_id = request.query_params.get("client_id", "")
        redirect_uri = request.query_params.get("redirect_uri", "")
        response_type = request.query_params.get("response_type")
        state = request.query_params.get("state", "")
        code_challenge = request.query_params.get("code_challenge", "")
        device_label = request.query_params.get("device_label", "")[:120]
        if not _valid_client(client_id, redirect_uri):
            return Response({"detail": "Invalid desktop client."}, status=400)
        if response_type != "code" or not state or not code_challenge:
            return Response(
                {"detail": "Authorization code and PKCE are required."},
                status=400,
            )
        if len(state) > 512 or len(code_challenge) > 128:
            return Response(
                {"detail": "Authorization parameters are too long."},
                status=400,
            )

        raw_code = secrets.token_urlsafe(48)
        DesktopAuthorizationCode.objects.create(
            user=request.user,
            code_hash=hashlib.sha256(raw_code.encode("ascii")).hexdigest(),
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            device_label=device_label,
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        location = (
            f"{redirect_uri}?{urlencode({'code': raw_code, 'state': state})}"
        )
        if request.query_params.get("mode") == "browser":
            return Response({"data": {"redirect_url": location}})
        response = HttpResponse(status=302)
        response["Location"] = location
        return response


class DesktopConfigAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "data": {
                    "protocol_version": "oauth2-pkce.v1",
                    "client_id": CLIENT_ID,
                    "authorize_path": "/api/v1/auth/desktop/authorize",
                    "browser_authorize_path": "/auth/desktop/authorize",
                    "token_path": "/api/v1/auth/desktop/token",
                    "redirect_uri": REDIRECT_URI,
                    "capabilities": [
                        "spaces", "chat_upload", "analysis_status"
                    ],
                }
            }
        )


class DesktopTokenAPIView(APIView):
    """Exchange a PKCE authorization code for the normal Devify JWT pair."""

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        if request.data.get("grant_type") != "authorization_code":
            return Response({"detail": "Unsupported grant type."}, status=400)
        client_id = request.data.get("client_id", "")
        redirect_uri = request.data.get("redirect_uri", "")
        code = request.data.get("code", "")
        verifier = request.data.get("code_verifier", "")
        device_id = str(request.data.get("device_id", "")).strip()
        device_label = str(request.data.get("device_label", "")).strip()[:120]
        platform = str(request.data.get("platform", "")).strip()[:40]
        if (
            not _valid_client(client_id, redirect_uri)
            or not code
            or not verifier
        ):
            return Response(
                {"detail": "Invalid authorization request."}, status=400
            )
        code_hash = hashlib.sha256(str(code).encode("ascii")).hexdigest()
        grant = (
            DesktopAuthorizationCode.objects.select_for_update()
            .select_related("user")
            .filter(
                code_hash=code_hash,
                client_id=client_id,
                redirect_uri=redirect_uri,
            )
            .first()
        )
        if not grant or grant.used_at or grant.is_expired:
            return Response(
                {"detail": "Authorization code is invalid or expired."},
                status=400,
            )
        if not secrets.compare_digest(
            _pkce_challenge(str(verifier)), grant.code_challenge
        ):
            return Response(
                {"detail": "PKCE verification failed."}, status=400
            )
        if not grant.user.is_active:
            return Response({"detail": "User is inactive."}, status=400)
        if not device_id:
            device_id = secrets.token_urlsafe(24)
        label = (
            device_label
            or grant.device_label
            or default_device_label(platform)
        )
        device, _ = DesktopDevice.objects.update_or_create(
            user=grant.user,
            device_id=device_id,
            defaults={
                "label": label,
                "platform": platform,
                "status": DesktopDevice.Status.ACTIVE,
                "revoked_at": None,
                "last_seen_at": timezone.now(),
            },
        )
        grant.used_at = timezone.now()
        grant.save(update_fields=("used_at",))
        refresh = RefreshToken.for_user(grant.user)
        refresh["device_id"] = device.device_id
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "token_type": "Bearer",
                "expires_in": int(
                    refresh.access_token.lifetime.total_seconds()
                ),
                "device_label": grant.device_label,
                "device_id": device.device_id,
            }
        )


class DesktopDeviceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _payload(device):
        return {
            "device_id": device.device_id,
            "label": device.label,
            "platform": device.platform,
            "status": device.status,
            "last_seen_at": device.last_seen_at,
            "created_at": device.created_at,
            "revoked_at": device.revoked_at,
        }

    def get(self, request):
        devices = DesktopDevice.objects.filter(user=request.user).order_by(
            "-last_seen_at", "-id"
        )
        return Response(
            {"data": [self._payload(device) for device in devices]}
        )

    @transaction.atomic
    def post(self, request):
        """Register or refresh the device behind an existing login.

        Older clients already hold a valid token without a device claim, so
        this endpoint lets them bind the current machine without forcing a new
        sign-in.
        """
        device_id = str(request.data.get("device_id", "")).strip()[:100]
        label = str(request.data.get("label", "")).strip()[:120]
        platform = str(request.data.get("platform", "")).strip()[:40]
        if device_id:
            device = DesktopDevice.objects.filter(
                user=request.user, device_id=device_id
            ).first()
            if (
                device is not None
                and device.status == DesktopDevice.Status.REVOKED
            ):
                return Response(
                    {"detail": "This device authorization was revoked."},
                    status=403,
                )
        else:
            # Adopt a row created before the client sent a label or platform,
            # so upgrading does not leave a stale "设备 xxxx" entry behind.
            device = (
                DesktopDevice.objects.filter(
                    user=request.user,
                    status=DesktopDevice.Status.ACTIVE,
                    label="",
                    platform="",
                )
                .order_by("-last_seen_at", "-id")
                .first()
            )
            if device is not None:
                device_id = device.device_id
        if device is None:
            if not device_id:
                device_id = secrets.token_urlsafe(24)
            device = DesktopDevice.objects.create(
                user=request.user,
                device_id=device_id,
                label=label or default_device_label(platform),
                platform=platform,
                status=DesktopDevice.Status.ACTIVE,
                last_seen_at=timezone.now(),
            )
        else:
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
        return Response({"data": self._payload(device)}, status=201)


class DesktopDeviceRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id):
        updated = DesktopDevice.objects.filter(
            user=request.user,
            device_id=device_id,
            status=DesktopDevice.Status.ACTIVE,
        ).update(
            status=DesktopDevice.Status.REVOKED,
            revoked_at=timezone.now(),
        )
        if not updated:
            return Response({"detail": "Device not found."}, status=404)
        return Response(status=204)
