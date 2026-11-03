from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_domain.models import Conversation, Message
from chat_domain.serializers import (
    ConversationDetailSerializer,
    ConversationListSerializer,
    MessageDetailSerializer,
    MessageListSerializer,
)
from spaces.models import Space, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action


class ChatPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class _ParamsRequest:
    """Minimal request wrapper that overrides query params for pagination."""

    def __init__(self, request, params):
        self._request = request
        self.query_params = params

    def build_absolute_uri(self, *args, **kwargs):
        return self._request.build_absolute_uri(*args, **kwargs)


def _latest_messages(conversations):
    """Map conversation id → its newest message, with parts prefetched."""
    latest_ids = [
        conversation.latest_message_id
        for conversation in conversations
        if getattr(conversation, "latest_message_id", None)
    ]
    if not latest_ids:
        return {}
    messages = Message.objects.filter(pk__in=latest_ids).prefetch_related(
        "parts"
    )
    return {message.conversation_id: message for message in messages}


def _authorized_space(user, space_id):
    space = get_object_or_404(Space, pk=space_id)
    if not SpacePermissionService.can_read(user, space):
        return None, None
    takeover = None
    if getattr(user, "is_staff", False):
        takeover = SpaceTakeover.objects.filter(
            space=space,
            admin=user,
            active=True,
        ).first()
    return space, takeover


def _pagination_data(paginator):
    return {
        "total": paginator.page.paginator.count,
        "page": paginator.page.number,
        "page_size": paginator.get_page_size(paginator.request),
        "next": paginator.get_next_link(),
        "previous": paginator.get_previous_link(),
    }


class SpaceConversationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)

        conversations = Conversation.objects.filter(space=space)
        platform = request.query_params.get("platform")
        if platform:
            conversations = conversations.filter(platform=platform)
        search = request.query_params.get("search", "").strip()
        if search:
            conversations = conversations.filter(
                Q(title__icontains=search)
                | Q(source_conversation_id__icontains=search)
            )
        conversations = conversations.order_by(
            "-last_message_at", "-id"
        ).annotate(
            latest_message_id=Subquery(
                Message.objects.filter(conversation=OuterRef("pk"))
                .order_by("-ingest_seq", "-id")
                .values("id")[:1]
            )
        )

        paginator = ChatPagination()
        page = paginator.paginate_queryset(conversations, request, view=self)
        data = ConversationListSerializer(
            page,
            many=True,
            context={"latest_messages": _latest_messages(page)},
        ).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.conversation_list_viewed",
                resource_type="conversation",
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )


class SpaceConversationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id, conversation_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        conversation = get_object_or_404(
            Conversation.objects.annotate(
                latest_message_id=Subquery(
                    Message.objects.filter(conversation=OuterRef("pk"))
                    .order_by("-ingest_seq", "-id")
                    .values("id")[:1]
                )
            ),
            space=space,
            pk=conversation_id,
        )
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.conversation_viewed",
                resource_type="conversation",
                resource_id=conversation.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": ConversationDetailSerializer(
                    conversation,
                    context={
                        "latest_messages": _latest_messages([conversation])
                    },
                ).data
            }
        )


class SpaceMessageListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id, conversation_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        conversation = get_object_or_404(
            Conversation,
            space=space,
            pk=conversation_id,
        )
        messages = (
            Message.objects.filter(conversation=conversation)
            .prefetch_related("parts")
            .order_by("ingest_seq", "id")
        )
        paginator = ChatPagination()
        pagination_request = request
        focus_id = request.query_params.get("focus_message_id", "").strip()
        if focus_id:
            if not focus_id.isdigit():
                return Response(
                    {"detail": "focus_message_id must be an integer."},
                    status=400,
                )
            anchor = messages.filter(pk=int(focus_id)).first()
            if anchor is not None:
                page_size = (
                    paginator.get_page_size(request) or paginator.page_size
                )
                before = messages.filter(
                    Q(ingest_seq__lt=anchor.ingest_seq)
                    | Q(ingest_seq=anchor.ingest_seq, pk__lt=anchor.pk)
                ).count()
                params = request.query_params.copy()
                params["page"] = str(before // page_size + 1)
                pagination_request = _ParamsRequest(request, params)
        page = paginator.paginate_queryset(
            messages, pagination_request, view=self
        )
        data = MessageListSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.message_list_viewed",
                resource_type="conversation",
                resource_id=conversation.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response(
            {
                "data": {
                    "list": data,
                    "pagination": _pagination_data(paginator),
                }
            }
        )


class SpaceMessageDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id, conversation_id, message_id):
        space, takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        message = get_object_or_404(
            Message.objects.prefetch_related("parts", "origins"),
            conversation__space=space,
            conversation_id=conversation_id,
            pk=message_id,
        )
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="chat.message_viewed",
                resource_type="message",
                resource_id=message.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": MessageDetailSerializer(message).data})
