"""Space membership and access checks."""

from spaces.models import Space, SpaceMembership, SpaceTakeover


class SpacePermissionService:
    ADMIN_ROLES = {
        SpaceMembership.Role.OWNER,
        SpaceMembership.Role.MAINTAINER,
    }
    WRITE_ROLES = ADMIN_ROLES | {SpaceMembership.Role.USER}

    @staticmethod
    def membership(user, space):
        return SpaceMembership.objects.filter(
            user=user,
            space=space,
            status=SpaceMembership.Status.ACTIVE,
        ).first()

    @classmethod
    def can_manage(cls, membership):
        return bool(
            membership
            and membership.status == SpaceMembership.Status.ACTIVE
            and membership.role in cls.ADMIN_ROLES
        )

    @classmethod
    def can_write(cls, membership):
        return bool(
            membership
            and membership.status == SpaceMembership.Status.ACTIVE
            and membership.role in cls.WRITE_ROLES
        )

    @classmethod
    def can_read(cls, user, space):
        if not getattr(user, "is_authenticated", False):
            return False
        # Membership always wins, including for staff accounts: every account
        # gets a personal space at bootstrap and the space list exposes it, so
        # denying staff their own spaces left those pages failing with 404.
        if cls.membership(user, space) is not None:
            return True
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        return False

    @classmethod
    def readable_space_ids(cls, user):
        """Space ids this user may read right now.

        Same rules as ``can_read``: active memberships for everyone, plus
        active takeovers for staff. Used to filter legacy per-user queries so
        they cannot bypass the space boundary.
        """
        if not getattr(user, "is_authenticated", False):
            return set()
        space_ids = set(
            SpaceMembership.objects.filter(
                user=user,
                status=SpaceMembership.Status.ACTIVE,
            ).values_list("space_id", flat=True)
        )
        if getattr(user, "is_staff", False):
            space_ids |= set(
                SpaceTakeover.objects.filter(
                    admin=user, active=True
                ).values_list("space_id", flat=True)
            )
        return space_ids

    @classmethod
    def can_upload(cls, user, space):
        if (
            not getattr(user, "is_authenticated", False)
            or space.status != Space.Status.ACTIVE
        ):
            return False
        if cls.can_write(cls.membership(user, space)):
            return True
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        return False

    @classmethod
    def can_delete_resource(cls, user, space, uploaded_by_id):
        if (
            not getattr(user, "is_authenticated", False)
            or space.status != Space.Status.ACTIVE
        ):
            return False
        membership = cls.membership(user, space)
        if membership and (
            cls.can_manage(membership) or user.pk == uploaded_by_id
        ):
            return True
        if getattr(user, "is_staff", False):
            return cls.has_active_takeover(user, space)
        return False

    @staticmethod
    def has_active_takeover(user, space):
        return SpaceTakeover.objects.filter(
            admin=user,
            space=space,
            active=True,
        ).exists()
