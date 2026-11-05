from django.urls import path

from chat_domain.views import (
    SpaceAvatarAPIView,
    SpaceConversationDetailAPIView,
    SpaceConversationListAPIView,
    SpaceMediaAPIView,
    SpaceMessageDetailAPIView,
    SpaceMessageListAPIView,
)

urlpatterns = [
    path(
        "spaces/<int:space_id>/media/<int:item_id>",
        SpaceMediaAPIView.as_view(),
        name="chat-media",
    ),
    path(
        "spaces/<int:space_id>/avatars/<str:sha256>",
        SpaceAvatarAPIView.as_view(),
        name="chat-avatar",
    ),
    path(
        "spaces/<int:space_id>/conversations",
        SpaceConversationListAPIView.as_view(),
        name="chat-conversation-list",
    ),
    path(
        "spaces/<int:space_id>/conversations/<int:conversation_id>",
        SpaceConversationDetailAPIView.as_view(),
        name="chat-conversation-detail",
    ),
    path(
        "spaces/<int:space_id>/conversations/<int:conversation_id>/messages",
        SpaceMessageListAPIView.as_view(),
        name="chat-message-list",
    ),
    path(
        "spaces/<int:space_id>/conversations/"
        "<int:conversation_id>/messages/<int:message_id>",
        SpaceMessageDetailAPIView.as_view(),
        name="chat-message-detail",
    ),
]
