from django.urls import path

from accounts.views.management import (
    ManagementGroupListView,
    ManagementUserDetailView,
    ManagementUserListView,
)

urlpatterns = [
    path("users/", ManagementUserListView.as_view(), name="management-users"),
    path(
        "users/<int:pk>/",
        ManagementUserDetailView.as_view(),
        name="management-user-detail",
    ),
    path(
        "groups/",
        ManagementGroupListView.as_view(),
        name="management-groups",
    ),
]
