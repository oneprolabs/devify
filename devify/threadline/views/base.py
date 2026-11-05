"""
Base APIView class for Threadline models

This module contains the BaseAPIView class that provides common functionality
for all Threadline APIView classes, including user filtering, object retrieval,
and common patterns.
"""

import logging

from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from spaces.services import SpacePermissionService

logger = logging.getLogger(__name__)


def email_visibility_q(user, prefix=""):
    """Rows whose space the user may read right now.

    Legacy endpoints filter by ``user`` alone; that is not enough once a
    message belongs to a space, because a removed member would keep reading
    it. Everything space-bound must also pass the current space check.
    """
    return models.Q(**{f"{prefix}space__isnull": True}) | models.Q(
        **{
            f"{prefix}space_id__in": (
                SpacePermissionService.readable_space_ids(user)
            )
        }
    )


class BaseAPIView(APIView):
    """
    Base APIView with common functionality for all Threadline models

    This class provides:
    - Authentication requirement (IsAuthenticated)
    - User-based filtering for querysets
    - Object retrieval with user ownership validation
    - Common error handling patterns
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Get queryset for the model

        Must be implemented by subclasses

        Returns:
            QuerySet: The base queryset for the model
        """
        raise NotImplementedError("Subclasses must implement get_queryset")

    def filter_by_user(self, queryset):
        """
        Filter queryset by current user

        This method can be overridden by subclasses for models that have
        different user relationship patterns (e.g., through foreign keys)

        Args:
            queryset: The queryset to filter

        Returns:
            QuerySet: Filtered queryset containing only user's objects
        """
        queryset = queryset.filter(user=self.request.user)
        field_names = {
            field.name for field in queryset.model._meta.get_fields()
        }
        if "space" in field_names:
            queryset = queryset.filter(email_visibility_q(self.request.user))
        return queryset

    def get_object(self, pk):
        """
        Get object by primary key, ensuring user ownership

        Args:
            pk: Primary key of the object to retrieve

        Returns:
            Model instance: The requested object

        Raises:
            Http404: If object doesn't exist or doesn't belong to user
        """
        queryset = self.filter_by_user(self.get_queryset())
        return get_object_or_404(queryset, pk=pk)
