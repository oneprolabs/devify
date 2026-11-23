import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from chat_analysis.execution import execute_analysis_job
from chat_analysis.models import AnalysisJob, AnalysisJobMessage
from chat_analysis.tests.test_execution import (
    add_message,
    make_conversation,
    make_job,
    make_space,
)

pytestmark = pytest.mark.django_db


def test_message_can_only_be_reserved_once():
    owner = User.objects.create_user(username="scope-owner")
    space = make_space(owner, "scope-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    first = make_job(space, owner, conversation, key="scope-1")
    second = make_job(space, owner, conversation, key="scope-2")
    AnalysisJobMessage.objects.create(job=first, message=message)
    with pytest.raises(IntegrityError), transaction.atomic():
        AnalysisJobMessage.objects.create(job=second, message=message)


def test_scope_rejects_message_from_other_conversation():
    owner = User.objects.create_user(username="scope-isolation-owner")
    space = make_space(owner, "scope-isolation-space")
    first = make_conversation(space, "first")
    second = make_conversation(space, "second")
    job = make_job(space, owner, first)
    with pytest.raises(ValidationError):
        AnalysisJobMessage.objects.create(
            job=job, message=add_message(second, 1)
        )


def test_scheduled_job_only_analyzes_assigned_messages(monkeypatch, settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="scope-execution-owner")
    space = make_space(owner, "scope-execution-space")
    conversation = make_conversation(space)
    first = add_message(conversation, 1)
    add_message(conversation, 2)
    third = add_message(conversation, 3)
    job = make_job(space, owner, conversation, end_seq=3)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    assignments = [
        AnalysisJobMessage.objects.create(job=job, message=m)
        for m in (first, third)
    ]
    seen = []
    monkeypatch.setattr(
        "chat_analysis.execution._prepare_chunk",
        lambda *_args, **_kwargs: (None, None),
    )
    monkeypatch.setattr(
        "chat_analysis.execution._write_chunk_note",
        lambda job, messages, *_results: (
            seen.extend(m.pk for m in messages) or True,
            False,
        ),
    )
    result = execute_analysis_job(job.pk, worker_id="test")
    assert result.job.state == AnalysisJob.State.READY
    assert seen == [first.pk, third.pk]
    assert all(
        AnalysisJobMessage.objects.get(pk=a.pk).completed_at
        for a in assignments
    )


def test_partial_chunk_is_not_marked_completed(monkeypatch, settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="scope-partial-owner")
    space = make_space(owner, "scope-partial-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    job = make_job(space, owner, conversation, end_seq=1)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    assignment = AnalysisJobMessage.objects.create(job=job, message=message)
    monkeypatch.setattr(
        "chat_analysis.execution._prepare_chunk",
        lambda *_args, **_kwargs: (None, None),
    )
    monkeypatch.setattr(
        "chat_analysis.execution._write_chunk_note",
        lambda job, messages, *_results: (True, True),
    )
    result = execute_analysis_job(job.pk, worker_id="test")
    assignment.refresh_from_db()
    assert result.job.state == AnalysisJob.State.PARTIAL
    assert assignment.completed_at is None


def test_disabled_llm_never_marks_scheduled_messages_complete(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = False
    owner = User.objects.create_user(username="scope-no-llm-owner")
    space = make_space(owner, "scope-no-llm-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    job = make_job(space, owner, conversation, end_seq=1)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    assignment = AnalysisJobMessage.objects.create(job=job, message=message)
    result = execute_analysis_job(job.pk, worker_id="test")
    assignment.refresh_from_db()
    assert result.job.state != AnalysisJob.State.READY
    assert assignment.completed_at is None


def test_model_window_keeps_the_rest_for_the_next_pass(monkeypatch, settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="scope-window-owner")
    space = make_space(owner, "scope-window-space")
    conversation = make_conversation(space)
    messages = [
        add_message(conversation, index, text="x" * 40) for index in (1, 2)
    ]
    job = make_job(space, owner, conversation, end_seq=2)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    for message in messages:
        AnalysisJobMessage.objects.create(job=job, message=message)
    seen = []

    def prefix(_job, chunk):
        return chunk[:1]

    monkeypatch.setattr("chat_analysis.execution._messages_for_model", prefix)
    monkeypatch.setattr(
        "chat_analysis.execution._prepare_chunk",
        lambda *_args, **_kwargs: (None, None),
    )
    monkeypatch.setattr(
        "chat_analysis.execution._write_chunk_note",
        lambda job, chunk, *_results: (
            seen.append([item.pk for item in chunk]) or True,
            False,
        ),
    )
    result = execute_analysis_job(job.pk, worker_id="test")
    assert seen == [[messages[0].pk], [messages[1].pk]]
    assert result.job.state == AnalysisJob.State.READY


def test_impossible_model_budget_keeps_assignment_retryable(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_MODEL_INPUT_TOKENS = 1
    owner = User.objects.create_user(username="scope-overlong-owner")
    space = make_space(owner, "scope-overlong-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1, text="x" * 80)
    job = make_job(space, owner, conversation, end_seq=1)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    assignment = AnalysisJobMessage.objects.create(job=job, message=message)

    result = execute_analysis_job(job.pk, worker_id="test")
    assignment.refresh_from_db()
    assert result.job.state == AnalysisJob.State.QUEUED
    assert assignment.completed_at is None
    assert assignment.error == ""
    assert "request overhead exceeds" in result.job.error


def test_unavailable_assigned_message_is_not_reported_as_complete(settings):
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    owner = User.objects.create_user(username="scope-orphan-owner")
    space = make_space(owner, "scope-orphan-space")
    conversation = make_conversation(space)
    message = add_message(conversation, 1)
    message.orphaned_at = timezone.now()
    message.save(update_fields=("orphaned_at",))
    job = make_job(space, owner, conversation, end_seq=1)
    job.specification["scheduled_message_scope"] = True
    job.save(update_fields=("specification",))
    assignment = AnalysisJobMessage.objects.create(job=job, message=message)
    result = execute_analysis_job(job.pk, worker_id="test")
    assignment.refresh_from_db()
    assert result.job.state == AnalysisJob.State.PARTIAL
    assert assignment.completed_at is None
