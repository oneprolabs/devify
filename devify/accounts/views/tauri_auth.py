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

from accounts.models import TauriAuthorizationCode, TauriDevice

CLIENT_ID = os.getenv("TAURI_OAUTH_CLIENT_ID", "wechat-devify-tauri")
REDIRECT_URI = os.getenv(
    "TAURI_OAUTH_REDIRECT_URI",
    "http://127.0.0.1:47832/auth/callback",
)


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _valid_client(client_id, redirect_uri):
    return client_id == CLIENT_ID and redirect_uri == REDIRECT_URI


class TauriAuthorizeAPIView(APIView):
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
            return Response({"detail": "Invalid Tauri client."}, status=400)
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
        TauriAuthorizationCode.objects.create(
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
        response = HttpResponse(status=302)
        response["Location"] = location
        return response


class TauriConfigAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "data": {
                    "protocol_version": "oauth2-pkce.v1",
                    "client_id": CLIENT_ID,
                    "authorize_path": "/api/v1/auth/tauri/authorize",
                    "token_path": "/api/v1/auth/tauri/token",
                    "redirect_uri": REDIRECT_URI,
                    "capabilities": ["spaces", "chat_upload", "analysis_status"],
                }
            }
        )


class TauriTokenAPIView(APIView):
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
            TauriAuthorizationCode.objects.select_for_update()
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
        device, _ = TauriDevice.objects.update_or_create(
            user=grant.user,
            device_id=device_id,
            defaults={
                "label": device_label or grant.device_label,
                "platform": platform,
                "status": TauriDevice.Status.ACTIVE,
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


class TauriDeviceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = TauriDevice.objects.filter(user=request.user).order_by(
            "-last_seen_at", "-id"
        )
        return Response(
            {
                "data": [
                    {
                        "device_id": device.device_id,
                        "label": device.label,
                        "platform": device.platform,
                        "status": device.status,
                        "last_seen_at": device.last_seen_at,
                        "created_at": device.created_at,
                        "revoked_at": device.revoked_at,
                    }
                    for device in devices
                ]
            }
        )


class TauriDeviceRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, device_id):
        updated = TauriDevice.objects.filter(
            user=request.user,
            device_id=device_id,
            status=TauriDevice.Status.ACTIVE,
        ).update(
            status=TauriDevice.Status.REVOKED,
            revoked_at=timezone.now(),
        )
        if not updated:
            return Response({"detail": "Device not found."}, status=404)
        return Response(status=204)
