import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventEvidence,
    EventParticipantEvidence,
    EventSuggestion,
)
from chat_analysis.services import create_note
from chat_analysis.tests.test_event_extraction import (
    add_message,
    make_conversation,
    make_job,
    make_space,
    run_job,
)
from chat_domain.models import (
    Conversation,
    ConversationIdentity,
    Message,
    MessageOrigin,
)
from chat_domain.services import merge_messages
from chat_ingestion.models import UploadBatch, UploadItem
from chat_ingestion.parsing import parse_archive
from chat_ingestion.services import archive_path, store_archive
from chat_ingestion.tests.archives import build_archive
from spaces.models import SpaceMembership

pytestmark = pytest.mark.django_db


def named_message(chat, seq, text, name, sender_key=None):
    message = add_message(chat, seq, text, sender=name)
    message.sender_key = sender_key or name.casefold()
    message.save(update_fields=("sender_key",))
    return message


def add_member(space, chat, name, key):
    user = User.objects.create_user(username=name)
    SpaceMembership.objects.create(
        space=space,
        user=user,
        role=SpaceMembership.Role.USER,
    )
    if key:
        ConversationIdentity.objects.create(
            conversation=chat,
            user=user,
            sender_key=key,
        )
    return user


def update(seq, quote, state="open", **fields):
    return {"seq": seq, "quote": quote, "state": state, **fields}


def event_payload(*, updates, source_seqs, **fields):
    return {
        "title": "Annual quote",
        "summary": "The group is preparing the annual quote.",
        "status": "in_progress",
        "sources": [{"seq": seq} for seq in source_seqs],
        "participant_updates": updates,
        **fields,
    }


def read_event(user, event):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(f"/api/v1/events/{event.pk}")
    assert response.status_code == 200
    return response.data["data"]


@pytest.mark.parametrize("scheduled", [False, True])
def test_viewer_labels_follow_individual_evidence_and_completion(
    settings,
    monkeypatch,
    scheduled,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution,
        "request_budget",
        lambda _: (12000, lambda *_: 500),
    )
    owner = User.objects.create_user(username="personal-event-owner")
    space = make_space(owner, "personal-event")
    chat = make_conversation(space, "sales", "Sales")
    alice = add_member(space, chat, "event-alice", "alice")
    bob = add_member(space, chat, "event-bob", "bob")
    carol = add_member(space, chat, "event-carol", "carol")
    observer = add_member(space, chat, "event-observer", None)
    # The person who prepared the import is not any of the assignees.
    chat.self_sender_key = "bob"
    chat.save(update_fields=("self_sender_key",))
    named_message(chat, 1, "Earlier participation", "Alice")
    named_message(chat, 2, "Earlier participation", "Bob")
    named_message(chat, 3, "Earlier participation", "Carol")
    assignment = "Alice, send the quote. Bob, confirm pricing. FYI Carol."
    assigned = named_message(chat, 4, assignment, "Manager")

    def analyze(key, messages, candidates):
        job = make_job(space, owner, chat, messages[-1].ingest_seq, key=key)
        if scheduled:
            boundary = timezone.now().isoformat()
            job.specification.update(
                scheduled_message_scope=True,
                boundary=boundary,
            )
            job.save(update_fields=("specification",))
            AnalysisJobMessage.objects.bulk_create(
                [AnalysisJobMessage(job=job, message=row) for row in messages]
            )
        captured = run_job(job, monkeypatch, candidates, [])
        assert job.state == AnalysisJob.State.READY
        if scheduled:
            assert execution._publish_event_batch(space.pk, boundary) == 1
        return captured[0][1]

    analyze(
        "assignment",
        [assigned],
        [
            event_payload(
                source_seqs=[4],
                updates=[
                    update(
                        4,
                        "Alice, send the quote.",
                        person_seq=4,
                        name="Alice",
                        link="name",
                        action="send the quote",
                    ),
                    update(
                        4,
                        "Bob, confirm pricing.",
                        name="Bob",
                        link="name",
                        action="confirm pricing",
                    ),
                    update(
                        4, "FYI Carol.", "related", name="Carol", link="name"
                    ),
                ],
            ),
        ],
    )
    event = Event.objects.get(space=space)
    for user in (alice, bob):
        data = read_event(user, event)
        assert data["viewer_relevance"] == "my_todo"
        assert data["viewer_evidence_message_ids"] == [assigned.pk]
    assert read_event(carol, event)["viewer_relevance"] == "related"
    assert read_event(observer, event)["viewer_relevance"] == "other"
    assert read_event(owner, event)["viewer_relevance"] == "other"

    original = EventParticipantEvidence.objects.get(
        suggestion__event=event,
        sender_key="alice",
    )
    finished = named_message(
        chat, 5, "I sent the quote. Bob still needs to confirm.", "Alice",
    )
    payload = analyze(
        "completion",
        [finished],
        [
            event_payload(
                source_seqs=[5],
                action="attach",
                event_key=event.event_key,
                updates=[
                    update(
                        5,
                        "I sent the quote.",
                        "done",
                        link="speaker",
                        ref=original.reference,
                    ),
                    update(
                        5, "Bob still needs to confirm.", name="Bob",
                        link="name", action="confirm pricing",
                    ),
                ],
            ),
        ],
    )
    assert original.reference in {
        item["ref"]
        for item in payload["open_events_same_conversation"][0]["open_actions"]
    }
    data = read_event(alice, event)
    assert data["status"] == "in_progress"
    assert data["viewer_relevance"] == "my_todo"
    assert finished.pk in data["viewer_evidence_message_ids"]
    assert read_event(bob, event)["viewer_relevance"] == "my_todo"
    assert EventParticipantEvidence.objects.filter(
        suggestion__event=event, sender_key="bob", state="open",
    ).count() == 1

    client = APIClient()
    client.force_authenticate(user=alice)
    path = f"/api/v1/spaces/{space.pk}/events"
    response = client.get(path)
    assert response.status_code == 200
    assert response.data["data"]["list"][0]["viewer_relevance"] == "my_todo"
    assert "relevance_counts" not in response.data["data"]

    unrelated = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="other",
        title="Different matter",
        content="Not referenced",
        status=Event.Status.OPEN,
        last_activity_at=timezone.now(),
    )
    expected_counts = {"my_todo": 1, "related": 0, "other": 1}
    response = client.get(path, {
        "page_size": 1, "include_relevance_counts": "true",
    })
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 2
    assert response.data["data"]["list"][0]["id"] == unrelated.pk
    assert response.data["data"]["relevance_counts"] == expected_counts

    response = client.get(path, {
        "page_size": 1, "viewer_relevance": "my_todo",
    })
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == event.pk
    assert response.data["data"]["relevance_counts"] == expected_counts
    invalid = client.get(path, {"viewer_relevance": "invalid"})
    assert invalid.status_code == 400

    client.force_authenticate(user=bob)
    response = client.get(path, {
        "viewer_relevance": "my_todo", "status": "in_progress",
    })
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == event.pk
    assert response.data["data"]["relevance_counts"] == {
        "my_todo": 1, "related": 0, "other": 0,
    }

    response = client.get(path, {
        "conversation_id": chat.pk, "include_relevance_counts": "true",
    })
    assert response.status_code == 200
    assert response.data["data"]["relevance_counts"] == {
        "my_todo": 1, "related": 0, "other": 0,
    }

    client.force_authenticate(user=owner)
    detail_path = f"/api/v1/events/{event.pk}"
    response = client.patch(detail_path, {"status": "done"}, format="json")
    assert response.status_code == 200
    for user, label in (
        (alice, "my_todo"), (bob, "my_todo"), (carol, "related"),
        (observer, "other"),
    ):
        detail = read_event(user, event)
        assert detail["viewer_relevance"] == label
        client.force_authenticate(user=user)
        response = client.get(path, {
            "status": "done", "viewer_relevance": label,
        })
        assert response.status_code == 200
        data = response.data["data"]
        assert data["completion_filter_supported"] is True
        assert [row["id"] for row in data["list"]] == [event.pk]
        assert data["list"][0]["viewer_relevance"] == label
        assert data["list"][0]["viewer_evidence_message_ids"] == (
            detail["viewer_evidence_message_ids"]
        )
        assert data["relevance_counts"][label] == 1

    client.force_authenticate(user=owner)
    response = client.patch(detail_path, {"status": "open"}, format="json")
    assert response.status_code == 200
    client.force_authenticate(user=alice)
    response = client.get(path, {
        "status": "unfinished", "viewer_relevance": "my_todo",
    })
    assert response.status_code == 200
    assert [row["id"] for row in response.data["data"]["list"]] == [event.pk]

    duplicate = named_message(
        chat, 6, "I sent the quote. Bob still needs to confirm.", "Alice",
    )
    merge_messages(source=finished, target=duplicate)
    assert (
        duplicate.pk in read_event(alice, event)["viewer_evidence_message_ids"]
    )


def test_ambiguous_people_and_acknowledgments_do_not_create_todos(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    monkeypatch.setattr(
        execution,
        "request_budget",
        lambda _: (12000, lambda *_: 500),
    )
    owner = User.objects.create_user(username="ambiguous-event-owner")
    space = make_space(owner, "ambiguous-event")
    chat = make_conversation(space, "sales", "Sales")
    user = add_member(space, chat, "event-sam", "sam")
    named_message(chat, 1, "Earlier message", "Sam")
    named_message(chat, 2, "Earlier message", "Sam", "another-sam")
    named_message(chat, 3, "Sam, confirm the quote.", "Manager")
    acknowledged = named_message(chat, 4, "收到", "Sam")

    job = make_job(space, owner, chat, 4)
    run_job(
        job,
        monkeypatch,
        [
            event_payload(
                source_seqs=[3, 4],
                updates=[
                    update(
                        3,
                        "Sam, confirm the quote.",
                        person_seq=1,
                        link="name",
                        action="confirm the quote",
                    ),
                    update(
                        4,
                        "I will confirm",
                        person_seq=4,
                        link="speaker",
                        action="confirm the quote",
                    ),
                    update(
                        4,
                        "收到",
                        person_seq=4,
                        link="speaker",
                        action="confirm the quote",
                    ),
                    update(
                        1,
                        "Earlier message",
                        person_seq=1,
                        link="speaker",
                        action="confirm the quote",
                    ),
                ],
            ),
        ],
        [],
    )
    event = Event.objects.get(space=space)
    assert list(
        EventParticipantEvidence.objects.filter(
            suggestion__event=event,
        ).values_list("state", flat=True)
    ) == ["related"]
    data = read_event(user, event)
    assert data["viewer_relevance"] == "related"
    assert data["viewer_evidence_message_ids"] == [acknowledged.pk]


def test_legacy_open_event_keeps_status_without_inventing_an_assignee():
    owner = User.objects.create_user(username="legacy-event-owner")
    space = make_space(owner, "legacy-event")
    chat = make_conversation(space, "sales", "Sales")
    message = named_message(chat, 1, "Bob, send the quote.", "Manager")
    event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="legacy-quote",
        title="Annual quote",
        content="Prepare the quote",
        status="open",
    )
    EventEvidence.objects.create(
        event=event, message=message, created_by=owner
    )

    data = read_event(owner, event)
    assert data["status"] == "open"
    assert data["viewer_relevance"] == "other"
    assert data["viewer_evidence_message_ids"] == []

    message.direction = Message.Direction.OUTGOING
    message.save(update_fields=("direction",))
    batch = UploadBatch.objects.create(
        space=space,
        uploaded_by=owner,
        source_type="wechat",
        source_account_id=message.sender_key,
        idempotency_key="historic",
        status=UploadBatch.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    item = UploadItem.objects.create(batch=batch, path="messages.jsonl")
    MessageOrigin.objects.create(
        message=message,
        upload_item=item,
        locator_key="1",
        parser_version="v1",
    )
    data = read_event(owner, event)
    assert data["status"] == "open"
    assert data["viewer_relevance"] == "related"
    assert data["viewer_evidence_message_ids"] == [message.pk]
    assert not ConversationIdentity.objects.filter(user=owner).exists()

    client = APIClient()
    client.force_authenticate(user=owner)
    path = f"/api/v1/spaces/{space.pk}/events"
    response = client.get(path, {"viewer_relevance": "related"})
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 1
    assert response.data["data"]["list"][0]["id"] == event.pk

    ConversationIdentity.objects.create(
        conversation=chat, user=owner, sender_key=message.sender_key.upper(),
    )
    assert read_event(owner, event)["viewer_relevance"] == "other"
    response = client.get(path, {"viewer_relevance": "related"})
    assert response.status_code == 200
    assert response.data["data"]["pagination"]["total"] == 0
    assert response.data["data"]["relevance_counts"] == {
        "my_todo": 0, "related": 0, "other": 1,
    }


def test_completed_backups_restore_only_their_uploader_identity(
    settings, tmp_path,
):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path)
    owner = User.objects.create_user(username="legacy-backup-owner")
    other = User.objects.create_user(username="legacy-backup-other")
    space = make_space(owner, "legacy-backup")
    batch = UploadBatch.objects.create(
        uploaded_by=owner,
        space=space,
        source_type="wechat",
        source_account_id="local-backup-account",
        idempotency_key="historic",
    )
    store_archive(batch, SimpleUploadedFile("history.zip", build_archive()))
    batch.status = UploadBatch.Status.PROCESSING
    batch.save(update_fields=("status",))
    assert parse_archive(batch).status == UploadBatch.Status.COMPLETED
    conversation = Conversation.objects.get(space=space)
    ConversationIdentity.objects.filter(conversation=conversation).delete()
    conversation.self_sender_key = "shared-field-from-someone-else"
    conversation.save(update_fields=("self_sender_key",))

    rejected = UploadBatch.objects.create(
        uploaded_by=other,
        space=space,
        source_type="wechat",
        idempotency_key="failed",
        status=UploadBatch.Status.FAILED,
    )
    archive_path(rejected).write_bytes(archive_path(batch).read_bytes())
    listing = batch.items.get(path="conversations.jsonl")
    UploadItem.objects.create(
        batch=rejected, path=listing.path, sha256=listing.sha256,
    )
    bad = UploadBatch.objects.create(
        uploaded_by=other,
        space=space,
        source_type="wechat",
        idempotency_key="tampered",
        status=UploadBatch.Status.COMPLETED,
    )
    archive_path(bad).write_bytes(archive_path(batch).read_bytes())
    UploadItem.objects.create(batch=bad, path=listing.path, sha256="0" * 64)

    call_command("backfill_chat_identities", conversation_id=conversation.pk)
    assert not ConversationIdentity.objects.filter(conversation=conversation)
    for _ in range(2):
        call_command(
            "backfill_chat_identities", "--space-id", str(space.pk), "--apply"
        )
    assert list(ConversationIdentity.objects.values_list(
        "conversation_id", "user_id", "sender_key",
    )) == [(conversation.pk, owner.pk, "wx-self")]


def test_quote_whitespace_and_commitment_speaker_are_grounded():
    from chat_analysis.event_relevance import resolve_participant_evidence

    owner = User.objects.create_user(username="grounded-commitment")
    space = make_space(owner, "grounded-commitment")
    chat = make_conversation(space, "sales", "Sales")
    source = named_message(chat, 1, "@Alice\u2005请准备报价", "Bob")
    promise = named_message(chat, 2, "我发给客户", "Alice")
    updates = resolve_participant_evidence(
        [
            update(1, "@Alice 请准备报价", name="Alice",
                   link="name", action="准备报价"),
            update(1, "@Alice 请发送报价", name="Alice",
                   link="name", action="发送报价"),
            update(2, "我发给客户", link="commitment", action="发给客户"),
            update(2, "我发给客户", person_seq=1, link="commitment",
                   action="替别人标记待办"),
        ],
        [source, promise],
        [source, promise],
        ["matter", "matter"],
        execution._message_texts,
        {},
    )
    assert [
        (item["sender_key"], item["state"], item["action"])
        for item in updates
    ] == [("alice", "open", "准备报价"), ("alice", "open", "发给客户")]


@pytest.mark.parametrize(
    ("relay", "event_open", "expected"),
    [
        ("我发给客户", True, {"alice", "bob"}),
        ("我发给客户", False, {"bob"}),
        ("我发给客户了", True, {"bob"}),
        ("我发给客户吗？", True, {"bob"}),
        ("要不要我发给客户", True, {"bob"}),
        ("请" * 280 + "，我发给客户", True, {"bob"}),
    ],
)
def test_named_assignment_can_include_speakers_own_handoff(
    relay, event_open, expected,
):
    from chat_analysis.event_relevance import resolve_participant_evidence

    owner = User.objects.create_user(username="explicit-handoff")
    space = make_space(owner, "explicit-handoff")
    chat = make_conversation(space, "sales", "Sales")
    bob = named_message(chat, 1, "报价出来了", "Bob")
    assignment = named_message(
        chat, 2, f"@Bob\u2005报价帮我上传吧 {relay}", "Alice",
    )
    model_update = update(
        2, "@Bob 报价帮我上传吧", name="Bob",
        link="name", action="上传报价",
    )
    updates = resolve_participant_evidence(
        [model_update], [bob, assignment], [assignment], ["matter"],
        execution._message_texts, {}, recover_handoffs=event_open,
    )
    assert {item["sender_key"] for item in updates} == expected
    assert all(
        item["state"] == "open" and item["message_id"] == assignment.pk
        for item in updates
    )
    if event_open and "alice" in expected:
        # The mentioned recipient does not have to appear in the backup.
        assert [
            item["sender_key"] for item in resolve_participant_evidence(
                [], [assignment], [assignment], ["matter"],
                execution._message_texts, {}, recover_handoffs=True,
            )
        ] == ["alice"]


def test_direct_address_requires_two_distinct_participants(
    settings,
    monkeypatch,
):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="direct-assignment-owner")
    space = make_space(owner, "direct-assignment")
    chat = make_conversation(space, "sales", "Sales")
    chat.kind = Conversation.Kind.DIRECT
    chat.save(update_fields=("kind",))
    user = add_member(space, chat, "direct-assignee", "alice")
    named_message(chat, 1, "Earlier message", "Alice")
    named_message(chat, 2, "Please send the quote.", "Bob")
    payload = event_payload(
        source_seqs=[2],
        updates=[
            update(
                2,
                "Please send the quote.",
                person_seq=1,
                link="direct",
                action="send the quote",
            )
        ],
    )
    captured = run_job(
        make_job(space, owner, chat, 2),
        monkeypatch,
        [payload],
        [],
    )
    assert captured[0][1]["conversation_kind"] == "direct"
    event = Event.objects.get(space=space)
    assert read_event(user, event)["viewer_relevance"] == "my_todo"

    named_message(chat, 3, "Earlier text from a merged export", "Carol")
    run_job(
        make_job(space, owner, chat, 3, key="ambiguous"),
        monkeypatch,
        [payload],
        [],
    )
    assert (
        EventParticipantEvidence.objects.filter(
            suggestion__event__space=space,
        ).count()
        == 1
    )


def test_database_cascades_allow_deletes_by_pre_relevance_workers():
    if connection.vendor != "mysql":
        pytest.skip("Production image rollback uses MariaDB foreign keys.")

    owner = User.objects.create_user(username="legacy-delete-owner")
    space = make_space(owner, "legacy-delete")
    chat = make_conversation(space, "sales", "Sales")
    job = make_job(space, owner, chat, 2)
    note = create_note(
        actor=owner, space=space, note_key="legacy-delete",
        title="Quote", content="Reply to the quote",
    )
    proposal = EventSuggestion.objects.create(
        space=space,
        analysis_job=job,
        note=note,
        event_key="legacy-delete",
        title="Quote",
        summary="Reply to the quote",
        created_by=owner,
    )
    messages = [
        Message.objects.create(
            conversation=chat, message_key=f"m-{seq}", ingest_seq=seq,
        )
        for seq in (1, 2)
    ]
    for message in messages:
        EventParticipantEvidence.objects.create(
            suggestion=proposal, message=message, sender_key="owner",
            state="related",
        )

    # An old Django worker knows neither of the new dependent tables.
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM chat_domain_message WHERE id = %s", [messages[0].pk],
        )
        assert cursor.rowcount == 1
        cursor.execute(
            "SELECT COUNT(*) FROM chat_analysis_eventparticipantevidence "
            "WHERE message_id = %s", [messages[0].pk],
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "DELETE FROM chat_analysis_eventsuggestion WHERE id = %s",
            [proposal.pk],
        )
        assert cursor.rowcount == 1
        cursor.execute(
            "SELECT COUNT(*) FROM chat_analysis_eventparticipantevidence "
            "WHERE suggestion_id = %s", [proposal.pk],
        )
        assert cursor.fetchone()[0] == 0
