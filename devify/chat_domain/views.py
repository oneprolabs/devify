from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat_analysis.models import Event
from chat_domain.avatars import avatar_path
from chat_domain.models import (
    Conversation,
    ConversationAvatar,
    Message,
    SenderAvatar,
)
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


def _sender_avatars(space, messages):
    """Map sender_key → SenderAvatar for the senders on this page."""
    keys = {message.sender_key for message in messages if message.sender_key}
    if not keys:
        return {}
    return {
        avatar.sender_key: avatar
        for avatar in SenderAvatar.objects.filter(
            space=space, sender_key__in=keys
        )
    }


def _conversations_with_pending_events(queryset):
    """Keep conversations that still have an open event attached."""
    return queryset.filter(
        messages__chat_note_evidence__note__event_links__event__status=(
            Event.Status.OPEN
        )
    ).distinct()


def _annotate_conversation_counts(queryset):
    """Attach participant and event counters used by the chat rail."""
    event_scope = Event.objects.filter(
        space_id=OuterRef("space_id"),
        note_links__note__evidence__message__conversation_id=OuterRef("pk"),
    )
    return queryset.annotate(
        participant_count=Coalesce(
            Subquery(
                Message.objects.filter(conversation=OuterRef("pk"))
                .exclude(sender_key="")
                .values("conversation")
                .annotate(total=Count("sender_key", distinct=True))
                .values("total")[:1],
                output_field=IntegerField(),
            ),
            0,
        ),
        event_count=Coalesce(
            Subquery(
                event_scope.order_by()
                .values("space_id")
                .annotate(total=Count("id", distinct=True))
                .values("total")[:1],
                output_field=IntegerField(),
            ),
            0,
        ),
        pending_event_count=Coalesce(
            Subquery(
                event_scope.filter(status=Event.Status.OPEN)
                .order_by()
                .values("space_id")
                .annotate(total=Count("id", distinct=True))
                .values("total")[:1],
                output_field=IntegerField(),
            ),
            0,
        ),
    )


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
        total = conversations.count()
        pending_total = _conversations_with_pending_events(
            conversations
        ).count()
        view_filter = request.query_params.get("filter", "").strip()
        if view_filter == "pending":
            conversations = _conversations_with_pending_events(conversations)
        elif view_filter not in ("", "all"):
            return Response(
                {"detail": "filter must be all or pending."},
                status=400,
            )
        conversations = _annotate_conversation_counts(conversations).order_by(
            "-last_message_at", "-id"
        ).select_related("avatar").annotate(
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
                    "counts": {"total": total, "pending": pending_total},
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
            _annotate_conversation_counts(
                Conversation.objects.filter(space=space).select_related(
                    "avatar"
                )
            ).annotate(
                latest_message_id=Subquery(
                    Message.objects.filter(conversation=OuterRef("pk"))
                    .order_by("-ingest_seq", "-id")
                    .values("id")[:1]
                )
            ),
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
        data = MessageListSerializer(
            page,
            many=True,
            context={"sender_avatars": _sender_avatars(space, page)},
        ).data
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
        return Response(
            {
                "data": MessageDetailSerializer(
                    message,
                    context={
                        "sender_avatars": _sender_avatars(space, [message])
                    },
                ).data
            }
        )


class SpaceAvatarAPIView(APIView):
    """Stream one avatar stored for the space, addressed by its digest."""

    permission_classes = [IsAuthenticated]

    def get(self, request, space_id, sha256):
        space, _takeover = _authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        avatar = ConversationAvatar.objects.filter(
            conversation__space=space, sha256=sha256
        ).first() or SenderAvatar.objects.filter(
            space=space, sha256=sha256
        ).first()
        if avatar is None:
            return Response({"detail": "Avatar not found."}, status=404)
        path = avatar_path(sha256)
        if not path.is_file():
            return Response({"detail": "Avatar not found."}, status=404)
        response = FileResponse(
            path.open("rb"), content_type=avatar.content_type
        )
        response["Cache-Control"] = "private, max-age=86400"
        return response
