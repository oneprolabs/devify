from django.urls import path

from chat_ingestion.views import (
    UploadBatchArchiveAPIView,
    UploadBatchCancelAPIView,
    UploadBatchCompleteAPIView,
    UploadBatchCreateAPIView,
    UploadBatchDetailAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/chat/uploads",
        UploadBatchCreateAPIView.as_view(),
        name="chat-upload-create",
    ),
    path(
        "chat/uploads/<int:batch_id>",
        UploadBatchDetailAPIView.as_view(),
        name="chat-upload-detail",
    ),
    path(
        "chat/uploads/<int:batch_id>/archive",
        UploadBatchArchiveAPIView.as_view(),
        name="chat-upload-archive",
    ),
    path(
        "chat/uploads/<int:batch_id>/complete",
        UploadBatchCompleteAPIView.as_view(),
        name="chat-upload-complete",
    ),
    path(
        "chat/uploads/<int:batch_id>/cancel",
        UploadBatchCancelAPIView.as_view(),
        name="chat-upload-cancel",
    ),
]
