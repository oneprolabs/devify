from django.urls import path

from chat_analysis.report_views import (
    ReportDetailAPIView,
    SpaceReportListCreateAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/reports",
        SpaceReportListCreateAPIView.as_view(),
        name="chat-report-list-create",
    ),
    path(
        "reports/<int:report_id>",
        ReportDetailAPIView.as_view(),
        name="chat-report-detail",
    ),
]
