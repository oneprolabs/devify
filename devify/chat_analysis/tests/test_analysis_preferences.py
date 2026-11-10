from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from chat_analysis import execution
from chat_analysis.models import AnalysisJob, NoteEvidence
from chat_analysis.services import ChatAnalysisConflict, create_analysis_job
from chat_domain.models import Conversation, Message, MessagePart
from spaces.models import SpaceWorkflowConfig
from spaces.services import SpaceBootstrapService


@pytest.mark.django_db
def test_job_freezes_settings_and_limits_records():
    owner = User.objects.create_user(username="analysis-preferences-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    prefs = dict(
        config.chat_analysis_preferences,
        lookback_days=30,
        event_granularity="coarse",
    )
    config.chat_analysis_preferences = prefs
    config.save()
    conversation = Conversation.objects.create(
        space=space, identity_key="test:group", kind=Conversation.Kind.GROUP
    )
    for seq, date in [
        (1, timezone.now() - timedelta(days=60)),
        (2, timezone.now()),
    ]:
        msg = Message.objects.create(
            conversation=conversation,
            message_key=f"m{seq}",
            ingest_seq=seq,
            occurred_at=date,
        )
        MessagePart.objects.create(
            message=msg,
            part_key="p",
            kind=MessagePart.Kind.TEXT,
            ordinal=0,
            text="hello",
        )
    job = create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key="prefs",
        end_seq=2,
        input_version="v1",
    )
    assert (
        job.specification["chat_analysis_preferences"]["event_granularity"]
        == "coarse"
    )
    config.chat_analysis_preferences = dict(
        prefs, lookback_days=0, event_granularity="fine"
    )
    config.save()
    execution.execute_analysis_job(job.pk, worker_id="prefs-test")
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.READY
    assert list(
        NoteEvidence.objects.filter(note__analysis_job=job).values_list(
            "message__ingest_seq", flat=True
        )
    ) == [2]


@pytest.mark.django_db
def test_existing_events_are_shared_across_conversations(
    settings, monkeypatch
):
    import json

    from chat_analysis.models import Event, EventEvidence

    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = True
    owner = User.objects.create_user(username="cross-conversation-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    seen = []

    def llm(*, prompt, content, json_mode, node_name, state):
        if node_name == "chat_event_extraction":
            seen.append((prompt, json.loads(content)["existing_events"]))
            return {
                "events": [
                    {
                        "event_key": "project-a",
                        "title": "Project A",
                        "summary": "Project update",
                        "source_seqs": [1],
                    }
                ]
            }, {}
        return {"facts": [], "actions": [], "risks": [], "decisions": []}, {}

    monkeypatch.setattr(execution.LLMTracker, "call_and_track", llm)
    for number in (1, 2):
        conversation = Conversation.objects.create(
            space=space,
            identity_key=f"test:cross:{number}",
            kind=Conversation.Kind.GROUP,
        )
        message = Message.objects.create(
            conversation=conversation,
            message_key="m1",
            ingest_seq=1,
            occurred_at=timezone.now(),
        )
        MessagePart.objects.create(
            message=message,
            part_key="p",
            kind=MessagePart.Kind.TEXT,
            ordinal=0,
            text="project a update",
        )
        job = create_analysis_job(
            actor=owner,
            space=space,
            conversation=conversation,
            request_key=f"cross-{number}",
            end_seq=1,
            input_version="v1",
        )
        execution.execute_analysis_job(job.pk, worker_id="cross-test")
    assert Event.objects.filter(space=space).count() == 1
    assert EventEvidence.objects.filter(event__space=space).count() == 2
    assert seen[1][1][0]["event_key"] == "project-a"
    assert "other conversations" in seen[1][0]
    assert "acknowledgements" in seen[1][0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "selected,kind,platform,expected",
    [
        (["direct"], "direct", "wechat", True),
        (["direct"], "group", "wechat", False),
        (["group"], "direct", "wechat", False),
        (["group"], "group", "wechat", True),
        (["direct"], "mail", "email", True),
        (["group"], "mail_thread", "email", True),
        (["direct"], "unknown", "wechat", False),
        (["group"], "unknown", "email", False),
        (["direct", "group"], "unknown", "wechat", True),
        (["direct", "group"], "unknown", "email", True),
    ],
)
def test_conversation_filter_respects_selected_types(
    selected, kind, platform, expected
):
    owner = User.objects.create_user(username="analysis-type-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    config.chat_analysis_preferences = dict(
        config.chat_analysis_preferences, conversation_types=selected
    )
    config.save()
    conversation = Conversation.objects.create(
        space=space, identity_key="test:type", kind=kind, platform=platform
    )
    message = Message.objects.create(
        conversation=conversation,
        message_key="m1",
        ingest_seq=1,
        occurred_at=timezone.now(),
    )
    MessagePart.objects.create(
        message=message,
        part_key="p",
        kind=MessagePart.Kind.TEXT,
        ordinal=0,
        text="example",
    )
    job = create_analysis_job(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key="type",
        end_seq=1,
        input_version="v1",
    )
    execution.execute_analysis_job(job.pk, worker_id="type-test")
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.READY
    assert (
        NoteEvidence.objects.filter(note__analysis_job=job).exists()
        is expected
    )


@pytest.mark.django_db
def test_explicit_request_key_stays_idempotent_across_preference_changes():
    owner = User.objects.create_user(username="analysis-request-key-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    conversation = Conversation.objects.create(
        space=space, identity_key="test:request-key"
    )
    args = dict(
        actor=owner,
        space=space,
        conversation=conversation,
        request_key="explicit",
        end_seq=1,
        input_version="v1",
    )
    first = create_analysis_job(**args)
    config.chat_analysis_preferences = dict(
        config.chat_analysis_preferences, event_granularity="fine"
    )
    config.save()
    second = create_analysis_job(**args)
    assert second.pk == first.pk
    assert second.specification == first.specification
    with pytest.raises(ChatAnalysisConflict):
        create_analysis_job(**dict(args, end_seq=2))


@pytest.mark.django_db
def test_legacy_job_without_preference_snapshot_keeps_unknown_behavior():
    owner = User.objects.create_user(username="analysis-legacy-unknown-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    config.chat_analysis_preferences = dict(
        config.chat_analysis_preferences, conversation_types=["group"]
    )
    config.save()
    conversation = Conversation.objects.create(
        space=space, identity_key="test:legacy-unknown", kind="unknown"
    )
    message = Message.objects.create(
        conversation=conversation, message_key="m1", ingest_seq=1
    )
    MessagePart.objects.create(
        message=message, part_key="p", kind=MessagePart.Kind.TEXT,
        ordinal=0, text="example",
    )
    job = create_analysis_job(
        actor=owner, space=space, conversation=conversation,
        request_key="legacy-unknown", end_seq=1, input_version="v1",
    )
    job.specification = {}
    job.save(update_fields=("specification",))
    execution.execute_analysis_job(job.pk, worker_id="legacy-unknown-test")
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.READY
    assert NoteEvidence.objects.filter(note__analysis_job=job).exists()


@pytest.mark.django_db
def test_job_fails_safely_if_conversation_kind_changes_before_execution():
    owner = User.objects.create_user(username="analysis-kind-race-owner")
    space = SpaceBootstrapService.ensure_personal_space(owner)
    config, _ = SpaceWorkflowConfig.objects.get_or_create(space=space)
    config.chat_analysis_preferences = dict(
        config.chat_analysis_preferences, conversation_types=["group"]
    )
    config.save()
    conversation = Conversation.objects.create(
        space=space, identity_key="test:kind-race", kind="group"
    )
    message = Message.objects.create(
        conversation=conversation, message_key="m1", ingest_seq=1
    )
    MessagePart.objects.create(
        message=message, part_key="p", kind=MessagePart.Kind.TEXT,
        ordinal=0, text="example",
    )
    job = create_analysis_job(
        actor=owner, space=space, conversation=conversation,
        request_key="kind-race", end_seq=1, input_version="v1",
    )
    assert job.specification["analysis_conversation_kind"] == "group"
    conversation.kind = "direct"
    conversation.save(update_fields=("kind",))
    execution.execute_analysis_job(job.pk, worker_id="kind-race-test")
    job.refresh_from_db()
    assert job.state == AnalysisJob.State.FAILED
    assert not NoteEvidence.objects.filter(note__analysis_job=job).exists()
