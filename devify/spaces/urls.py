from django.urls import path

from spaces.views import (
    OwnerlessSpaceListAPIView,
    SpaceDetailAPIView,
    SpaceInvitationListAPIView,
    SpaceListCreateAPIView,
    SpaceMemberAcceptAPIView,
    SpaceMemberActionAPIView,
    SpaceMemberListCreateAPIView,
    SpaceOwnershipAPIView,
    SpacePolicyAPIView,
    SpaceTakeoverAPIView,
)

urlpatterns = [
    path("spaces", SpaceListCreateAPIView.as_view(), name="space-list-create"),
    path(
        "spaces/invitations",
        SpaceInvitationListAPIView.as_view(),
        name="space-invitations",
    ),
    path(
        "spaces/<int:space_id>",
        SpaceDetailAPIView.as_view(),
        name="space-detail",
    ),
    path(
        "spaces/<int:space_id>/members",
        SpaceMemberListCreateAPIView.as_view(),
        name="space-members",
    ),
    path(
        "spaces/<int:space_id>/members/<int:user_id>",
        SpaceMemberActionAPIView.as_view(),
        name="space-member-action",
    ),
    path(
        "spaces/<int:space_id>/members/<int:user_id>/accept",
        SpaceMemberAcceptAPIView.as_view(),
        name="space-member-accept",
    ),
    path(
        "spaces/<int:space_id>/takeover",
        SpaceTakeoverAPIView.as_view(),
        name="space-takeover",
    ),
    path(
        "spaces/<int:space_id>/ownership",
        SpaceOwnershipAPIView.as_view(),
        name="space-ownership",
    ),
    path(
        "admin/spaces/ownerless",
        OwnerlessSpaceListAPIView.as_view(),
        name="ownerless-space-list",
    ),
    path(
        "admin/spaces/policy",
        SpacePolicyAPIView.as_view(),
        name="space-policy",
    ),
]
