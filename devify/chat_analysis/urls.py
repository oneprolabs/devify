from django.urls import path

from chat_analysis.views import (
    AnalysisJobDetailAPIView,
    AnalysisJobRetryAPIView,
    SpaceAnalysisJobListCreateAPIView,
)


urlpatterns = [
    path(
        "spaces/<int:space_id>/analysis-jobs",
        SpaceAnalysisJobListCreateAPIView.as_view(),
        name="chat-analysis-job-list-create",
    ),
    path(
        "analysis-jobs/<int:job_id>",
        AnalysisJobDetailAPIView.as_view(),
        name="chat-analysis-job-detail",
    ),
    path(
        "analysis-jobs/<int:job_id>/retry",
        AnalysisJobRetryAPIView.as_view(),
        name="chat-analysis-job-retry",
    ),
]
