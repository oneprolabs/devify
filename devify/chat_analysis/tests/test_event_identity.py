from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.keys import canonical_event_key
from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventEvidence,
    EventNote,
    Note,
)
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def make_space(owner, slug="identity-team"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def make_conversation(space, key="group"):
    return Conversation.objects.create(
        space=space,
        platform=Conversation.Platform.WECHAT,
        source_namespace="local",
        source_conversation_id=key,
        identity_key=f"wechat:local:{key}-{space.pk}",
        title=key,
    )


def add_message(conversation, index, text, occurred_at):
    message = Message.objects.create(
        conversation=conversation,
        message_key=f"m-{index}",
        ingest_seq=index,
        occurred_at=occurred_at,
        sender_name="Alice",
    )
    MessagePart.objects.create(
        message=message,
        part_key="text-0",
        kind=MessagePart.Kind.TEXT,
        text=text,
    )
    return message


def make_job(
    space, owner, conversation, end_seq, start_seq=0, request_key=None
):
    return AnalysisJob.objects.create(
        space=space,
        created_by=owner,
        conversation=conversation,
        request_key=request_key or f"job-{space.pk}-{end_seq}",
        start_seq=start_seq,
        end_seq=end_seq,
        input_version="wechat.v1",
    )


def fake_llm(events):
    def side_effect(*, prompt, content, json_mode, node_name, state):
        if node_name == "chat_event_extraction":
            return {"events": events}, {"model": "test"}
        return (
            {"facts": [], "actions": [], "risks": [], "decisions": []},
            {"model": "test"},
        )

    return side_effect


def test_canonical_event_key_removes_prefix_and_dates():
    assert (
        canonical_event_key("evt_inc13442_hcs_block_storage")
        == "inc13442-hcs-block-storage"
    )
    assert canonical_event_key("INC13442-2026-08-12") == "inc13442"
    assert canonical_event_key("event_inc14606_tencent_aksk") == (
        "inc14606-tencent-aksk"
    )
    assert canonical_event_key("") == ""


def test_execution_attaches_message_level_evidence_and_window(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="identity-owner")
    space = make_space(owner)
    conversation = make_conversation(space)
    start = timezone.now() - timedelta(days=3)
    add_message(conversation, 1, "open incident 100", start)
    add_message(
        conversation, 2, "incident 100 resolved", start + timedelta(days=2)
    )
    job = make_job(space, owner, conversation, end_seq=2)

    events = [
        {
            "event_key": "INC100-opening",
            "entity": "INC100",
            "title": "INC100 opening",
            "summary": "Incident 100 was reported.",
            "status": "in_progress",
            "source_seqs": [1],
            "tags": ["INC100", "HyperBDR"],
        },
        {
            "event_key": "inc100-resolution",
            "entity": "INC100",
            "title": "INC100 resolution",
            "summary": "Incident 100 was resolved.",
            "status": "done",
            "source_seqs": [2],
            "tags": ["INC100"],
        },
    ]
    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        side_effect=fake_llm(events),
    ):
        execution.execute_analysis_job(job.pk, worker_id="identity-worker")

    opened = Event.objects.get(space=space, event_key="inc100-opening")
    resolved = Event.objects.get(space=space, event_key="inc100-resolution")
    assert opened.opened_at == start
    assert opened.last_activity_at == start
    assert opened.status == Event.Status.IN_PROGRESS
    assert opened.entity_key == "inc100"
    assert resolved.last_activity_at == start + timedelta(days=2)
    assert EventEvidence.objects.filter(event=opened).count() == 1
    assert EventEvidence.objects.filter(event=resolved).count() == 1
    assert opened.tag_assignments.count() == 2
    assert resolved.tag_assignments.count() == 1


def test_same_matter_across_chunks_merges_into_one_event(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="identity-merge-owner")
    space = make_space(owner, "identity-merge-team")
    conversation = make_conversation(space, "merge")
    start = timezone.now() - timedelta(days=5)
    add_message(conversation, 1, "quote draft", start)
    add_message(conversation, 2, "quote sent", start + timedelta(days=4))
    first_job = make_job(
        space, owner, conversation, end_seq=1, request_key="chunk-a"
    )
    second_job = make_job(
        space,
        owner,
        conversation,
        start_seq=1,
        end_seq=2,
        request_key="chunk-b",
    )

    first = [
        {
            "event_key": "evt_quote_follow_up_2026-08-01",
            "title": "Quote follow-up",
            "summary": "Prepare the quote.",
            "source_seqs": [1],
        }
    ]
    second = [
        {
            "event_key": "Quote-Follow-Up",
            "title": "Quote follow-up",
            "summary": "Send the quote.",
            "status": "done",
            "source_seqs": [2],
        }
    ]
    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        side_effect=fake_llm(first),
    ):
        execution.execute_analysis_job(
            first_job.pk, worker_id="identity-worker-1"
        )

    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        side_effect=fake_llm(second),
    ):
        execution.execute_analysis_job(
            second_job.pk, worker_id="identity-worker-2"
        )

    assert Event.objects.filter(space=space).count() == 1
    event = Event.objects.get(space=space)
    assert event.event_key == "quote-follow-up"
    assert event.note_links.count() == 2
    assert EventEvidence.objects.filter(event=event).count() == 2
    assert event.opened_at == start
    assert event.last_activity_at == start + timedelta(days=4)
    assert event.status == Event.Status.DONE


def test_repair_events_merges_duplicates_and_backfills_windows(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    owner = User.objects.create_user(username="identity-repair-owner")
    space = make_space(owner, "identity-repair-team")
    conversation = make_conversation(space, "repair")
    occurred_at = timezone.now() - timedelta(days=1)
    message = add_message(conversation, 1, "incident 200", occurred_at)
    job = make_job(space, owner, conversation, end_seq=1)
    note = Note.objects.create(
        space=space,
        created_by=owner,
        analysis_job=job,
        note_key="repair-note",
        title="Repair note",
        content="content",
    )
    from chat_analysis.services import add_note_evidence

    add_note_evidence(actor=owner, note=note, message=message)

    first = Event.objects.create(
        space=space,
        created_by=owner,
        event_key="evt_inc200_report_2026-08-01",
        title="INC200 report",
        content="reported",
    )
    Event.objects.create(
        space=space,
        created_by=owner,
        event_key="INC200_REPORT",
        title="INC200 report",
        content="reported again",
    )
    EventNote.objects.create(event=first, note=note, created_by=owner)

    out = StringIO()
    call_command(
        "repair_events", "--space", str(space.pk), "--apply", stdout=out
    )

    assert Event.objects.filter(space=space).count() == 1
    event = Event.objects.get(space=space)
    assert event.event_key == "inc200-report"
    assert event.opened_at == occurred_at
    assert event.last_activity_at == occurred_at
    assert "merged=1" in out.getvalue()


def test_rebuild_events_replaces_old_events_with_evidence(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="identity-rebuild-owner")
    space = make_space(owner, "identity-rebuild-team")
    conversation = make_conversation(space, "rebuild")
    occurred_at = timezone.now() - timedelta(days=2)
    message = add_message(conversation, 1, "incident 300", occurred_at)
    job = make_job(space, owner, conversation, end_seq=1)
    note = Note.objects.create(
        space=space,
        created_by=owner,
        analysis_job=job,
        note_key="rebuild-note",
        title="Rebuild note",
        content="content",
    )
    from chat_analysis.services import add_note_evidence

    add_note_evidence(actor=owner, note=note, message=message)
    Event.objects.create(
        space=space,
        created_by=owner,
        event_key="old-incident-key",
        title="Old incident",
        content="old",
    )

    events = [
        {
            "event_key": "INC300-report",
            "entity": "INC300",
            "title": "INC300 report",
            "summary": "Incident 300 was reported.",
            "source_seqs": [1],
            "tags": ["INC300"],
        }
    ]
    out = StringIO()
    with patch(
        "chat_analysis.execution.LLMTracker.call_and_track",
        side_effect=fake_llm(events),
    ):
        call_command(
            "rebuild_events",
            "--space",
            str(space.pk),
            "--apply",
            stdout=out,
        )

    assert Event.objects.filter(space=space).count() == 1
    event = Event.objects.get(space=space)
    assert event.event_key == "inc300-report"
    assert event.entity_key == "inc300"
    assert event.opened_at == occurred_at
    assert EventEvidence.objects.filter(event=event).count() == 1
    assert "rebuilt_notes=1" in out.getvalue()
