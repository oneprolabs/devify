from django.urls import path

from feedback import views

urlpatterns = [
    path("feedbacks", views.FeedbackList.as_view()),
    path("feedbacks/<uuid:report_id>", views.FeedbackDetail.as_view()),
    path(
        "feedbacks/<uuid:report_id>/attachments/<uuid:attachment_id>",
        views.AttachmentDownload.as_view(),
    ),
    path("admin/feedbacks", views.AdminFeedbackList.as_view()),
    path(
        "admin/feedbacks/<uuid:report_id>", views.AdminFeedbackDetail.as_view()
    ),
]
