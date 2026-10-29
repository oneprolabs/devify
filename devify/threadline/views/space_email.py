from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from spaces.models import Space, SpaceMembership, SpaceTakeover
from spaces.services import SpacePermissionService, audit_space_action
from threadline.models import EmailMessage
from threadline.serializers.space_email import (
    SpaceEmailDetailSerializer,
    SpaceEmailSerializer,
)


def authorized_space(user, space_id):
    space = get_object_or_404(Space.objects.select_for_update(), pk=space_id)
    if user.is_staff:
        takeover = SpaceTakeover.objects.select_for_update().filter(
            space=space, admin=user, active=True
        ).first()
        if not takeover:
            return None, None
        return space, takeover
    if not SpaceMembership.objects.filter(
        space=space, user=user, status=SpaceMembership.Status.ACTIVE
    ).exists():
        return None, None
    return space, None


class SpaceEmailPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class SpaceEmailListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request, space_id):
        space, takeover = authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        emails = EmailMessage.objects.filter(
            space=space, merged_into__isnull=True
        ).order_by("-received_at", "-id")
        paginator = SpaceEmailPagination()
        page = paginator.paginate_queryset(emails, request, view=self)
        data = SpaceEmailSerializer(page, many=True).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="email.list_viewed",
                resource_type="email",
                metadata={
                    "takeover_id": takeover.pk,
                    "page": paginator.page.number,
                },
            )
        return Response({"data": {
            "list": data,
            "pagination": {
                "total": paginator.page.paginator.count,
                "page": paginator.page.number,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
            },
        }})


class SpaceEmailDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request, space_id, email_uuid):
        space, takeover = authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        email = get_object_or_404(EmailMessage, space=space, uuid=email_uuid)
        data = SpaceEmailDetailSerializer(email).data
        if takeover:
            audit_space_action(
                actor=request.user,
                space=space,
                action="email.viewed",
                resource_type="email",
                resource_id=email.pk,
                metadata={"takeover_id": takeover.pk},
            )
        return Response({"data": data})

    @transaction.atomic
    def delete(self, request, space_id, email_uuid):
        space, takeover = authorized_space(request.user, space_id)
        if space is None:
            return Response({"detail": "Space not found."}, status=404)
        email = get_object_or_404(EmailMessage, space=space, uuid=email_uuid)
        if space.status != Space.Status.ACTIVE:
            return Response(
                {"detail": "Archived spaces are read-only."}, status=409
            )
        if not SpacePermissionService.can_delete_resource(
            request.user, space, email.user_id
        ):
            return Response(
                {"detail": "Resource deletion permission required."},
                status=403,
            )
        audit_space_action(
            actor=request.user,
            space=space,
            action="email.deleted",
            resource_type="email",
            resource_id=email.pk,
            metadata={
                "uploaded_by_id": email.user_id,
                "takeover_id": takeover.pk if takeover else None,
            },
        )
        email.delete()
        return Response(status=204)
