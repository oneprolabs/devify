from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.api_serializers import (
    ReportCreateSerializer,
    ReportSectionSerializer,
    ReportSerializer,
)
from chat_analysis.models import Report
from chat_analysis.report_services import create_report_snapshot
from chat_analysis.report_tasks import dispatch_report_generation
from chat_analysis.services import (
    ChatAnalysisConflict,
    ChatAnalysisPermissionError,
)
from spaces.models import Space, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action


class ReportPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


def _authorized_space(user, space_id, *, write=False):
    space = get_object_or_404(Space, pk=space_id)
    allowed = (
        SpacePermissionService.can_upload(user, space)
        if write
        else SpacePermissionService.can_read(user, space)
    )
    if not allowed:
        return None, None
    takeover = None
    if getattr(user, "is_staff", False):
        takeover = SpaceTakeover.objects.filter(
            space=space, admin=user, active=True
        ).first()
    return space, takeover


def _pagination_data(paginator):
    return {
        "total": paginator.page.paginator.count,
        "page": paginator.page.number,
        "page_size": paginator.get_page_size(paginator.request),
        "next": paginator.get_next_link(),
        "previous": paginator.get_previous_link(),
    }


class SpaceReportListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        reports = Report.objects.filter(space=space).order_by(
            "-generated_at", "-id"
        )
        state = request.query_params.get("status")
        if state:
            reports = reports.filter(status=state)
        paginator = ReportPagination()
        page = paginator.paginate_queryset(reports, request, view=self)
        data = ReportSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.report_list_viewed",
                resource_type="report",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )

    @transaction.atomic
    def post(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id, write=True)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report, created = create_report_snapshot(
                actor=request.user,
                space=space,
                **serializer.validated_data,
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        except ChatAnalysisConflict as error:
            return Response({"detail": str(error)}, status=409)
        if created:
            report.status = Report.Status.QUEUED
            report.processing = {
                **(report.processing or {}),
                "generator": "llm_pending",
                "version": "report.llm.v1",
            }
            report.save(update_fields=("status", "processing", "updated_at"))
            transaction.on_commit(lambda: dispatch_report_generation(report))
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.report_created" if created else "chat.report_reused",
            resource_type="report",
            resource_id=report.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response(
            {"data": ReportSerializer(report).data},
            status=202 if created else 200,
        )


class ReportDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_related("space"), pk=report_id
        )
        space, takeover = _authorized_space(request.user, report.space_id)
        if space is None:
            return Response({"detail": "Report not found."}, status=404)
        data = ReportSerializer(report).data
        data["sections"] = ReportSectionSerializer(
            report.sections.prefetch_related("items__sources"), many=True
        ).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.report_viewed",
                resource_type="report",
                resource_id=report.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": data})
