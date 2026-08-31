"""Expense API views."""

from __future__ import annotations

import logging
import os

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.services.config_service import get_credit_policy
from billing.services.credits_service import CreditsService
from expense.models import (
    ExpenseGroup,
    Invoice,
    InvoiceScanRun,
    InvoiceSourceFile,
    TripSuggestion,
)
from expense.serializers import (
    ExpenseAppConfigSerializer,
    ExpenseUserConfigSerializer,
    ExpenseGroupSerializer,
    GroupItemsSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    InvoiceScanRunDetailSerializer,
    InvoiceScanRunSerializer,
    InvoiceSourceFileSerializer,
    InvoiceUpdateSerializer,
    ScanRequestSerializer,
    TripSuggestionSerializer,
)
from expense.services.config_service import (
    get_app_config,
    get_user_config,
    set_user_enabled,
)
from expense.services.scan_scheduler import sync_scan_periodic_task
from expense.services import export as export_service
from expense.services import invoices as invoice_service
from expense.services import groups as group_service
from expense.services import trips as trip_service
from expense.services import naming
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
            # Failed reads, non-invoices and duplicates are noise in the
            # default view: none of them can be claimed, and counting them
            # inflates every chip. They stay reachable through an explicit
            # status filter.
            queryset = queryset.filter(status=Invoice.Status.EXTRACTED)

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

        if params.get("buyer"):
            queryset = queryset.filter(buyer_name=params["buyer"])

        # The lifecycle stage is the list's primary question -- what have I
        # not claimed yet -- so it is a first-class filter rather than
        # something to reconstruct from group membership by hand.
        stage = params.get("stage")
        if stage and stage != "all":
            queryset = invoice_service.by_stage(queryset, stage)
        if params.get("q"):
            term = params["q"]
            queryset = queryset.filter(
                Q(seller_name__icontains=term)
                | Q(invoice_no__icontains=term)
                | Q(buyer_name__icontains=term)
            )

        rows = queryset.select_related("email_message")[:200]
        return _response(
            {
                "invoices": InvoiceListSerializer(rows, many=True).data,
                "counts": invoice_service.stage_counts(request.user),
                "buyers": invoice_service.buyer_titles(request.user),
            }
        )


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


def _bad_request(message):
    return Response(
        {"code": 400, "message": str(message), "data": None},
        status=status.HTTP_400_BAD_REQUEST,
    )


class ExpenseGroupListAPIView(APIView):
    """Reimbursement groups belonging to the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = ExpenseGroup.objects.filter(user=request.user)
        if request.query_params.get("status"):
            queryset = queryset.filter(
                status=request.query_params["status"]
            )
        return _response(ExpenseGroupSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ExpenseGroupSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        if ExpenseGroup.objects.filter(
            user=request.user, name=serializer.validated_data["name"]
        ).exists():
            return _bad_request(_("A group with that name already exists."))

        group = serializer.save(user=request.user)
        return _response(
            ExpenseGroupSerializer(group).data,
            message=_("created"),
            code=201,
            status_code=status.HTTP_201_CREATED,
        )


class ExpenseGroupDetailAPIView(APIView):
    """Read, rename, restate or delete one group."""

    permission_classes = [IsAuthenticated]

    def _get_object(self, request, uuid):
        return get_object_or_404(ExpenseGroup, uuid=uuid, user=request.user)

    def get(self, request, uuid):
        group = self._get_object(request, uuid)
        invoices = group_service.group_invoices(group)
        data = ExpenseGroupSerializer(group).data
        data["invoices"] = InvoiceListSerializer(invoices, many=True).data
        # A claim form is filled in one category at a time, so the detail
        # view offers the same invoices already split that way.
        data["sections"] = [
            {
                **section,
                "invoices": InvoiceListSerializer(
                    section["invoices"], many=True
                ).data,
            }
            for section in group_service.category_sections(invoices)
        ]
        return _response(data)

    def patch(self, request, uuid):
        group = self._get_object(request, uuid)
        serializer = ExpenseGroupSerializer(
            group, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return _response(ExpenseGroupSerializer(group).data)

    def delete(self, request, uuid):
        group = self._get_object(request, uuid)
        group.delete()
        return _response(None, message=_("deleted"))


class ExpenseGroupItemsAPIView(APIView):
    """Add invoices to a group, or take them back out."""

    permission_classes = [IsAuthenticated]

    def _get_group(self, request, uuid):
        return get_object_or_404(ExpenseGroup, uuid=uuid, user=request.user)

    def post(self, request, uuid):
        group = self._get_group(request, uuid)
        serializer = GroupItemsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        try:
            added = group_service.add_invoices(
                group,
                [
                    str(item)
                    for item in serializer.validated_data["invoice_uuids"]
                ],
            )
        except group_service.GroupError as exc:
            return _bad_request(exc)

        data = ExpenseGroupSerializer(group).data
        data["added"] = added
        return _response(data)

    def put(self, request, uuid):
        """
        Move invoices into this group from wherever they are now.

        POST refuses an invoice held by another group because claiming the
        same expense twice is unrecoverable. Putting one in the wrong group
        is an ordinary mistake, though, so correcting it gets its own verb
        rather than making the user detach and re-attach by hand.
        """
        group = self._get_group(request, uuid)
        serializer = GroupItemsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        try:
            result = group_service.move_invoices(
                group,
                [
                    str(item)
                    for item in serializer.validated_data["invoice_uuids"]
                ],
            )
        except group_service.GroupError as exc:
            return _bad_request(exc)

        data = ExpenseGroupSerializer(group).data
        data.update(result)
        return _response(data)

    def delete(self, request, uuid):
        group = self._get_group(request, uuid)
        serializer = GroupItemsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        removed = group_service.remove_invoices(
            group,
            [
                str(item)
                for item in serializer.validated_data["invoice_uuids"]
            ],
        )
        data = ExpenseGroupSerializer(group).data
        data["removed"] = removed
        return _response(data)


class ExpenseGroupSummaryAPIView(APIView):
    """The figures a claim form asks for, structured and as pasteable text."""

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        group = get_object_or_404(ExpenseGroup, uuid=uuid, user=request.user)
        return _response(group_service.build_summary(group))


class ExpenseGroupExportAPIView(APIView):
    """
    Package the group as a zip of uniformly named files.

    ``preview=true`` returns the filenames the current template would
    produce, so a naming template can be checked before it is used.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        group = get_object_or_404(ExpenseGroup, uuid=uuid, user=request.user)
        template = (
            request.query_params.get("template")
            or get_user_config(request.user).filename_template
        )
        by_category = request.query_params.get("flat") != "true"

        try:
            if request.query_params.get("preview") == "true":
                plan = export_service.plan_export(
                    group, template, by_category
                )
                return _response(
                    {
                        "total_bytes": plan["total_bytes"],
                        "missing_files": plan["missing_files"],
                        "files": [
                            {
                                "filename": entry["filename"],
                                "path": entry["arcname"],
                                "size": entry["size"],
                            }
                            for entry in plan["entries"]
                        ],
                    }
                )

            archive_path = export_service.write_archive(
                group, template, by_category
            )
        except export_service.ExportError as exc:
            return _bad_request(exc)

        group.exported_at = timezone.now()
        group.save(update_fields=["exported_at", "updated_at"])

        # The archive is a scratch file; hand it to the client and let it
        # go rather than leaving copies behind on the worker.
        handle = open(archive_path, "rb")
        os.unlink(archive_path)
        return FileResponse(
            handle,
            as_attachment=True,
            filename=f"{naming.sanitize(group.name)}.zip",
            content_type="application/zip",
        )


class ExpenseTripListAPIView(APIView):
    """Business trips inferred from the invoice timeline."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = TripSuggestion.objects.filter(
            user=request.user, status=TripSuggestion.Status.SUGGESTED
        )
        return _response(TripSuggestionSerializer(queryset, many=True).data)

    def post(self, request):
        """Recompute suggestions. Costs nothing; calls no model."""
        config = get_user_config(request.user)
        created = trip_service.refresh_suggestions(
            request.user, config.home_city
        )
        queryset = TripSuggestion.objects.filter(
            user=request.user, status=TripSuggestion.Status.SUGGESTED
        )
        return _response(
            {
                "created": created,
                "suggestions": TripSuggestionSerializer(
                    queryset, many=True
                ).data,
            }
        )


class ExpenseTripAcceptAPIView(APIView):
    """Turn one suggestion into a real group."""

    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        suggestion = get_object_or_404(
            TripSuggestion, uuid=uuid, user=request.user
        )
        if suggestion.status != TripSuggestion.Status.SUGGESTED:
            return _bad_request(_("This suggestion was already decided."))

        try:
            group = trip_service.accept(
                suggestion, (request.data or {}).get("name", "")
            )
        except group_service.GroupError as exc:
            return _bad_request(exc)

        return _response(
            ExpenseGroupSerializer(group).data,
            message=_("accepted"),
            code=201,
            status_code=status.HTTP_201_CREATED,
        )


class ExpenseTripDismissAPIView(APIView):
    """Set one suggestion aside without acting on it."""

    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        suggestion = get_object_or_404(
            TripSuggestion, uuid=uuid, user=request.user
        )
        suggestion.status = TripSuggestion.Status.DISMISSED
        suggestion.save(update_fields=["status", "updated_at"])
        return _response(TripSuggestionSerializer(suggestion).data)


class ExpenseInvoiceFileAwayAPIView(APIView):
    """
    Set invoices aside as never-to-be-claimed, or put them back.

    Without this an invoice that will never be claimed has nowhere to go
    and keeps asking to be dealt with.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GroupItemsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        uuids = [
            str(item) for item in serializer.validated_data["invoice_uuids"]
        ]
        reason = (request.data or {}).get("reason", "")

        filed = invoice_service.file_invoices(request.user, uuids, reason)
        return _response(
            {
                "filed": filed,
                "skipped": len(uuids) - filed,
                "counts": invoice_service.stage_counts(request.user),
            },
            message=_("filed"),
        )

    def delete(self, request):
        serializer = GroupItemsSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        uuids = [
            str(item) for item in serializer.validated_data["invoice_uuids"]
        ]

        restored = invoice_service.unfile_invoices(request.user, uuids)
        return _response(
            {
                "restored": restored,
                "counts": invoice_service.stage_counts(request.user),
            },
            message=_("restored"),
        )

