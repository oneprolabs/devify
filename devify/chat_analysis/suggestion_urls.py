from django.urls import path

from chat_analysis.suggestion_views import (
    EventSuggestionListAPIView,
    EventSuggestionReviewAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/event-suggestions",
        EventSuggestionListAPIView.as_view(),
        name="chat-event-suggestion-list",
    ),
    path(
        "event-suggestions/<int:suggestion_id>/review",
        EventSuggestionReviewAPIView.as_view(),
        name="chat-event-suggestion-review",
    ),
]
