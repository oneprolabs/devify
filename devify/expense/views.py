"""Expense API views."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.services.config_service import get_credit_policy
from billing.services.credits_service import CreditsService
from expense.serializers import (
    ExpenseAppConfigSerializer,
    ExpenseUserConfigSerializer,
)
from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)
from expense.services.scan_scheduler import sync_scan_periodic_task

logger = logging.getLogger(__name__)


def _response(data, message="ok", code=200, status_code=status.HTTP_200_OK):
    return Response(
        {"code": code, "message": message, "data": data}, status=status_code
    )


def _user_config_payload(config) -> dict:
    """
    Serialize the user config together with the billing facts the UI needs.

    The enable card has to state the price before the user flips the switch,
    so the balance and unit price travel with the config rather than forcing
    a second round trip.
    """
    data = ExpenseUserConfigSerializer(config).data
    policy = get_credit_policy()
    data["cost_credits_per_email"] = policy.get(
        "invoice_email_cost_credits", 1
    )
    data["credits_balance"] = CreditsService.get_credits_balance(
        config.user_id
    ).get("available_credits")
    return data


class ExpenseConfigAPIView(APIView):
    """User-facing switch and preferences."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = get_user_config(request.user)
        return _response(_user_config_payload(config))

    def patch(self, request):
        config = get_user_config(request.user)
        payload = dict(request.data or {})
        enabled = payload.pop("enabled", None)

        if payload:
            serializer = ExpenseUserConfigSerializer(
                config, data=payload, partial=True
            )
            serializer.is_valid(raise_exception=True)
            config = serializer.save()

        if enabled is not None:
            config = set_user_enabled(config, bool(enabled))

        return _response(_user_config_payload(config))


class ExpenseAdminConfigAPIView(APIView):
    """Platform-level configuration, including the scan schedule."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        config = get_app_config()
        return _response(ExpenseAppConfigSerializer(config).data)

    def put(self, request):
        config = get_app_config()
        serializer = ExpenseAppConfigSerializer(
            config,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        config = serializer.save()

        # A schedule change must reach Beat immediately; that is the whole
        # point of keeping the cron in the database.
        sync_result = sync_scan_periodic_task(config)
        logger.info("Expense scan schedule synced: %s", sync_result)

        data = ExpenseAppConfigSerializer(config).data
        data["schedule_sync"] = sync_result
        return _response(data)
