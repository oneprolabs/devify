from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.entitlements import build_entitlements
from billing.services.config_service import get_public_billing_status


class BillingStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_public_billing_status())


class EntitlementsAPIView(APIView):
    """What the signed-in account may use, including internal-only features."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_entitlements(request.user))
