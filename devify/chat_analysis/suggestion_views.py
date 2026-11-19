from datetime import timedelta

from django.db import transaction
from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.api_serializers import EventSuggestionSerializer
from chat_analysis.api_views import (
    AnalysisPagination,
    _authorized_space,
    _pagination_data,
)
from chat_analysis.models import (
    DeferredEventCandidate,
    Event,
    EventEvidence,
    EventSuggestion,
)
from chat_analysis.suggestions import review_event_suggestion
from chat_domain.models import MessagePart
from spaces.models import Space
from spaces.services import SpacePermissionService, audit_space_action


class EventSuggestionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = get_object_or_404(Space, pk=space_id)
        if not SpacePermissionService.can_read(request.user, space):
            return Response({"detail": "Space not found."}, status=404)
        suggestions = EventSuggestion.objects.filter(space=space).order_by(
            "-created_at", "-id"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            suggestions = suggestions.filter(status=status_filter)
        return Response(
            {"data": EventSuggestionSerializer(suggestions, many=True).data}
        )


class EventSuggestionReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, suggestion_id):
        suggestion = get_object_or_404(
            EventSuggestion.objects.select_related("space"), pk=suggestion_id
        )
        if not SpacePermissionService.can_upload(
            request.user, suggestion.space
        ):
            return Response(
                {"detail": "Suggestion review permission required."},
                status=403,
            )
        decision = request.data.get("decision")
        if decision not in (
            EventSuggestion.Status.ACCEPTED,
            EventSuggestion.Status.REJECTED,
        ):
            return Response(
                {"detail": "decision must be accepted or rejected."},
                status=400,
            )
        suggestion = review_event_suggestion(
            actor=request.user, suggestion=suggestion, decision=decision
        )
        audit_space_action(
            actor=request.user,
            space=suggestion.space,
            action="chat.event_suggestion_reviewed",
            resource_type="event_suggestion",
            resource_id=suggestion.pk,
            metadata={"decision": decision},
        )
        return Response({"data": EventSuggestionSerializer(suggestion).data})


DEFERRED_REVIEW_WAIT = timedelta(minutes=30)


def _reviewable_deferred_candidates(space):
    return DeferredEventCandidate.objects.filter(
        space=space,
        conversation__space=space,
        message__conversation_id=F("conversation_id"),
        message__orphaned_at__isnull=True,
        urgent=True,
        created_at__lte=timezone.now() - DEFERRED_REVIEW_WAIT,
    )


def _deferred_review_row(candidate):
    part = next(iter(candidate.message.deferred_review_text), None)
    return {
        "id": candidate.pk,
        "reason": candidate.reason,
        "question": candidate.question,
        "created_at": candidate.created_at,
        "source": {
            "message_id": candidate.message_id,
            "conversation_id": candidate.conversation_id,
            "occurred_at": candidate.message.occurred_at,
            "excerpt": part.text.strip()[:240] if part else "",
        },
    }


class DeferredEventCandidateListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        candidates = _reviewable_deferred_candidates(space).filter(
            status=DeferredEventCandidate.Status.PENDING
        ).select_related("message").prefetch_related(
            Prefetch(
                "message__parts",
                queryset=MessagePart.objects.filter(kind=MessagePart.Kind.TEXT)
                .exclude(text="").order_by("ordinal", "id")[:1],
                to_attr="deferred_review_text",
            )
        ).order_by("created_at", "pk")
        paginator = AnalysisPagination()
        page = paginator.paginate_queryset(candidates, request, view=self)
        if takeover:
            audit_space_action(
                actor=request.user, space=space,
                action="chat.deferred_event_candidates_viewed",
                resource_type="deferred_event_candidate",
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": {
            "list": [_deferred_review_row(candidate) for candidate in page],
            "pagination": _pagination_data(paginator),
        }})


class DeferredEventCandidateReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("dismiss", "link"))
    event_id = serializers.IntegerField(
        required=False, min_value=1, max_value=2**63 - 1,
    )

    def validate(self, attrs):
        if (attrs["decision"] == "link") != ("event_id" in attrs):
            raise serializers.ValidationError({
                "event_id": "Provide an event_id only when linking a candidate.",
            })
        return attrs


class DeferredEventCandidateReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, space_id, candidate_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        if not SpacePermissionService.can_upload(request.user, space):
            return Response(
                {"detail": "Candidate review permission required."}, status=403,
            )
        serializer = DeferredEventCandidateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        target = None
        if decision == "link":
            # Publication locks Event before DeferredEventCandidate too.
            target = get_object_or_404(
                Event.objects.select_for_update(), space=space,
                pk=serializer.validated_data["event_id"],
            )
        candidate = get_object_or_404(
            _reviewable_deferred_candidates(space).select_for_update(),
            pk=candidate_id,
        )
        if candidate.status != DeferredEventCandidate.Status.PENDING:
            return Response(
                {"detail": "Candidate has already been reviewed or resolved."},
                status=409,
            )
        if target is not None:
            EventEvidence.objects.get_or_create(
                event=target, message_id=candidate.message_id,
                defaults={"created_by": request.user},
            )
        candidate.status = (
            DeferredEventCandidate.Status.RESOLVED
            if target is not None else DeferredEventCandidate.Status.DISMISSED
        )
        candidate.resolved_event = target
        # Retain any staged suggestion link so publication can recognize
        # and suppress a proposal superseded by this human decision.
        candidate.save(update_fields=("status", "resolved_event", "updated_at"))
        metadata = {"decision": decision, "event_id": candidate.resolved_event_id}
        if takeover:
            metadata["takeover_id"] = takeover.pk
        audit_space_action(
            actor=request.user, space=space,
            action="chat.deferred_event_candidate_reviewed",
            resource_type="deferred_event_candidate", resource_id=candidate.pk,
            metadata=metadata,
        )
        return Response({"data": {
            "id": candidate.pk,
            "status": candidate.status,
            "resolved_event_id": candidate.resolved_event_id,
        }})
