"""Space membership roles and invitation status."""

from django.conf import settings
from django.db import models

from spaces.models.space import Space


class SpaceMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MAINTAINER = "maintainer", "Maintainer"
        USER = "user", "User"
        GUEST = "guest", "Guest"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        REMOVED = "removed", "Removed"

    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="space_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="space_invitations_sent",
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("space", "user"),
                name="unique_space_membership",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("space", "status", "role")),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.space_id}:{self.role}"
