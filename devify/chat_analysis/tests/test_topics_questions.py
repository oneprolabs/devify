from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from chat_analysis.models import (
    Event,
    EventNote,
    EventTag,
    EventTagAssignment,
    Note,
    NoteEvidence,
)
from chat_analysis.topic_services import answer_question, question_context
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = pytest.mark.django_db


def make_space(owner, slug):
    space = Space.objects.create(name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner)
    SpaceMembership.objects.create(space=space, user=owner, role=SpaceMembership.Role.OWNER, status=SpaceMembership.Status.ACTIVE)
    return space


def test_topic_subscriptions_are_crud_and_space_scoped():
    owner = User.objects.create_user(username="topic-owner")
    other = User.objects.create_user(username="topic-other")
    space = make_space(owner, "topic-team")
    other_space = make_space(other, "topic-other-team")
    client = APIClient()
    client.force_authenticate(user=owner)

    created = client.post(f"/api/v1/spaces/{space.pk}/topics", {"title": "客户风险", "instruction": "只总结未完成的客户风险", "filters": {"keywords": ["风险"]}}, format="json")
    assert created.status_code == 201
    topic_id = created.data["data"]["id"]
    assert client.get(f"/api/v1/spaces/{space.pk}/topics").data["data"][0]["title"] == "客户风险"
    assert client.patch(f"/api/v1/topics/{topic_id}", {"enabled": False}, format="json").data["data"]["enabled"] is False
    assert client.delete(f"/api/v1/topics/{topic_id}").status_code == 204
    assert client.get(f"/api/v1/spaces/{other_space.pk}/topics").status_code == 404


def test_topic_filters_reject_unknown_keys():
    owner = User.objects.create_user(username="topic-validation")
    space = make_space(owner, "topic-validation-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{space.pk}/topics", {"title": "bad", "instruction": "bad", "filters": {"sql": "drop"}}, format="json")
    assert response.status_code == 400


@patch("chat_analysis.api_views.dispatch_question_answer")
@patch("chat_analysis.api_views.transaction.on_commit", side_effect=lambda callback: callback())
def test_question_is_queued_and_scoped(on_commit, dispatch):
    owner = User.objects.create_user(username="question-owner")
    space = make_space(owner, "question-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{space.pk}/questions", {"question": "当前风险是什么", "tag_keys": ["risk"]}, format="json")
    assert response.status_code == 202
    assert response.data["data"]["status"] == "queued"
    dispatch.assert_called_once()
    assert response.data["data"]["scope"] == {"tag_keys": ["risk"]}


def test_question_requires_question_text():
    owner = User.objects.create_user(username="question-validation")
    space = make_space(owner, "question-validation-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    assert client.post(f"/api/v1/spaces/{space.pk}/questions", {"question": "  "}, format="json").status_code == 400


def test_event_tags_are_scoped_and_returned_on_events():
    owner = User.objects.create_user(username="tag-owner")
    other = User.objects.create_user(username="tag-other")
    space = make_space(owner, "tag-team")
    other_space = make_space(other, "tag-other-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    event = client.post(f"/api/v1/spaces/{space.pk}/events", {"event_key": "tagged", "title": "Tagged", "content": "Content", "status": "open"}, format="json").data["data"]
    created = client.post(f"/api/v1/spaces/{space.pk}/tags", {"label": "客户风险"}, format="json")
    assert created.status_code == 201
    tag = created.data["data"]
    assigned = client.post(f"/api/v1/events/{event['id']}/tags", {"tag_id": tag["id"]}, format="json")
    assert assigned.status_code == 201
    detail = client.get(f"/api/v1/events/{event['id']}")
    assert detail.data["data"]["tags"][0]["label"] == "客户风险"
    filtered = client.get(f"/api/v1/spaces/{space.pk}/events", {"tag_key": tag["tag_key"]})
    assert [item["id"] for item in filtered.data["data"]["list"]] == [event["id"]]
    assert client.get(f"/api/v1/spaces/{other_space.pk}/tags").status_code == 404
    assert client.delete(f"/api/v1/events/{event['id']}/tags/{tag['id']}").status_code == 204
    assert client.delete(f"/api/v1/tags/{tag['id']}").status_code == 204


def test_event_relation_can_be_read_updated_and_deleted():
    owner = User.objects.create_user(username="relation-owner")
    space = make_space(owner, "relation-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    first = client.post(f"/api/v1/spaces/{space.pk}/events", {"event_key": "one", "title": "One", "content": "One"}, format="json").data["data"]
    second = client.post(f"/api/v1/spaces/{space.pk}/events", {"event_key": "two", "title": "Two", "content": "Two"}, format="json").data["data"]
    created = client.post(f"/api/v1/spaces/{space.pk}/event-relations", {"left_event_id": first["id"], "right_event_id": second["id"], "relation_kind": "related", "decision": "pending", "source_note_ids": []}, format="json")
    assert created.status_code == 201
    relation_id = created.data["data"]["id"]
    assert client.get(f"/api/v1/event-relations/{relation_id}").status_code == 200
    assert client.get(f"/api/v1/events/{first["id"]}/notes").status_code == 200
    assert client.patch(f"/api/v1/event-relations/{relation_id}", {"decision": "accepted", "reason": "人工确认"}, format="json").data["data"]["decision"] == "accepted"
    assert client.delete(f"/api/v1/event-relations/{relation_id}").status_code == 204

@patch("chat_analysis.api_views.transaction.on_commit", side_effect=lambda callback: callback())
@patch("chat_analysis.api_views.dispatch_report_generation")
def test_topic_run_creates_scoped_report_and_dispatches_generation(dispatch, on_commit):
    owner = User.objects.create_user(username="topic-run-owner")
    space = make_space(owner, "topic-run-team")
    client = APIClient()
    client.force_authenticate(user=owner)
    topic = client.post(f"/api/v1/spaces/{space.pk}/topics", {"title": "未完成风险", "instruction": "总结风险", "filters": {"keywords": ["风险"]}}, format="json").data["data"]
    Event.objects.create(space=space, created_by=owner, event_key="risk-run", title="风险事项", content="风险等待确认", status=Event.Status.OPEN)
    response = client.post(f"/api/v1/topics/{topic['id']}/run")
    assert response.status_code == 202
    report = response.data["data"]
    assert report["source_info"]["subscription_id"] == topic["id"]
    assert report["status"] == "queued"
    dispatch.assert_called_once()

@pytest.mark.django_db
def test_resource_copy_requires_source_read_and_target_write_and_reports_gaps():
    owner = User.objects.create_user(username="copy-owner")
    target_owner = User.objects.create_user(username="copy-target")
    source = make_space(owner, "copy-source")
    target = make_space(target_owner, "copy-target")
    SpaceMembership.objects.create(space=target, user=owner, role=SpaceMembership.Role.USER, status=SpaceMembership.Status.ACTIVE)
    note = Note.objects.create(space=source, created_by=owner, note_key="copy-note", title="Note", content="Content")
    client = APIClient(); client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{target.pk}/resource-copies", {"source_space_id": source.pk, "resource_type": "note", "resource_ids": [note.pk]}, format="json")
    assert response.status_code == 201
    assert response.data["data"]["copied"][0]["type"] == "note"
    assert response.data["data"]["warnings"][0]["code"] == "evidence_not_copied"
    assert Note.objects.filter(space=target, title="Note").exists()

@pytest.mark.django_db
def test_daily_ai_quota_blocks_new_question():
    owner = User.objects.create_user(username="quota-question-owner")
    space = make_space(owner, "quota-question-team")
    from spaces.models import SpaceQuota
    SpaceQuota.objects.create(space=space, daily_ai_calls=0)
    client = APIClient(); client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{space.pk}/questions", {"question": "这个问题不应执行"}, format="json")
    assert response.status_code == 429

@pytest.mark.django_db
def test_event_copy_can_copy_independent_notes_without_evidence():
    owner = User.objects.create_user(username="copy-event-owner")
    target_owner = User.objects.create_user(username="copy-event-target")
    source = make_space(owner, "copy-event-source")
    target = make_space(target_owner, "copy-event-target")
    SpaceMembership.objects.create(space=target, user=owner, role=SpaceMembership.Role.USER, status=SpaceMembership.Status.ACTIVE)
    event = Event.objects.create(space=source, created_by=owner, event_key="copy-event", title="Event", content="Event content")
    note = Note.objects.create(space=source, created_by=owner, note_key="copy-event-note", title="Note", content="Note content")
    EventNote.objects.create(event=event, note=note, created_by=owner)
    client = APIClient(); client.force_authenticate(user=owner)
    response = client.post(f"/api/v1/spaces/{target.pk}/resource-copies", {"source_space_id": source.pk, "resource_type": "event", "resource_ids": [event.pk], "copy_notes": True}, format="json")
    assert response.status_code == 201
    copied_event = Event.objects.get(pk=response.data["data"]["copied"][0]["id"])
    assert copied_event.space_id == target.pk
    assert copied_event.note_links.count() == 1
    assert response.data["data"]["warnings"][0]["code"] == "evidence_not_copied"


def test_question_message_citation_keeps_conversation_id():
    owner = User.objects.create_user(username="question-citation-owner")
    space = make_space(owner, "question-citation-team")
    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="test",
        source_conversation_id="group",
        identity_key=f"wechat:test:group-{space.pk}",
    )
    message = Message.objects.create(
        conversation=conversation,
        message_key="message-1",
        ingest_seq=1,
        sender_name="Alice",
    )
    MessagePart.objects.create(
        message=message,
        part_key="part-1",
        kind=MessagePart.Kind.TEXT,
        text="明天确认报价",
    )
    output = {
        "answer": "需要确认报价。",
        "citations": [
            {"kind": "message", "id": message.pk, "title": "Alice", "excerpt": "明天确认报价"}
        ],
    }
    with patch(
        "chat_analysis.topic_services.LLMTracker.call_and_track",
        return_value=(output, {"model": "test-model"}),
    ):
        result = answer_question(actor=owner, space=space, question="报价确认了吗？")

    assert result["citations"] == [
        {
            "kind": "message",
            "id": message.pk,
            "conversation_id": conversation.pk,
            "title": "Alice",
            "excerpt": "明天确认报价",
        }
    ]


def test_question_context_applies_keyword_tag_and_relation_filters():
    owner = User.objects.create_user(username="question-filter-owner")
    other = User.objects.create_user(username="question-filter-other")
    space = make_space(owner, "question-filter-team")
    other_space = make_space(other, "question-filter-other-team")

    conversation = Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="test",
        source_conversation_id="quote-group",
        identity_key=f"wechat:test:quote-group-{space.pk}",
    )
    message = Message.objects.create(
        conversation=conversation,
        message_key="quote-message",
        ingest_seq=1,
        sender_name="Alice",
    )
    MessagePart.objects.create(
        message=message,
        part_key="quote-part",
        kind=MessagePart.Kind.TEXT,
        text="客户要求降价百分之十",
    )

    risk_note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="risk-note",
        title="报价风险",
        content="客户要求降价",
    )
    NoteEvidence.objects.create(
        note=risk_note,
        message=message,
        reference_key=NoteEvidence.build_reference_key(message.pk),
    )
    unrelated_note = Note.objects.create(
        space=space,
        created_by=owner,
        note_key="unrelated-note",
        title="无关笔记",
        content="周末团建安排",
    )
    risk_event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="risk-event",
        title="客户风险",
        content="降价压力",
        status=Event.Status.OPEN,
    )
    unrelated_event = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="unrelated-event",
        title="无关事件",
        content="办公室搬迁",
        status=Event.Status.OPEN,
    )
    EventNote.objects.create(event=risk_event, note=risk_note, created_by=owner)
    other_space_event = Event.objects.create(
        space=other_space,
        created_by=other,
        event_key="other-space-risk",
        title="客户风险",
        content="降价压力",
        status=Event.Status.OPEN,
    )
    tag = EventTag.objects.create(
        space=space, created_by=owner, tag_key="risk", label="风险"
    )
    EventTagAssignment.objects.create(event=risk_event, tag=tag, created_by=owner)

    by_keyword = question_context(space=space, keywords=["降价"])
    assert [item["id"] for item in by_keyword["events"]] == [risk_event.pk]
    assert [item["id"] for item in by_keyword["notes"]] == [risk_note.pk]
    assert [item["id"] for item in by_keyword["messages"]] == [message.pk]

    by_tag = question_context(space=space, tag_keys=["risk"])
    assert [item["id"] for item in by_tag["events"]] == [risk_event.pk]

    by_conversation = question_context(
        space=space, conversation_ids=[conversation.pk]
    )
    assert [item["id"] for item in by_conversation["notes"]] == [risk_note.pk]
    assert [item["id"] for item in by_conversation["events"]] == [risk_event.pk]

    by_note = question_context(space=space, note_ids=[unrelated_note.pk])
    assert [item["id"] for item in by_note["notes"]] == [unrelated_note.pk]
    assert by_note["events"] == []

    assert other_space_event.pk not in {
        item["id"] for item in by_keyword["events"]
    }
    assert unrelated_event.pk not in {item["id"] for item in by_keyword["events"]}
