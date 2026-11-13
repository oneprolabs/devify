from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.api_serializers import EventSuggestionSerializer
from chat_analysis.models import EventSuggestion
from chat_analysis.suggestions import review_event_suggestion
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
