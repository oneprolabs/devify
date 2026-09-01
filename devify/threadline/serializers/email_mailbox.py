"""Serializers for user-connected mailboxes."""

from django.conf import settings as django_settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from threadline.models import EmailMailbox


class EmailMailboxSerializer(serializers.ModelSerializer):
    """
    A connected mailbox and its health.

    The password is write-only: it goes in, it never comes back out.
    """

    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    has_password = serializers.SerializerMethodField()
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = EmailMailbox
        fields = [
            "uuid",
            "name",
            "display_name",
            "imap_host",
            "imap_port",
            "use_ssl",
            "username",
            "password",
            "has_password",
            "folder",
            "delete_after_fetch",
            "invoice_only",
            "enabled",
            "last_fetched_at",
            "last_success_at",
            "last_error",
            "consecutive_failures",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uuid",
            "display_name",
            "has_password",
            "last_fetched_at",
            "last_success_at",
            "last_error",
            "consecutive_failures",
            "created_at",
            "updated_at",
        ]

    def get_has_password(self, obj) -> bool:
        return bool(obj.password)

    def validate_imap_host(self, value):
        host = str(value or "").strip()
        if not host:
            raise serializers.ValidationError(_("IMAP host is required."))
        return host

    def validate_username(self, value):
        username = str(value or "").strip()
        if not username:
            raise serializers.ValidationError(_("Username is required."))
        return username

    def validate(self, attrs):
        user = self.context["request"].user

        # A new mailbox needs credentials; an edit may leave them alone.
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": _("A password is required.")}
            )

        host = attrs.get("imap_host") or getattr(
            self.instance, "imap_host", ""
        )
        username = attrs.get("username") or getattr(
            self.instance, "username", ""
        )
        duplicate = EmailMailbox.objects.filter(
            user=user, imap_host=host, username=username
        )
        if self.instance is not None:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                _("That mailbox is already connected.")
            )

        if self.instance is None:
            limit = getattr(django_settings, "MAX_USER_MAILBOXES", 5)
            if EmailMailbox.objects.filter(user=user).count() >= limit:
                raise serializers.ValidationError(
                    _("You can connect at most %(limit)d mailboxes.")
                    % {"limit": limit}
                )

        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # An empty password means "leave the stored one alone", so an edit
        # of the folder does not silently wipe the credentials.
        if not validated_data.get("password"):
            validated_data.pop("password", None)
        return super().update(instance, validated_data)
