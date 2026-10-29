from django.urls import path

from chat_sources.views import (
    SourceDetailAPIView,
    SpaceSourceListCreateAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/sources",
        SpaceSourceListCreateAPIView.as_view(),
        name="chat-source-list-create",
    ),
    path(
        "sources/<int:source_id>",
        SourceDetailAPIView.as_view(),
        name="chat-source-detail",
    ),
]
