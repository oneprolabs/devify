"""
Tests for connecting several mailboxes alongside the virtual address.

The two channels are parallel: a user can receive on their alias and on
any mailbox they connect, at the same time.
"""

import pytest
from django.conf import settings as django_settings

from threadline.models import EmailAlias, EmailMailbox, Settings


pytestmark = [pytest.mark.integration, pytest.mark.django_db]

LIST_URL = "/api/v1/settings/mailboxes"


def make_mailbox(user, host="imap.example.com", username="a@example.com"):
    return EmailMailbox.objects.create(
        user=user,
        name=username,
        imap_host=host,
        imap_port=993,
        username=username,
        password="secret",
    )


class TestMailboxModel:
    def test_the_password_is_not_stored_in_plain_text(self, django_user_model):
        from django.db import connection

        user = django_user_model.objects.create_user("m1", password="x")
        mailbox = make_mailbox(user)

        # The ORM decrypts on the way out, so the column has to be read
        # directly to see what actually sits on disk.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT password FROM threadline_emailmailbox WHERE id = %s",
                [mailbox.pk],
            )
            stored = cursor.fetchone()[0]

        assert EmailMailbox.objects.get(pk=mailbox.pk).password == "secret"
        assert stored != "secret"
        assert stored.startswith("fernet:")

    def test_it_renders_the_config_the_fetch_pipeline_expects(
        self, django_user_model
    ):
        user = django_user_model.objects.create_user("m2", password="x")
        config = make_mailbox(user).to_email_config()

        assert config["imap_config"]["imap_host"] == "imap.example.com"
        assert config["imap_config"]["password"] == "secret"
        assert config["imap_config"]["imap_ssl_port"] == 993

    def test_the_same_mailbox_cannot_be_added_twice(self, django_user_model):
        from django.db import IntegrityError, transaction

        user = django_user_model.objects.create_user("m3", password="x")
        make_mailbox(user)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_mailbox(user)

    def test_two_users_may_connect_the_same_address(self, django_user_model):
        first = django_user_model.objects.create_user("m4", password="x")
        second = django_user_model.objects.create_user("m5", password="x")

        make_mailbox(first)
        make_mailbox(second)

        assert EmailMailbox.objects.filter(user=first).count() == 1
        assert EmailMailbox.objects.filter(user=second).count() == 1


class TestMailboxAPI:
    def test_requires_authentication(self, api_client):
        assert api_client.get(LIST_URL).status_code in (401, 403)

    def test_mailboxes_are_scoped_to_their_owner(
        self, api_client, django_user_model
    ):
        mine = django_user_model.objects.create_user("m6", password="x")
        theirs = django_user_model.objects.create_user("m7", password="x")
        make_mailbox(mine)
        make_mailbox(theirs)
        api_client.force_authenticate(user=mine)

        response = api_client.get(LIST_URL)

        assert len(response.data["data"]["mailboxes"]) == 1

    def test_a_mailbox_can_be_connected(self, api_client, django_user_model):
        user = django_user_model.objects.create_user("m8", password="x")
        api_client.force_authenticate(user=user)

        response = api_client.post(
            LIST_URL,
            {
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "username": "a@example.com",
                "password": "secret",
            },
            format="json",
        )

        assert response.status_code == 201
        assert EmailMailbox.objects.filter(user=user).count() == 1

    def test_the_password_never_comes_back(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("m9", password="x")
        make_mailbox(user)
        api_client.force_authenticate(user=user)

        row = api_client.get(LIST_URL).data["data"]["mailboxes"][0]

        assert "password" not in row
        assert row["has_password"] is True

    def test_a_new_mailbox_needs_a_password(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("m10", password="x")
        api_client.force_authenticate(user=user)

        response = api_client.post(
            LIST_URL,
            {"imap_host": "imap.example.com", "username": "a@example.com"},
            format="json",
        )

        assert response.status_code == 400

    def test_editing_without_a_password_keeps_the_stored_one(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("m11", password="x")
        mailbox = make_mailbox(user)
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{mailbox.uuid}", {"folder": "Archive"}, format="json"
        )
        mailbox.refresh_from_db()

        assert mailbox.folder == "Archive"
        assert mailbox.password == "secret"

    def test_connecting_a_duplicate_is_refused(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("m12", password="x")
        make_mailbox(user)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            LIST_URL,
            {
                "imap_host": "imap.example.com",
                "username": "a@example.com",
                "password": "secret",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_the_cap_is_enforced(
        self, api_client, django_user_model, settings
    ):
        settings.MAX_USER_MAILBOXES = 2
        user = django_user_model.objects.create_user("m13", password="x")
        make_mailbox(user, username="a@example.com")
        make_mailbox(user, username="b@example.com")
        api_client.force_authenticate(user=user)

        response = api_client.post(
            LIST_URL,
            {
                "imap_host": "imap.example.com",
                "username": "c@example.com",
                "password": "secret",
            },
            format="json",
        )

        assert response.status_code == 400
        assert EmailMailbox.objects.filter(user=user).count() == 2

    def test_a_mailbox_can_be_disconnected(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("m14", password="x")
        mailbox = make_mailbox(user)
        api_client.force_authenticate(user=user)

        api_client.delete(f"{LIST_URL}/{mailbox.uuid}")

        assert not EmailMailbox.objects.filter(pk=mailbox.pk).exists()

    def test_another_users_mailbox_is_not_found(
        self, api_client, django_user_model
    ):
        mine = django_user_model.objects.create_user("m15", password="x")
        theirs = django_user_model.objects.create_user("m16", password="x")
        mailbox = make_mailbox(theirs)
        api_client.force_authenticate(user=mine)

        assert (
            api_client.get(f"{LIST_URL}/{mailbox.uuid}").status_code == 404
        )


class TestChannelsRunInParallel:
    def test_a_user_can_hold_an_alias_and_a_mailbox_at_once(
        self, django_user_model
    ):
        user = django_user_model.objects.create_user("m17", password="x")
        EmailAlias.objects.create(user=user, alias="m17")
        make_mailbox(user)

        assert EmailAlias.objects.filter(user=user, is_active=True).exists()
        assert EmailMailbox.objects.filter(user=user, enabled=True).exists()

    def test_the_fetch_loop_picks_up_every_enabled_mailbox(
        self, django_user_model
    ):
        user = django_user_model.objects.create_user("m18", password="x")
        make_mailbox(user, username="a@example.com")
        make_mailbox(user, username="b@example.com")
        disabled = make_mailbox(user, username="c@example.com")
        disabled.enabled = False
        disabled.save(update_fields=["enabled"])

        selected = EmailMailbox.objects.filter(
            enabled=True, user__is_active=True, user=user
        )

        assert selected.count() == 2

    def test_account_settings_no_longer_reach_a_mailbox(
        self, django_user_model
    ):
        # Filters used to have an account-wide layer under the per-mailbox
        # one. It served nobody: the virtual address arrives over SMTP and
        # that path reads no filter config, so all the layer did was put
        # half of one mailbox's settings on another screen.
        user = django_user_model.objects.create_user("m19", password="x")
        Settings.objects.create(
            user=user,
            key="email_config",
            value={"filter_config": {"max_age_days": 7}},
            is_active=True,
        )
        mailbox = make_mailbox(user)

        config = mailbox.to_email_config()["filter_config"]

        assert "max_age_days" not in config

    def test_the_alias_channel_no_longer_depends_on_a_mode_flag(
        self, django_user_model
    ):
        # Previously only users whose settings said mode=auto_assign were
        # routed inbound mail; the alias alone is enough now.
        user = django_user_model.objects.create_user("m20", password="x")
        EmailAlias.objects.create(user=user, alias="m20")
        Settings.objects.create(
            user=user,
            key="email_config",
            value={"mode": "custom_imap"},
            is_active=True,
        )

        domain = django_settings.AUTO_ASSIGN_EMAIL_DOMAIN
        assert EmailAlias.find_user_by_email(f"m20@{domain}") == user


class TestConnectionCheck:
    """
    The validator reads `imap_config` out of the config it is handed, so
    the endpoint has to keep the settings nested. Passing the inner dict
    made every check fail with "imap_host is missing".
    """

    VALIDATE = (
        "threadline.views.email_mailbox."
        "EmailConfigManager.validate_imap_connection"
    )

    def test_a_draft_is_checked_with_a_nested_config(
        self, api_client, django_user_model
    ):
        from unittest.mock import patch

        user = django_user_model.objects.create_user("m21", password="x")
        api_client.force_authenticate(user=user)

        with patch(self.VALIDATE, return_value=(True, "")) as validate:
            response = api_client.post(
                f"{LIST_URL}/test",
                {
                    "imap_host": "imap.example.com",
                    "imap_port": 993,
                    "username": "a@example.com",
                    "password": "secret",
                },
                format="json",
            )

        config = validate.call_args.args[0]
        assert response.status_code == 200
        assert config["imap_config"]["imap_host"] == "imap.example.com"
        assert config["imap_config"]["password"] == "secret"

    def test_a_stored_mailbox_is_checked_with_its_own_settings(
        self, api_client, django_user_model
    ):
        from unittest.mock import patch

        user = django_user_model.objects.create_user("m22", password="x")
        mailbox = make_mailbox(user)
        api_client.force_authenticate(user=user)

        with patch(self.VALIDATE, return_value=(True, "")) as validate:
            api_client.post(f"{LIST_URL}/{mailbox.uuid}/test")

        config = validate.call_args.args[0]
        assert config["imap_config"]["imap_host"] == "imap.example.com"
        assert config["imap_config"]["password"] == "secret"

    def test_editing_reuses_the_stored_password(
        self, api_client, django_user_model
    ):
        from unittest.mock import patch

        user = django_user_model.objects.create_user("m23", password="x")
        mailbox = make_mailbox(user)
        api_client.force_authenticate(user=user)

        with patch(self.VALIDATE, return_value=(True, "")) as validate:
            api_client.post(
                f"{LIST_URL}/test",
                {
                    "uuid": str(mailbox.uuid),
                    "imap_host": "imap.example.com",
                    "username": "a@example.com",
                    "password": "",
                },
                format="json",
            )

        config = validate.call_args.args[0]
        assert config["imap_config"]["password"] == "secret"

    def test_a_failure_is_reported_with_its_reason(
        self, api_client, django_user_model
    ):
        from unittest.mock import patch

        user = django_user_model.objects.create_user("m24", password="x")
        api_client.force_authenticate(user=user)

        with patch(self.VALIDATE, return_value=(False, "auth failed")):
            response = api_client.post(
                f"{LIST_URL}/test",
                {
                    "imap_host": "imap.example.com",
                    "username": "a@example.com",
                    "password": "wrong",
                },
                format="json",
            )

        assert response.status_code == 400
        assert "auth failed" in response.data["message"]

    def test_another_users_mailbox_cannot_be_checked(
        self, api_client, django_user_model
    ):
        mine = django_user_model.objects.create_user("m25", password="x")
        theirs = django_user_model.objects.create_user("m26", password="x")
        mailbox = make_mailbox(theirs)
        api_client.force_authenticate(user=mine)

        response = api_client.post(f"{LIST_URL}/{mailbox.uuid}/test")

        assert response.status_code == 404


class TestPerMailboxFilters:
    """
    Filters belong to the mailbox that uses them, and to nothing else.

    They briefly had an account-wide layer underneath, on the theory that
    the virtual address needed somewhere to be configured. It did not: the
    virtual address arrives over SMTP, and that path never reads a filter
    config. The layer only meant half of one mailbox's settings lived on a
    different screen, so an empty field now means "do not filter on this"
    rather than "inherit from somewhere else".
    """

    def test_a_mailbox_uses_its_own_filters(self, django_user_model):
        user = django_user_model.objects.create_user("f2", password="x")
        mailbox = make_mailbox(user)
        mailbox.filters = ["行程单"]
        mailbox.max_age_days = 3
        mailbox.save(update_fields=["filters", "max_age_days"])

        config = mailbox.to_email_config()["filter_config"]

        assert config["filters"] == ["行程单"]
        assert config["max_age_days"] == 3

    def test_an_empty_filter_means_no_filter(self, django_user_model):
        user = django_user_model.objects.create_user("f1", password="x")
        mailbox = make_mailbox(user)

        config = mailbox.to_email_config()["filter_config"]

        assert config["filters"] == []
        assert config["exclude_patterns"] == []
        # Absent rather than empty: no age limit at all, which the fetch
        # reads differently from a limit of zero days.
        assert "max_age_days" not in config

    def test_one_mailbox_does_not_affect_another(self, django_user_model):
        # The whole point of moving these onto the mailbox: a work inbox
        # and a personal one want different rules.
        user = django_user_model.objects.create_user("f3", password="x")
        work = make_mailbox(user, username="work@example.com")
        personal = make_mailbox(user, username="personal@example.com")
        work.filters = ["发票"]
        work.save(update_fields=["filters"])

        assert work.to_email_config()["filter_config"]["filters"] == ["发票"]
        assert personal.to_email_config()["filter_config"]["filters"] == []

    def test_zero_days_is_a_real_limit_not_an_absence(
        self, django_user_model
    ):
        user = django_user_model.objects.create_user("f4", password="x")
        mailbox = make_mailbox(user)
        mailbox.max_age_days = 0
        mailbox.save(update_fields=["max_age_days"])

        config = mailbox.to_email_config()["filter_config"]

        assert config["max_age_days"] == 0

    def test_blank_and_duplicate_entries_are_cleaned(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("f5", password="x")
        mailbox = make_mailbox(user)
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            f"{LIST_URL}/{mailbox.uuid}",
            {"filters": ["发票", "  ", "发票", "行程单"]},
            format="json",
        )

        assert response.data["data"]["filters"] == ["发票", "行程单"]

    def test_clearing_a_filter_leaves_the_mailbox_unfiltered(
        self, api_client, django_user_model
    ):
        user = django_user_model.objects.create_user("f6", password="x")
        mailbox = make_mailbox(user)
        mailbox.max_age_days = 3
        mailbox.save(update_fields=["max_age_days"])
        api_client.force_authenticate(user=user)

        api_client.patch(
            f"{LIST_URL}/{mailbox.uuid}", {"max_age_days": None}, format="json"
        )
        mailbox.refresh_from_db()

        assert "max_age_days" not in mailbox.to_email_config()["filter_config"]