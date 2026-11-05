from chat_sources.views import (
    SourceDetailAPIView,
    SourceImportListAPIView,
    SourceStatusAPIView,
    SourceVerifyAPIView,
    SpaceSourceListCreateAPIView,
)
from django.urls import path

urlpatterns = [
    path(
        "spaces/<int:space_id>/sources",
        SpaceSourceListCreateAPIView.as_view(),
        name="chat-source-list-create",
    ),
    path(
        "sources/<int:source_id>/verify",
        SourceVerifyAPIView.as_view(),
        name="chat-source-verify",
    ),
    path(
        "sources/<int:source_id>/status",
        SourceStatusAPIView.as_view(),
        name="chat-source-status",
    ),
    path(
        "sources/<int:source_id>/jobs",
        SourceImportListAPIView.as_view(),
        name="chat-source-jobs",
    ),
    path(
        "sources/<int:source_id>",
        SourceDetailAPIView.as_view(),
        name="chat-source-detail",
    ),
]
