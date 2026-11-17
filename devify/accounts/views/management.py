from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Prefetch
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.services.user_bootstrap import UserBootstrapService

User = get_user_model()


def _safe_int(value, default, min_value=1, max_value=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min(parsed, max_value), min_value)


def _paginated_payload(items, total, page, page_size):
    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": items,
    }


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _user_queryset():
    groups_prefetch = Prefetch(
        "groups",
        queryset=Group.objects.order_by("name"),
        to_attr="ordered_groups",
    )
    return (
        User.objects.select_related("profile")
        .prefetch_related(groups_prefetch)
        .order_by("id")
    )


def _bad_request(detail, code):
    return Response(
        {"detail": detail, "code": code},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _valid_group_ids(group_ids):
    return isinstance(group_ids, (list, tuple)) and all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in group_ids
    )


def _display_name(user):
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}".strip()
    if user.first_name:
        return user.first_name.strip()
    try:
        profile = user.profile
    except Exception:
        profile = None
    if profile and profile.nickname:
        return profile.nickname
    return user.username


def _group_payload(group):
    return {
        "id": group.pk,
        "name": group.name,
        "user_count": getattr(group, "user_count", None),
        "permission_count": getattr(group, "permission_count", None),
    }


def _user_payload(user):
    if user is None:
        return None

    try:
        profile = user.profile
    except Exception:
        profile = None

    language = profile.language if profile else "zh-CN"
    timezone = profile.timezone if profile else "Asia/Shanghai"

    ordered_groups = getattr(user, "ordered_groups", None)
    if ordered_groups is None:
        ordered_groups = user.groups.all().order_by("name")

    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "display_name": _display_name(user),
        "is_staff": bool(user.is_staff),
        "is_active": bool(user.is_active),
        "date_joined": (
            user.date_joined.isoformat() if user.date_joined else None
        ),
        "language": language,
        "timezone": timezone,
        "groups": [_group_payload(group) for group in ordered_groups],
    }


class ManagementUserListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        page = _safe_int(request.query_params.get("page"), default=1)
        page_size = _safe_int(
            request.query_params.get("page_size"),
            default=20,
        )
        qs = _user_queryset()
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [_user_payload(user) for user in qs[start:end]]
        return Response(_paginated_payload(items, total, page, page_size))

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        is_staff = _as_bool(request.data.get("is_staff", False))
        is_active = request.data.get("is_active", True)
        language = (request.data.get("language") or "").strip() or "zh-CN"
        timezone = (
            request.data.get("timezone") or ""
        ).strip() or "Asia/Shanghai"
        group_ids = request.data.get("group_ids") or []
        if not _valid_group_ids(group_ids):
            return _bad_request(
                "group_ids must be a list of integers.",
                "invalid_group_ids",
            )

        if not username:
            return Response(
                {
                    "detail": "Username is required.",
                    "code": "username_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not password:
            return Response(
                {
                    "detail": "Password is required.",
                    "code": "password_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {
                    "detail": "A user with that username already exists.",
                    "code": "username_taken",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if email and User.objects.filter(email=email).exists():
            return Response(
                {
                    "detail": "A user with that email already exists.",
                    "code": "email_taken",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email or "",
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            if is_staff:
                user.is_staff = True
            user.is_active = _as_bool(is_active)
            user.save(update_fields=["is_staff", "is_active"])

            UserBootstrapService.bootstrap_user(
                user,
                language=language,
                timezone_str=timezone,
                scene=None,
                email_config=(
                    UserBootstrapService.build_auto_assign_email_config()
                ),
                prompt_description="User prompt configuration",
                email_description="User email configuration",
                email_alias=username,
            )

            if group_ids:
                groups = Group.objects.filter(id__in=group_ids)
                user.groups.set(groups)

        user.refresh_from_db()
        return Response(_user_payload(user), status=status.HTTP_201_CREATED)


class ManagementUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        user = _user_queryset().filter(pk=pk).first()
        if user is None:
            return Response(
                {"detail": "User not found.", "code": "user_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(_user_payload(user))

    def patch(self, request, pk):
        user = _user_queryset().filter(pk=pk).first()
        if user is None:
            return Response(
                {"detail": "User not found.", "code": "user_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Only superusers may edit superusers: staff accounts can otherwise
        # reset a superuser password (or deactivate the account) and inherit
        # the superuser-only branches elsewhere in the product.
        if user.is_superuser and not request.user.is_superuser:
            return Response(
                {
                    "detail": "You cannot modify a superuser account.",
                    "code": "superuser_protected",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data
        is_self = user.pk == request.user.pk
        user_fields = []

        group_ids = data.get("group_ids", None)
        if group_ids is not None and not _valid_group_ids(group_ids):
            return _bad_request(
                "group_ids must be a list of integers.",
                "invalid_group_ids",
            )

        if "username" in data:
            username = (data.get("username") or "").strip()
            if not username:
                return _bad_request(
                    "Username is required.",
                    "username_required",
                )
            # EmailAlias is derived from the username at bootstrap, so a
            # rename would strand the alias and block reusing the old name.
            if username != user.username:
                return _bad_request(
                    "Username cannot be changed.",
                    "username_immutable",
                )

        if "email" in data:
            email = (data.get("email") or "").strip()
            if (
                email
                and User.objects.filter(email=email)
                .exclude(pk=user.pk)
                .exists()
            ):
                return _bad_request(
                    "A user with that email already exists.",
                    "email_taken",
                )
            if email != (user.email or ""):
                user.email = email
                user_fields.append("email")

        for field in ("first_name", "last_name"):
            if field in data:
                value = (data.get(field) or "").strip()
                if value != getattr(user, field):
                    setattr(user, field, value)
                    user_fields.append(field)

        if "is_staff" in data:
            is_staff = _as_bool(data.get("is_staff"))
            if is_self and not is_staff:
                return _bad_request(
                    "You cannot remove your own admin permission.",
                    "cannot_revoke_own_admin",
                )
            if is_staff != bool(user.is_staff):
                user.is_staff = is_staff
                user_fields.append("is_staff")

        if "is_active" in data:
            is_active = _as_bool(data.get("is_active"))
            if is_self and not is_active:
                return _bad_request(
                    "You cannot deactivate your own account.",
                    "cannot_deactivate_self",
                )
            if is_active != bool(user.is_active):
                user.is_active = is_active
                user_fields.append("is_active")

        password = data.get("password") or ""
        if password:
            user.set_password(password)
            user_fields.append("password")

        with transaction.atomic():
            if user_fields:
                user.save(update_fields=user_fields)

            if "language" in data or "timezone" in data:
                profile_fields = []
                profile, _ = Profile.objects.get_or_create(user=user)
                if "language" in data:
                    language = (
                        (data.get("language") or "").strip()
                        or profile.language
                        or "zh-CN"
                    )
                    if language != profile.language:
                        profile.language = language
                        profile_fields.append("language")
                if "timezone" in data:
                    timezone = (
                        (data.get("timezone") or "").strip()
                        or profile.timezone
                        or "Asia/Shanghai"
                    )
                    if timezone != profile.timezone:
                        profile.timezone = timezone
                        profile_fields.append("timezone")
                if profile_fields:
                    profile.save(update_fields=profile_fields)

            if group_ids is not None:
                user.groups.set(Group.objects.filter(id__in=group_ids))

        user = _user_queryset().get(pk=user.pk)
        return Response(_user_payload(user))


class ManagementGroupListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        page = _safe_int(request.query_params.get("page"), default=1)
        page_size = _safe_int(
            request.query_params.get("page_size"),
            default=20,
        )
        qs = (
            Group.objects.annotate(
                user_count=Count("user", distinct=True),
                permission_count=Count("permissions", distinct=True),
            )
            .order_by("name")
        )
        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        items = [_group_payload(group) for group in qs[start:end]]
        return Response(_paginated_payload(items, total, page, page_size))

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"detail": "Group name is required.", "code": "name_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Group.objects.filter(name=name).exists():
            return Response(
                {
                    "detail": "A group with that name already exists.",
                    "code": "name_taken",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        group = Group.objects.create(name=name)
        return Response(_group_payload(group), status=status.HTTP_201_CREATED)
