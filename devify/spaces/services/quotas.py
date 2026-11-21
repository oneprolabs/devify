"""Space membership, AI usage, and storage quota checks."""

from django.db import models
from django.utils import timezone


def get_space_quota(space):
    from spaces.models import SpaceQuota

    quota, _ = SpaceQuota.objects.get_or_create(space=space)
    return quota


def check_member_quota(space):
    quota = get_space_quota(space)
    if quota.max_members is None:
        return None
    count = space.memberships.filter(status="active").count()
    if count >= quota.max_members:
        return "Space member quota exceeded."
    return None


def check_daily_ai_quota(space):
    quota = get_space_quota(space)
    if quota.daily_ai_calls is None:
        return None
    from chat_analysis.models import ChatSummary, QuestionAnswer

    start = timezone.localtime(timezone.now()).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    count = QuestionAnswer.objects.filter(
        space=space, created_at__gte=start
    ).count()
    count += ChatSummary.objects.filter(
        space=space, created_at__gte=start
    ).count()
    if count >= quota.daily_ai_calls:
        return "Space daily AI quota exceeded."
    return None


def check_storage_quota(space, additional_bytes=0):
    quota = get_space_quota(space)
    if quota.storage_limit_bytes is None:
        return None
    from chat_ingestion.models import UploadBatch

    used = (
        UploadBatch.objects.filter(space=space)
        .exclude(status="cancelled")
        .aggregate(total=models.Sum("archive_size"))["total"]
        or 0
    )
    if used + int(additional_bytes or 0) > quota.storage_limit_bytes:
        return "Space storage quota exceeded."
    return None
