"""Desktop session credential endpoints."""

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import DeviceAwareJWTAuthentication
from accounts.services.desktop_session import (
    SESSION_CLAIM,
    create_session,
    refresh_session,
    revoke_session,
)


class DesktopSessionCreateInput(serializers.Serializer):
    device_id = serializers.CharField(max_length=100)


class DesktopSessionCredentialInput(DesktopSessionCreateInput):
    session = serializers.CharField(max_length=128, trim_whitespace=False)


class DesktopSessionAPIView(APIView):
    authentication_classes = (DeviceAwareJWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = DesktopSessionCreateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = serializer.validated_data["device_id"]
        token = request.auth
        bound_device = token.get("device_id")
        if SESSION_CLAIM in token or (
            bound_device and bound_device != device_id
        ):
            raise PermissionDenied("This token cannot create this session.")

        payload = create_session(request.user, device_id)
        if payload is None:
            raise PermissionDenied("This device is not authorized.")
        return Response({"data": payload}, status=201)


class DesktopSessionRefreshAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = DesktopSessionCredentialInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = refresh_session(
            serializer.validated_data["device_id"],
            serializer.validated_data["session"],
        )
        if payload is None:
            return Response(
                {"detail": "This desktop session is no longer authorized."},
                status=401,
            )
        return Response({"data": payload})

    def delete(self, request):
        serializer = DesktopSessionCredentialInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoke_session(
            serializer.validated_data["device_id"],
            serializer.validated_data["session"],
        )
        return Response(status=204)
