"""Personal space bootstrap operations."""

from django.db import transaction

from spaces.models import Space, SpaceMembership


class SpaceBootstrapService:
    @staticmethod
    @transaction.atomic
    def ensure_personal_space(user):
        space, _ = Space.objects.get_or_create(
            personal_owner=user,
            defaults={
                "name": f"{user.get_username()[:112]}'s Space",
                "slug": SpaceBootstrapService._personal_slug(user),
                "kind": Space.Kind.PERSONAL,
                "owner": user,
                "created_by": user,
            },
        )
        SpaceMembership.objects.get_or_create(
            space=space,
            user=user,
            defaults={
                "role": SpaceMembership.Role.OWNER,
                "status": SpaceMembership.Status.ACTIVE,
            },
        )
        return space

    @staticmethod
    def _personal_slug(user):
        return f"personal-{user.pk}"
