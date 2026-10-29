from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.models import AnalysisJob
from chat_analysis.serializers import (
    AnalysisJobCreateSerializer,
    AnalysisJobSerializer,
)
from chat_analysis.services import (
    ChatAnalysisConflict,
    ChatAnalysisPermissionError,
    create_analysis_job,
    retry_analysis_job,
)
from chat_analysis.tasks import dispatch_analysis_job
from chat_domain.models import Conversation
from spaces.models import Space, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action


class AnalysisJobPagination(PageNumberPagination):
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
            space=space,
            admin=user,
            active=True,
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


def _queue_job(job):
    transaction.on_commit(lambda: dispatch_analysis_job(job))


class SpaceAnalysisJobListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        jobs = AnalysisJob.objects.filter(space=space).order_by(
            "-created_at", "-id"
        )
        state = request.query_params.get("state")
        if state:
            jobs = jobs.filter(state=state)
        paginator = AnalysisJobPagination()
        page = paginator.paginate_queryset(jobs, request, view=self)
        data = AnalysisJobSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.analysis_job_list_viewed",
                resource_type="analysis_job",
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
        space, takeover = _authorized_space(
            request.user, space_id, write=True
        )
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        serializer = AnalysisJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        conversation = Conversation.objects.filter(
            pk=values["conversation_id"],
            space=space,
        ).first()
        if conversation is None:
            return Response(
                {"detail": "Conversation not found."}, status=404
            )
        try:
            job = create_analysis_job(
                actor=request.user,
                space=space,
                conversation=conversation,
                request_key=values["request_key"],
                start_seq=values["start_seq"],
                end_seq=values["end_seq"],
                input_version=values["input_version"],
                specification=values["specification"],
            )
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        except ChatAnalysisConflict as error:
            return Response({"detail": str(error)}, status=409)
        _queue_job(job)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.analysis_job_created",
            resource_type="analysis_job",
            resource_id=job.pk,
            metadata={
                "takeover_id": takeover.pk if takeover else None,
                "created": job.created_by_id == request.user.pk,
            },
        )
        return Response(
            {"data": AnalysisJobSerializer(job).data},
            status=202 if job.state == AnalysisJob.State.QUEUED else 200,
        )


class AnalysisJobDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_object_or_404(
            AnalysisJob.objects.select_related("space"), pk=job_id
        )
        space, takeover = _authorized_space(request.user, job.space_id)
        if space is None:
            return Response({"detail": "Analysis job not found."}, status=404)
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.analysis_job_viewed",
                resource_type="analysis_job",
                resource_id=job.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": AnalysisJobSerializer(job).data})


class AnalysisJobRetryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, job_id):
        """Retry a failed or partial job without changing its input window."""
        job = get_object_or_404(
            AnalysisJob.objects.select_for_update().select_related("space"),
            pk=job_id,
        )
        space, takeover = _authorized_space(
            request.user, job.space_id, write=True
        )
        if space is None:
            return Response({"detail": "Analysis job not found."}, status=404)
        try:
            job = retry_analysis_job(actor=request.user, job=job)
        except ChatAnalysisPermissionError as error:
            return Response({"detail": str(error)}, status=403)
        except ChatAnalysisConflict as error:
            return Response({"detail": str(error)}, status=409)
        _queue_job(job)
        audit_space_action(
            actor=request.user,
            space=space,
            action="chat.analysis_job_retried",
            resource_type="analysis_job",
            resource_id=job.pk,
            metadata={"takeover_id": takeover.pk if takeover else None},
        )
        return Response({"data": AnalysisJobSerializer(job).data}, status=202)
