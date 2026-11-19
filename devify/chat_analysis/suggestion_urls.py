from django.urls import path

from chat_analysis.suggestion_views import (
    DeferredEventCandidateListAPIView,
    DeferredEventCandidateReviewAPIView,
    EventSuggestionListAPIView,
    EventSuggestionReviewAPIView,
)

urlpatterns = [
    path(
        "spaces/<uuid:space_id>/deferred-event-candidates",
        DeferredEventCandidateListAPIView.as_view(),
        name="chat-deferred-event-candidate-list",
    ),
    path(
        "spaces/<uuid:space_id>/deferred-event"
        "-candidates/<int:candidate_id>/review",
        DeferredEventCandidateReviewAPIView.as_view(),
        name="chat-deferred-event-candidate-review",
    ),
    path(
        "spaces/<uuid:space_id>/event-suggestions",
        EventSuggestionListAPIView.as_view(),
        name="chat-event-suggestion-list",
    ),
    path(
        "event-suggestions/<int:suggestion_id>/review",
        EventSuggestionReviewAPIView.as_view(),
        name="chat-event-suggestion-review",
    ),
]
