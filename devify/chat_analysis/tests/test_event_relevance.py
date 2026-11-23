import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from chat_analysis import execution
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventEvidence,
    EventParticipantEvidence,
)
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
    assert data["viewer_relevance"] == "related"
    assert finished.pk in data["viewer_evidence_message_ids"]
    assert read_event(bob, event)["viewer_relevance"] == "my_todo"
    assert EventParticipantEvidence.objects.filter(
        suggestion__event=event, sender_key="bob", state="open",
    ).count() == 1

    client = APIClient()
    client.force_authenticate(user=alice)
    response = client.get(f"/api/v1/spaces/{space.pk}/events")
    assert response.status_code == 200
    assert response.data["data"]["list"][0]["viewer_relevance"] == "related"

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
