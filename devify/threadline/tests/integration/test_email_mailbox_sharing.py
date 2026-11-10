"""A mailbox is one globally unique source shared to one or more spaces."""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from spaces.models import Space, SpaceMembership
from threadline.models import (
    EmailAttachment,
    EmailMailbox,
    EmailMailboxShare,
    EmailMessage,
    compute_mailbox_source_key,
)
from threadline.services.space_email import email_ai_allowed
from threadline.tasks.email_fetch import (
    _queue_merge_for_saved_email,
    fetch_user_imap_emails,
)
from threadline.tasks.email_merge import process_email_merge
from threadline.utils.email.service import EmailSaveService

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_team(owner, slug="sharing-team"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def make_mailbox(owner, space, username="sales@example.com", host=None):
    return EmailMailbox.objects.create(
        user=owner,
        created_by=owner,
        space=space,
        name=username,
        imap_host=host or "imap.example.com",
        imap_port=993,
        username=username,
        password="secret",
    )


def email_data(message_id="<sharing-1@example.com>"):
    return {
        "message_id": message_id,
        "subject": "Shared inbox",
        "sender": "a@example.com",
        "recipients": "sales@example.com",
        "received_at": timezone.now(),
        "text_content": "hello",
        "html_content": "",
        "metadata": {},
    }


def add_owner_share(mailbox):
    share, _ = EmailMailboxShare.objects.get_or_create(
        mailbox=mailbox,
        space=mailbox.space,
        defaults={"permission": EmailMailboxShare.Permission.MANAGE},
    )
    return share


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_a_shared_mailbox_stores_one_message_visible_in_both_spaces():
    owner = User.objects.create_user(username="sharing-owner")
    team = make_team(owner)
    personal = Space.objects.get(personal_owner=owner)
    mailbox = make_mailbox(owner, team)
    add_owner_share(mailbox)
    EmailMailboxShare.objects.create(
        mailbox=mailbox,
        space=personal,
        permission=EmailMailboxShare.Permission.READ,
    )

    service = EmailSaveService()
    first = service.save_email(owner.id, email_data(), mailbox=mailbox)
    duplicate = service.save_email(owner.id, email_data(), mailbox=mailbox)

    assert first is not None
    assert duplicate is None
    message = EmailMessage.objects.get(message_id="<sharing-1@example.com>")
    assert message.mailbox_id == mailbox.pk
    assert message.space_id == team.pk
    assert (
        EmailMessage.objects.filter(
            message_id=message.message_id
        ).count()
        == 1
    )

    client = client_for(owner)
    for space in (team, personal):
        response = client.get(
            reverse("space-email-list", kwargs={"space_id": space.pk})
        )
        assert response.status_code == 200
        assert len(response.data["data"]["list"]) == 1


def test_a_team_member_reads_shared_mail_but_an_outsider_does_not():
    owner = User.objects.create_user(username="sharing-owner-2")
    member = User.objects.create_user(username="sharing-member")
    outsider = User.objects.create_user(username="sharing-outsider")
    team = make_team(owner, slug="sharing-team-2")
    SpaceMembership.objects.create(
        space=team, user=member, role=SpaceMembership.Role.USER
    )
    mailbox = make_mailbox(owner, team, username="team@example.com")
    add_owner_share(mailbox)
    EmailSaveService().save_email(owner.id, email_data(), mailbox=mailbox)

    team_url = reverse("space-email-list", kwargs={"space_id": team.pk})
    member_response = client_for(member).get(team_url)
    outsider_response = client_for(outsider).get(team_url)

    assert member_response.status_code == 200
    assert len(member_response.data["data"]["list"]) == 1
    assert outsider_response.status_code == 404


def test_team_mail_skips_merge_and_ai_but_personal_mail_keeps_them():
    owner = User.objects.create_user(username="sharing-ai-owner")
    team = make_team(owner, slug="sharing-ai-team")
    personal = Space.objects.get(personal_owner=owner)
    team_mailbox = make_mailbox(owner, team, username="team-ai@example.com")
    personal_mailbox = make_mailbox(
        owner, personal, username="personal-ai@example.com"
    )
    add_owner_share(team_mailbox)
    add_owner_share(personal_mailbox)

    service = EmailSaveService()
    team_message = service.save_email(
        owner.id, email_data("<team-ai@example.com>"), mailbox=team_mailbox
    )
    personal_message = service.save_email(
        owner.id,
        email_data("<personal-ai@example.com>"),
        mailbox=personal_mailbox,
    )

    assert email_ai_allowed(team_message) is False
    assert email_ai_allowed(personal_message) is True

    with patch(
        "threadline.tasks.email_fetch.process_email_merge.delay"
    ) as delay:
        _queue_merge_for_saved_email(team_message)
        delay.assert_not_called()

    with patch(
        "threadline.tasks.email_fetch.is_processing_paused",
        return_value=False,
    ):
        with patch(
            "threadline.tasks.email_fetch.process_email_merge.delay"
        ) as delay:
            _queue_merge_for_saved_email(personal_message)
            delay.assert_called_once_with(str(personal_message.id))


def test_creating_a_space_source_creates_the_owner_share():
    owner = User.objects.create_user(username="sharing-create-owner")
    team = make_team(owner, slug="sharing-create-team")

    response = client_for(owner).post(
        reverse("space-email-sources", kwargs={"space_id": team.pk}),
        {
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "username": "new-source@example.com",
            "password": "secret",
        },
        format="json",
    )

    assert response.status_code == 201
    mailbox = EmailMailbox.objects.get(username="new-source@example.com")
    assert mailbox.space_id == team.pk
    assert mailbox.created_by_id == owner.pk
    assert mailbox.source_key == compute_mailbox_source_key(
        "imap.example.com", 993, "new-source@example.com", "INBOX", True
    )
    share = EmailMailboxShare.objects.get(mailbox=mailbox, space=team)
    assert share.permission == EmailMailboxShare.Permission.MANAGE


def test_a_duplicate_source_returns_conflict_instead_of_a_second_row():
    owner = User.objects.create_user(username="sharing-dup-owner")
    team = make_team(owner, slug="sharing-dup-team")
    mailbox = make_mailbox(owner, team, username="dup@example.com")
    add_owner_share(mailbox)

    response = client_for(owner).post(
        reverse("space-email-sources", kwargs={"space_id": team.pk}),
        {
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "username": "dup@example.com",
            "password": "secret",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["data"]["mailbox_uuid"] == str(mailbox.uuid)
    assert EmailMailbox.objects.filter(username="dup@example.com").count() == 1


def test_a_source_can_be_shared_and_transferred_between_spaces():
    owner = User.objects.create_user(username="sharing-transfer-owner")
    team = make_team(owner, slug="sharing-transfer-team")
    personal = Space.objects.get(personal_owner=owner)
    mailbox = make_mailbox(owner, team, username="transfer@example.com")
    add_owner_share(mailbox)
    client = client_for(owner)

    share_response = client.post(
        reverse(
            "space-email-source-shares",
            kwargs={"space_id": team.pk, "mailbox_uuid": mailbox.uuid},
        ),
        {"space_id": personal.pk, "permission": "read"},
        format="json",
    )
    assert share_response.status_code == 201
    assert (
        EmailMailboxShare.objects.get(
            mailbox=mailbox, space=personal
        ).permission
        == EmailMailboxShare.Permission.READ
    )

    transfer_response = client.post(
        reverse(
            "space-email-source-transfer",
            kwargs={"space_id": team.pk, "mailbox_uuid": mailbox.uuid},
        ),
        {"space_id": personal.pk},
        format="json",
    )
    assert transfer_response.status_code == 200
    mailbox.refresh_from_db()
    assert mailbox.space_id == personal.pk
    assert (
        EmailMailboxShare.objects.get(
            mailbox=mailbox, space=personal
        ).permission
        == EmailMailboxShare.Permission.MANAGE
    )
    assert (
        EmailMailboxShare.objects.get(mailbox=mailbox, space=team).permission
        == EmailMailboxShare.Permission.READ
    )


def test_the_same_message_id_from_two_mailboxes_is_stored_once_per_source():
    owner = User.objects.create_user(username="sharing-dedup-owner")
    team = make_team(owner, slug="sharing-dedup-team")
    personal = Space.objects.get(personal_owner=owner)
    team_mailbox = make_mailbox(owner, team, username="dedup-a@example.com")
    personal_mailbox = make_mailbox(
        owner, personal, username="dedup-b@example.com"
    )
    add_owner_share(team_mailbox)
    add_owner_share(personal_mailbox)
    service = EmailSaveService()

    service.save_email(
        owner.id, email_data("<same@example.com>"), mailbox=team_mailbox
    )
    service.save_email(
        owner.id, email_data("<same@example.com>"), mailbox=personal_mailbox
    )

    assert EmailMessage.objects.filter(
        message_id="<same@example.com>"
    ).count() == 2


def test_a_legacy_message_without_a_mailbox_stays_readable_in_its_space():
    owner = User.objects.create_user(username="sharing-legacy-owner")
    team = make_team(owner, slug="sharing-legacy-team")
    EmailMessage.objects.create(
        user=owner,
        space=team,
        message_id="<legacy@example.com>",
        subject="Legacy",
        sender="a@example.com",
        recipients="b@example.com",
        received_at=timezone.now(),
    )

    response = client_for(owner).get(
        reverse("space-email-list", kwargs={"space_id": team.pk})
    )

    assert response.status_code == 200
    assert len(response.data["data"]["list"]) == 1


def test_the_personal_mailbox_api_does_not_expose_team_owned_sources():
    owner = User.objects.create_user(username="sharing-settings-owner")
    team = make_team(owner, slug="sharing-settings-team")
    personal = Space.objects.get(personal_owner=owner)
    team_mailbox = make_mailbox(
        owner, team, username="team-settings@example.com"
    )
    personal_mailbox = make_mailbox(
        owner, personal, username="mine-settings@example.com"
    )
    add_owner_share(team_mailbox)
    add_owner_share(personal_mailbox)
    client = client_for(owner)

    listing = client.get(reverse("mailboxes-list"))
    usernames = [m["username"] for m in listing.data["data"]["mailboxes"]]
    detail = client.get(
        reverse("mailboxes-detail", kwargs={"uuid": team_mailbox.uuid})
    )

    assert listing.status_code == 200
    assert usernames == ["mine-settings@example.com"]
    assert detail.status_code == 404


def test_the_source_key_follows_the_imap_configuration():
    owner = User.objects.create_user(username="sharing-key-owner")
    team = make_team(owner, slug="sharing-key-team")
    mailbox = make_mailbox(owner, team, username="key@example.com")
    before = mailbox.source_key

    mailbox.folder = "Archive"
    mailbox.save()

    assert mailbox.source_key != before
    assert mailbox.source_key == compute_mailbox_source_key(
        "imap.example.com", 993, "key@example.com", "Archive", True
    )


def test_team_ai_can_be_enabled_by_setting(settings):
    owner = User.objects.create_user(username="sharing-ai-flag-owner")
    team = make_team(owner, slug="sharing-ai-flag-team")
    mailbox = make_mailbox(owner, team, username="ai-flag@example.com")
    add_owner_share(mailbox)
    message = EmailSaveService().save_email(
        owner.id,
        email_data("<ai-flag@example.com>"),
        mailbox=mailbox,
    )

    settings.EMAIL_TEAM_AI_ENABLED = True

    assert email_ai_allowed(message) is True


def test_message_with_mailbox_but_no_space_uses_the_mailbox_space():
    owner = User.objects.create_user(username="sharing-fallback-owner")
    team = make_team(owner, slug="sharing-fallback-team")
    mailbox = make_mailbox(owner, team, username="fallback@example.com")
    add_owner_share(mailbox)

    message = EmailMessage.objects.create(
        user=owner,
        mailbox=mailbox,
        message_id="<fallback@example.com>",
        subject="Fallback",
        sender="a@example.com",
        recipients="b@example.com",
        received_at=timezone.now(),
    )

    assert message.space_id == team.pk


def test_attachment_inherits_the_team_space():
    owner = User.objects.create_user(username="sharing-attachment-owner")
    team = make_team(owner, slug="sharing-attachment-team")
    mailbox = make_mailbox(owner, team, username="attachment@example.com")
    add_owner_share(mailbox)
    message = EmailMessage.objects.create(
        user=owner,
        mailbox=mailbox,
        space=team,
        message_id="<attachment@example.com>",
        subject="Attachment",
        sender="a@example.com",
        recipients="b@example.com",
        received_at=timezone.now(),
    )

    attachment = EmailAttachment.objects.create(
        user=owner,
        email_message=message,
        filename="quote.pdf",
        safe_filename="quote.pdf",
        content_type="application/pdf",
        file_size=10,
        file_path="/tmp/quote.pdf",
    )

    assert attachment.space_id == team.pk


@patch(
    "agentcore_task.adapters.django.services.lock.release_task_lock",
    return_value=True,
)
@patch(
    "agentcore_task.adapters.django.services.lock.acquire_task_lock",
    return_value=True,
)
@patch(
    "agentcore_task.adapters.django.services.lock.is_task_locked",
    return_value=False,
)
@patch("threadline.tasks.email_merge.process_email_workflow.delay")
def test_process_email_merge_skips_team_space(
    mock_delay,
    mock_is_locked,
    mock_acquire_lock,
    mock_release_lock,
):
    owner = User.objects.create_user(username="sharing-merge-owner")
    team = make_team(owner, slug="sharing-merge-team")
    mailbox = make_mailbox(owner, team, username="merge-team@example.com")
    add_owner_share(mailbox)
    message = EmailSaveService().save_email(
        owner.id,
        email_data("<merge-team@example.com>"),
        mailbox=mailbox,
    )

    result = process_email_merge(str(message.id))

    assert result == "team_ai_disabled"
    mock_delay.assert_not_called()


@patch(
    "agentcore_task.adapters.django.services.lock.release_task_lock",
    return_value=True,
)
@patch(
    "agentcore_task.adapters.django.services.lock.acquire_task_lock",
    return_value=True,
)
@patch(
    "agentcore_task.adapters.django.services.lock.is_task_locked",
    return_value=False,
)
@patch("threadline.tasks.email_fetch.EmailSaveService")
@patch("threadline.tasks.email_fetch.EmailProcessor")
def test_fetch_user_imap_emails_passes_the_mailbox_to_save(
    mock_processor_class,
    mock_save_service_class,
    mock_is_locked,
    mock_acquire_lock,
    mock_release_lock,
):
    owner = User.objects.create_user(username="sharing-fetch-owner")
    team = make_team(owner, slug="sharing-fetch-team")
    mailbox = make_mailbox(owner, team, username="fetch-pass@example.com")
    add_owner_share(mailbox)
    email = email_data("<fetch-pass@example.com>")

    processor = Mock()
    processor.process_emails.return_value = [email]
    mock_processor_class.return_value = processor
    save_service = Mock()
    save_service.save_email.return_value = None
    mock_save_service_class.return_value = save_service

    result = fetch_user_imap_emails(
        owner.id,
        {
            "imap_config": {
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "username": "fetch-pass@example.com",
                "folder": "INBOX",
            }
        },
        mailbox=mailbox,
    )

    save_service.save_email.assert_called_once_with(
        owner.id, email, mailbox=mailbox
    )
    assert result["status"] == "completed"
