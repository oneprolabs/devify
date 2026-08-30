"""Expense API views."""

from __future__ import annotations

import logging
import os

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.services.config_service import get_credit_policy
from billing.services.credits_service import CreditsService
from expense.models import Invoice, InvoiceScanRun, InvoiceSourceFile
from expense.serializers import (
    ExpenseAppConfigSerializer,
    ExpenseUserConfigSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    InvoiceScanRunDetailSerializer,
    InvoiceScanRunSerializer,
    InvoiceSourceFileSerializer,
    InvoiceUpdateSerializer,
    ScanRequestSerializer,
)
from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)
from expense.services.scan_scheduler import sync_scan_periodic_task
from expense.services.classification import remember_correction
from expense.services.scanner import preview_scan, start_scan

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


class ExpenseScanPreviewAPIView(APIView):
    """
    Report what a scan would find and cost, without doing it.

    Nothing is written and nothing is charged here, so the UI can put a
    real number in front of the user before they commit to spending.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScanRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        result = preview_scan(
            request.user,
            lookback_days=payload.get("lookback_days"),
            email_uuids=[str(item) for item in payload.get("email_uuids", [])]
            or None,
        )
        return _response(result)


class ExpenseScanAPIView(APIView):
    """Start a scan and hand back the run to poll."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScanRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        email_uuids = [str(item) for item in payload.get("email_uuids", [])]
        trigger = (
            InvoiceScanRun.Trigger.BACKFILL
            if payload.get("lookback_days") or email_uuids
            else InvoiceScanRun.Trigger.MANUAL
        )

        run = start_scan(
            request.user,
            trigger=trigger,
            lookback_days=payload.get("lookback_days"),
            email_uuids=email_uuids or None,
        )
        return _response(
            InvoiceScanRunSerializer(run).data,
            message=_("scan started"),
            code=202,
            status_code=status.HTTP_202_ACCEPTED,
        )


class ExpenseScanRunListAPIView(APIView):
    """Scan history for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = InvoiceScanRun.objects.filter(user=request.user)[:50]
        return _response(InvoiceScanRunSerializer(queryset, many=True).data)


class ExpenseScanRunDetailAPIView(APIView):
    """One scan batch including its per-email verdicts."""

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        run = get_object_or_404(InvoiceScanRun, uuid=uuid, user=request.user)
        return _response(InvoiceScanRunDetailSerializer(run).data)


class ExpenseLinkListAPIView(APIView):
    """Links found in email bodies, and what became of each."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = InvoiceSourceFile.objects.filter(user=request.user)
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(fetch_status=status_filter)
        return _response(
            InvoiceSourceFileSerializer(queryset[:100], many=True).data
        )


class ExpenseLinkAllowAPIView(APIView):
    """
    Release one blocked link.

    The override is deliberately scoped to this single URL rather than
    adding its domain to the allowlist, so trusting one invoice email does
    not quietly widen what the server will fetch in future.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        record = get_object_or_404(
            InvoiceSourceFile, uuid=uuid, user=request.user
        )
        record.user_allowed = True
        record.save(update_fields=["user_allowed"])

        run = start_scan(
            request.user,
            trigger=InvoiceScanRun.Trigger.MANUAL,
            email_uuids=[str(record.email_message.uuid)],
        )
        return _response(
            {
                "link": InvoiceSourceFileSerializer(record).data,
                "run_uuid": str(run.uuid),
            },
            message=_("link released"),
            code=202,
            status_code=status.HTTP_202_ACCEPTED,
        )


class ExpenseInvoiceListAPIView(APIView):
    """The invoice table, with the filters the list view offers."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Invoice.objects.filter(user=request.user)
        params = request.query_params

        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        else:
            # Failed reads and non-invoices are noise in the default view;
            # they stay reachable through an explicit status filter.
            queryset = queryset.filter(
                status__in=[
                    Invoice.Status.EXTRACTED,
                    Invoice.Status.DUPLICATE,
                ]
            )

        if params.get("category"):
            queryset = queryset.filter(category=params["category"])
        if params.get("city"):
            queryset = queryset.filter(city__icontains=params["city"])
        if params.get("start"):
            queryset = queryset.filter(issue_date__gte=params["start"])
        if params.get("end"):
            queryset = queryset.filter(issue_date__lte=params["end"])
        if params.get("needs_review") == "true":
            queryset = queryset.filter(needs_review=True)
        if params.get("q"):
            term = params["q"]
            queryset = queryset.filter(
                Q(seller_name__icontains=term)
                | Q(invoice_no__icontains=term)
                | Q(buyer_name__icontains=term)
            )

        queryset = queryset.select_related("email_message")[:200]
        return _response(InvoiceListSerializer(queryset, many=True).data)


class ExpenseInvoiceDetailAPIView(APIView):
    """Read, correct or discard one invoice."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, request, uuid):
        return get_object_or_404(Invoice, uuid=uuid, user=request.user)

    def get(self, request, uuid):
        invoice = self._get_object(request, uuid)
        return _response(InvoiceDetailSerializer(invoice).data)

    def patch(self, request, uuid):
        invoice = self._get_object(request, uuid)
        previous_category = invoice.category

        serializer = InvoiceUpdateSerializer(
            invoice, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()

        if "category" in serializer.validated_data:
            new_category = serializer.validated_data["category"]
            if new_category and new_category != previous_category:
                # A correction is worth remembering, so the next invoice
                # from this supplier lands in the right place unaided.
                remember_correction(request.user, invoice, new_category)
                invoice.category_source = Invoice.CategorySource.USER
                invoice.save(update_fields=["category_source", "updated_at"])

        return _response(InvoiceDetailSerializer(invoice).data)

    def delete(self, request, uuid):
        invoice = self._get_object(request, uuid)
        invoice.delete()
        return _response(None, message=_("deleted"))


class ExpenseInvoiceReextractAPIView(APIView):
    """Read one email's invoices again, charging for the rerun."""

    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        invoice = get_object_or_404(Invoice, uuid=uuid, user=request.user)
        run = start_scan(
            request.user,
            trigger=InvoiceScanRun.Trigger.MANUAL,
            email_uuids=[str(invoice.email_message.uuid)],
            force=True,
        )
        return _response(
            {"run_uuid": str(run.uuid)},
            message=_("re-extraction started"),
            code=202,
            status_code=status.HTTP_202_ACCEPTED,
        )


class ExpenseInvoiceFileAPIView(APIView):
    """
    Serve the original document behind an invoice.

    Always authenticated and always scoped to the owner: these files carry
    tax numbers and billing titles, so there is no anonymous path to them.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        invoice = get_object_or_404(Invoice, uuid=uuid, user=request.user)

        source = invoice.email_attachment or invoice.source_file
        path = getattr(source, "file_path", "") if source else ""
        if not path or not os.path.exists(path):
            raise Http404("Original file is no longer available")

        filename = (
            getattr(source, "filename", None)
            or os.path.basename(path)
        )
        return FileResponse(
            open(path, "rb"),
            as_attachment=False,
            filename=filename,
        )

