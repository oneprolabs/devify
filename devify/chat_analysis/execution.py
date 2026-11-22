"""Analysis job execution: leases, fencing, checkpoints and rule extraction.

Execution never trusts a worker beyond its lease. Every claim increments the
job's fencing token, so a worker whose lease expired cannot complete or
overwrite a job that another worker has taken over.

The first extractor is deliberately rule based: it turns a message window
into chunked Notes with message evidence. Automatic runs reuse stable note
keys and the existing Note service, which refuses to overwrite manual Notes.
"""

import json
import logging
import os
import time
from copy import copy
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from time import monotonic

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from chat_analysis.event_metadata import participant_metadata
from chat_analysis.event_reducer import prepare_event_reduction
from chat_analysis.keys import (
    canonical_event_key,
    entity_from_text,
    slugify_key,
)
from chat_analysis.models import (
    AnalysisJob,
    AnalysisJobMessage,
    Event,
    EventSuggestion,
    Note,
)
from chat_analysis.services import (
    ChatAnalysisError,
    ChatAnalysisPermissionError,
    add_note_evidence,
    create_note,
    readable_text_parts,
    refresh_event_window,
)
from chat_analysis.suggestions import (
    create_event_suggestion,
    review_event_suggestion,
)
from chat_analysis.token_budget import (
    MessageExceedsBudget,
    request_budget,
    take_message_window,
)
from chat_analysis.user_dispatch import (
    claim_publication_slot,
    dispatch_lock,
    next_analysis_hour,
    publication_slot_valid,
    release_publication_slot,
    renew_publication_slot,
    reserve_user_slot,
    resume_is_due,
)
from chat_domain.models import Message, MessagePart
from core.tracking import LLMTracker
from spaces.models import Space, SpaceWorkflowConfig
from spaces.services import SpacePermissionService

logger = logging.getLogger(__name__)

DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3
ANALYSIS_CHUNK_SIZE = 200
MODEL_INPUT_TOKEN_BUDGET = 12000
ENGINE_VERSION = "chat-analysis.v2"
MAX_EVENTS_PER_CHUNK = 8
EXISTING_EVENT_CONTEXT_LIMIT = 40
CROSS_CANDIDATE_LIMIT = 12
DEFAULT_OUTPUT_LANGUAGE = "zh-CN"
MODULE_LOADED_AT = time.time()
MODULE_PATH = os.path.abspath(__file__)


class AnalysisJobRejected(Exception):
    """Raised when a job may not run for a non-transient reason."""


class AnalysisLeaseLost(Exception):
    """Raised when a worker no longer holds the job lease."""


class AnalysisBatchYield(Exception):
    """Stop after saving a bounded portion of event reduction."""


@dataclass(frozen=True)
class ExecutionResult:
    job: AnalysisJob
    handler_result: dict


def _lock_job(job_id):
    return AnalysisJob.objects.select_for_update().filter(pk=job_id).first()


def _ensure_lease(job, worker_id, fencing_token):
    if (
        job.state != AnalysisJob.State.RUNNING
        or job.lease_owner != worker_id
        or job.fencing_token != fencing_token
        or job.lease_until is None
        or job.lease_until <= timezone.now()
    ):
        raise AnalysisLeaseLost(
            "The analysis job lease is no longer held by this worker."
        )


def claim_analysis_job(
    job_id,
    *,
    worker_id,
    lease_seconds=DEFAULT_LEASE_SECONDS,
):
    """Claim a queued job or an expired running job.

    Returns ``None`` when another worker holds a live lease or the job is in
    a terminal state. Each successful claim increments ``fencing_token`` and
    ``attempts``.
    """
    if not worker_id:
        raise ValueError("worker_id is required.")
    now = timezone.now()
    with dispatch_lock():
        job = _lock_job(job_id)
        if job is None:
            return None
        if job.state == AnalysisJob.State.RUNNING:
            if job.lease_until and job.lease_until > now:
                return None
        elif job.state != AnalysisJob.State.QUEUED:
            return None
        if not resume_is_due(job):
            return None
        if reserve_user_slot(job) is None:
            return None
        job.state = AnalysisJob.State.RUNNING
        job.lease_owner = worker_id
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.fencing_token = job.fencing_token + 1
        job.attempts = job.attempts + 1
        job.engine_version = ENGINE_VERSION
        job.error = ""
        job.checkpoint = dict(job.checkpoint)
        job.checkpoint.pop("resume_after", None)
        job.save(
            update_fields=(
                "state",
                "checkpoint",
                "lease_owner",
                "lease_until",
                "fencing_token",
                "attempts",
                "engine_version",
                "error",
                "updated_at",
            )
        )
        return job


def renew_analysis_lease(
    job,
    *,
    worker_id,
    fencing_token,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    checkpoint=None,
):
    """Extend the lease and optionally store a checkpoint."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.lease_until = timezone.now() + timedelta(seconds=lease_seconds)
        update_fields = ["lease_until", "updated_at"]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
            update_fields.append("checkpoint")
        locked.save(update_fields=update_fields)
        return locked


def update_analysis_checkpoint(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint,
):
    return renew_analysis_lease(
        job,
        worker_id=worker_id,
        fencing_token=fencing_token,
        checkpoint=checkpoint,
    )


def complete_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    checkpoint=None,
    result_ref=None,
    partial=False,
):
    """Finish a job as ``ready`` or, with unreadable input, ``partial``."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.state = (
            AnalysisJob.State.PARTIAL if partial else AnalysisJob.State.READY
        )
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        if result_ref is not None:
            locked.result_ref = result_ref
        locked.lease_owner = ""
        locked.lease_until = None
        locked.error = ""
        locked.save(
            update_fields=(
                "state",
                "checkpoint",
                "result_ref",
                "lease_owner",
                "lease_until",
                "error",
                "updated_at",
            )
        )
        return locked


def yield_analysis_job(job, outcome):
    """Continue from committed progress without charging a failed attempt."""
    with transaction.atomic():
        locked = _lock_job(job.pk)
        _ensure_lease(locked, job.lease_owner, job.fencing_token)
        locked.state = AnalysisJob.State.QUEUED
        locked.checkpoint = outcome["checkpoint"]
        locked.checkpoint["resume_after"] = next_analysis_hour()
        locked.result_ref = outcome["result_ref"]
        locked.lease_owner = ""
        locked.lease_until = None
        locked.attempts = max(0, locked.attempts - 1)
        locked.save(
            update_fields=(
                "state",
                "checkpoint",
                "result_ref",
                "lease_owner",
                "lease_until",
                "attempts",
                "updated_at",
            )
        )
        return locked


def fail_analysis_job(
    job,
    *,
    worker_id,
    fencing_token,
    error,
    retryable=False,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
    checkpoint=None,
):
    """Record a failure and requeue it while attempts remain."""
    with transaction.atomic():
        locked = AnalysisJob.objects.select_for_update().get(pk=job.pk)
        _ensure_lease(locked, worker_id, fencing_token)
        locked.error = str(error)[:4000]
        if checkpoint is not None:
            locked.checkpoint = checkpoint
        locked.lease_owner = ""
        locked.lease_until = None
        if retryable and locked.attempts < max_attempts:
            locked.state = AnalysisJob.State.QUEUED
            locked.checkpoint = {
                **locked.checkpoint,
                "resume_after": next_analysis_hour(),
            }
        else:
            locked.state = AnalysisJob.State.FAILED
        locked.save(
            update_fields=(
                "state",
                "error",
                "checkpoint",
                "lease_owner",
                "lease_until",
                "updated_at",
            )
        )
        return locked


def execute_analysis_job(
    job_id,
    *,
    worker_id,
    handler=None,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    max_attempts=DEFAULT_MAX_ATTEMPTS,
    message_limit=None,
    time_limit=None,
    input_boundary=None,
):
    """Claim and run one job, recording success, retry or failure.

    ``handler`` receives the claimed job and a ``lease_seconds`` keyword. It
    must return a dict with optional ``checkpoint``, ``partial`` and
    ``result_ref`` keys. A handler that loses its lease raises
    ``AnalysisLeaseLost`` instead of writing over the new owner's work.
    """
    job = claim_analysis_job(
        job_id,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    if job is None:
        return None
    handler = handler or run_rule_based_analysis
    try:
        if job.specification.get("snapshot_pending"):
            from chat_analysis.scheduled_dispatch import freeze_scheduled_input

            job = freeze_scheduled_input(job, input_boundary=input_boundary)
        budgets = {}
        if message_limit is not None:
            budgets["message_limit"] = message_limit
        if time_limit is not None:
            budgets["time_limit"] = time_limit
        outcome = handler(job, lease_seconds=lease_seconds, **budgets)
    except AnalysisLeaseLost:
        raise
    except Exception as exc:
        non_retryable = isinstance(
            exc,
            (
                AnalysisJobRejected,
                ChatAnalysisPermissionError,
                ChatAnalysisError,
            ),
        )
        failed = fail_analysis_job(
            job,
            worker_id=worker_id,
            fencing_token=job.fencing_token,
            error=f"{type(exc).__name__}: {exc}",
            retryable=not non_retryable,
            max_attempts=max_attempts,
        )
        return ExecutionResult(job=failed, handler_result={"error": str(exc)})
    if not isinstance(outcome, dict):
        outcome = {}
    if outcome.get("yielded"):
        return ExecutionResult(
            job=yield_analysis_job(job, outcome), handler_result=outcome,
        )
    completed = complete_analysis_job(
        job,
        worker_id=worker_id,
        fencing_token=job.fencing_token,
        checkpoint=outcome.get("checkpoint"),
        result_ref=outcome.get("result_ref"),
        partial=bool(outcome.get("partial")),
    )
    return ExecutionResult(job=completed, handler_result=outcome)


def _ensure_job_runnable(job):
    if job.space.status != Space.Status.ACTIVE:
        raise AnalysisJobRejected("Space is not active.")
    if not SpacePermissionService.can_upload(job.created_by, job.space):
        raise AnalysisJobRejected(
            "The initiating user can no longer write to the space."
        )


def _message_texts(message):
    if hasattr(message, "analysis_fragment_text"):
        return [message.analysis_fragment_text]
    return [
        part.text.strip()
        for part in message.parts.all()
        if part.kind == MessagePart.Kind.TEXT
        and part.text
        and part.text.strip()
    ]


def _chunk_note_key(job, messages):
    note_key = (
        f"job:{job.uuid}:{messages[0].ingest_seq}-{messages[-1].ingest_seq}"
    )
    first = messages[0]
    if hasattr(first, "analysis_fragment_offset"):
        start = first.analysis_fragment_offset
        end = start + len(first.analysis_fragment_text)
        note_key += f":offset:{start}-{end}"
    return note_key


def _write_chunk_note(job, messages, summary, events):
    """Create or refresh the automatic Note for one message chunk."""
    conversation = job.conversation
    lines = []
    occurred_at = []
    missing_content = False
    missing_count = 0
    for message in messages:
        if message.occurred_at:
            occurred_at.append(message.occurred_at)
        texts = _message_texts(message)
        if not texts:
            missing_content = True
            missing_count += 1
            continue
        if message.occurred_at:
            stamp = timezone.localtime(message.occurred_at).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            stamp = "unknown-time"
        sender = message.sender_name or message.sender_key or "unknown"
        lines.append(f"[{stamp}] {sender}: {' / '.join(texts)}")
    if missing_count:
        logger.info(
            "Chat analysis job %s: %s messages have no text",
            job.pk, missing_count,
        )
    if not lines:
        return False, True
    first_seq = messages[0].ingest_seq
    last_seq = messages[-1].ingest_seq
    title = (
        f"{conversation.title or conversation.identity_key} "
        f"#{first_seq}-{last_seq}"
    )[:500]
    note = create_note(
        actor=job.created_by,
        space=job.space,
        note_key=_chunk_note_key(job, messages),
        title=title,
        content="\n".join(lines),
        start_at=min(occurred_at) if occurred_at else None,
        end_at=max(occurred_at) if occurred_at else None,
        analysis_job=job,
    )
    if note.origin == Note.Origin.MANUAL:
        return False, missing_content
    for message in messages:
        add_note_evidence(
            actor=job.created_by,
            note=note,
            message=message,
        )
    _persist_enrichment(job, note, messages, summary, events)
    partial = settings.CHAT_ANALYSIS_LLM_ENABLED and (
        summary is None or events is None
    )
    return True, missing_content or partial


def _persist_enrichment(job, note, messages, summary, events):
    if summary is not None:
        note.structured_data = summary
        note.generation_version = "chat-note-llm.v1"
        note.save(
            update_fields=(
                "structured_data",
                "generation_version",
                "updated_at",
            )
        )
    if events is not None:
        _store_events(job, note, messages, events)


def _output_language(space):
    language = (
        SpaceWorkflowConfig.objects.filter(space=space)
        .values_list("language", flat=True)
        .first()
    )
    return language or DEFAULT_OUTPUT_LANGUAGE


def _model_input_budget():
    return int(
        getattr(
            settings,
            "CHAT_ANALYSIS_MODEL_INPUT_TOKENS",
            MODEL_INPUT_TOKEN_BUDGET,
        )
    )


def _request_sizer(job):
    preferences = (job.specification or {}).get(
        "chat_analysis_preferences"
    ) or {}
    language = _output_language(job.space)
    prompt = _event_extraction_prompt(language, preferences)
    summary_prompt = _note_summary_prompt(language, preferences)
    title = job.conversation.title or job.conversation.identity_key
    budget, count = request_budget(_model_input_budget())
    base = count(prompt, _event_content(title, [], [], []))
    # Leave up to a quarter of the usable space for existing events.
    event_limit = budget - max(0, budget - base) // 4

    def count_request(window):
        payload = _message_payload(window)
        event_size = count(prompt, _event_content(title, payload, [], []))
        summary_size = count(
            summary_prompt, json.dumps(payload, ensure_ascii=False)
        )
        return max(event_size + budget - event_limit, summary_size)

    return budget, count_request


def _messages_for_model(job, messages):
    budget, count_request = _request_sizer(job)
    window = take_message_window(messages, count_request, budget)
    # A reply stays with the message it quotes. If it does not fit,
    # both wait for the next window.
    if len(window) < len(messages) and len(window) > 1:
        nxt = messages[len(window)]
        if nxt.reply_to_id and nxt.reply_to_id == window[-1].pk:
            window = window[:-1]
    return window


def _message_fragment(job, message, offset, text):
    if offset >= len(text):
        raise ValueError(
            "No message text remains at the saved fragment offset."
        )
    budget, count = _request_sizer(job)
    fragment = copy(message)
    fragment.analysis_fragment_offset = offset
    fragment.analysis_fragment_text = text[offset:offset + 1]
    if count([fragment]) > budget:
        raise MessageExceedsBudget("Model budget cannot fit one character.")

    # Avoid repeatedly tokenizing the entire remaining text for large uploads.
    low, high = offset + 1, min(len(text) + 1, offset + budget * 4)
    while high - low > 1:
        end = (low + high) // 2
        fragment.analysis_fragment_text = text[offset:end]
        if count([fragment]) <= budget:
            low = end
        else:
            high = end
    if low < len(text):
        newline = text.rfind("\n", offset + (low - offset) * 3 // 4, low)
        if newline >= offset:
            fragment.analysis_fragment_text = text[offset:newline + 1]
            if count([fragment]) <= budget:
                low = newline + 1
    fragment.analysis_fragment_text = text[offset:low]
    return fragment, low if low < len(text) else None


def _message_payload(messages):
    return [
        {
            "seq": message.ingest_seq,
            "sender": message.sender_name or message.sender_key,
            "time": (
                message.occurred_at.isoformat()
                if message.occurred_at
                else None
            ),
            "text": " / ".join(_message_texts(message)),
            **(
                {"fragment_offset": message.analysis_fragment_offset}
                if hasattr(message, "analysis_fragment_offset")
                else {}
            ),
            "reply_to_seq": (
                message.reply_to.ingest_seq
                if message.reply_to_id
                else None
            ),
        }
        for message in messages
    ]


def _message_people(messages):
    people = set()
    for message in messages:
        for value in (message.sender_name, message.sender_key):
            key = slugify_key(value)
            if key:
                people.add(key)
    return people


def _text_overlaps(left, right):
    left_key = slugify_key(left)
    right_key = slugify_key(right)
    if len(left_key) < 2 or len(right_key) < 2:
        return False
    return left_key in right_key or right_key in left_key


def _chunk_text(messages):
    return " ".join(
        " ".join(_message_texts(message)) for message in messages
    )


def _event_overlaps_chunk(event, messages):
    """True when person, title or entity overlaps this chunk."""
    chunk_text = _chunk_text(messages)
    if event.entity_key and _text_overlaps(event.entity_key, chunk_text):
        return True
    if event.title and _text_overlaps(event.title, chunk_text):
        return True
    chunk_people = _message_people(messages)
    evidence_people = set()
    for link in event.evidence.all():
        evidence_people |= _message_people([link.message])
    return bool(chunk_people & evidence_people)


def _event_prompt_item(event, conversation_title):
    return {
        "event_key": event.event_key,
        "title": event.title,
        "summary": event.content,
        "status": event.status or Event.Status.OPEN,
        "entity": event.entity_key,
        "conversation_title": conversation_title,
    }


def _unfinished_event_qs(space):
    return (
        Event.objects.filter(space=space)
        .exclude(status=Event.Status.DONE)
        .prefetch_related("evidence__message__conversation")
        .order_by("-last_activity_at", "-id")
    )


def _open_events_same_conversation(space, conversation):
    title = conversation.title or conversation.identity_key
    events = (
        _unfinished_event_qs(space)
        .filter(evidence__message__conversation_id=conversation.pk)
        .distinct()[:EXISTING_EVENT_CONTEXT_LIMIT]
    )
    return [_event_prompt_item(event, title) for event in events]


def _other_conversation_title(event, conversation_id):
    for link in event.evidence.all():
        other = link.message.conversation
        if other.pk != conversation_id:
            return other.title or other.identity_key
    return ""


def _anchored_events(space, messages):
    quoted = {
        message.reply_to_id for message in messages if message.reply_to_id
    }
    entities = {
        entity for message in messages for text in _message_texts(message)
        if (entity := entity_from_text(text))
    }
    if not (quoted or entities):
        return []
    return list(
        Event.objects.filter(space=space)
        .filter(
            Q(evidence__message_id__in=quoted) | Q(entity_key__in=entities)
        )
        .prefetch_related("evidence__message__conversation")
        .distinct()[:CROSS_CANDIDATE_LIMIT]
    )


def _cross_candidates(space, conversation, messages):
    events = (
        _unfinished_event_qs(space)
        .exclude(evidence__message__conversation_id=conversation.pk)
        .distinct()[:EXISTING_EVENT_CONTEXT_LIMIT]
    )
    selected = []
    for event in events:
        if not _event_overlaps_chunk(event, messages):
            continue
        selected.append(
            _event_prompt_item(
                event,
                _other_conversation_title(event, conversation.pk),
            )
        )
        if len(selected) >= CROSS_CANDIDATE_LIMIT:
            break
    return selected


def _cited_messages(event, by_seq):
    """Resolve cited seqs from sources or legacy source_seqs."""
    source_messages = []
    roles = []
    sources = event.get("sources")
    if isinstance(sources, list) and sources:
        for item in sources:
            if not isinstance(item, dict):
                continue
            try:
                seq = int(item.get("seq"))
            except (TypeError, ValueError):
                continue
            message = by_seq.get(seq)
            if message is None:
                continue
            source_messages.append(message)
            role = str(item.get("role") or "matter").strip().lower()
            roles.append(role or "matter")
        return source_messages, roles
    for value in event.get("source_seqs") or []:
        try:
            seq = int(value)
        except (TypeError, ValueError):
            continue
        message = by_seq.get(seq)
        if message is None:
            continue
        source_messages.append(message)
        roles.append("matter")
    return source_messages, roles


def _reject_pending_false_positive(*, actor, space, event_key):
    """Reject pending suggestions that never became Events."""
    canonical_key = canonical_event_key(event_key)
    if not canonical_key:
        return
    pending = EventSuggestion.objects.filter(
        space=space,
        event_key=canonical_key,
        status=EventSuggestion.Status.PENDING,
        event__isnull=True,
    )
    for suggestion in pending:
        review_event_suggestion(
            actor=actor,
            suggestion=suggestion,
            decision=EventSuggestion.Status.REJECTED,
        )


def _event_extraction_prompt(language, preferences):
    """Ask the model to judge create, attach or drop for one chat chunk."""
    granularity = preferences.get("event_granularity", "balanced")
    style = preferences.get("summary_style", "concise")
    length = preferences.get("summary_length", "standard")
    return (
        "Judge trackable matters in one conversation chunk, fold them into "
        "existing events when they are the same matter, and name the source "
        "chat for every message you use. Return JSON: "
        '{"events":[{"action":"create"|"attach"|"drop","event_key":"",'
        '"title":"","summary":"","status":"open"|"in_progress"|"done",'
        '"entity":"","tags":[],"sources":[{"seq":0,"conversation_title":"",'
        '"role":"matter"|"confirmation"}],"cross_decision":"same"|"related"'
        '|"separate"|null,"reason":""}]}. '
        "Input fields: conversation_title; messages with seq, sender, time, "
        "text, reply_to_seq and optional fragment_offset; "
        "open_events_same_conversation; "
        "A message with fragment_offset is a slice of the original message. "
        "Use existing events to fold later slices into the same matter. "
        "cross_candidates. reply_to_seq is the quoted message when WeChat "
        "has one, otherwise null. open_events_same_conversation are "
        "events from this chat, including closed matters explicitly cited. "
        "An explicit update can reopen a closed matter; a mention cannot. "
        "cross_candidates are events from other chats sharing a person or "
        "a concrete subject with this chunk. Do not treat that list as the "
        "whole space. If a candidate is not in the list, do not merge with "
        "it. "
        "A trackable matter is an assignment, a reminder that expects "
        "action, a decision, a commitment, a deadline, or a follow-up "
        "someone still owes. Greetings, jokes, small talk, meals, casual "
        "invitations, and short replies that confirm nothing are not "
        'events. If this chunk has no trackable matter, return {"events":'
        "[]}. If an existing event is only trivial chat and these messages "
        "do not continue a real matter, emit action drop with that "
        "event_key so a rerun can remove it. "
        'A message whose text is only "1", "收到", "好的", "ok", "嗯" or '
        '"知道了" is a confirmation, never a new event. If reply_to_seq is '
        "set, the confirmation belongs to the matter of that quoted "
        "message. If reply_to_seq is null, attach it to the latest "
        "unfinished matter in this conversation that was directed at the "
        "sender. Later messages from other people do not break the link. "
        "If several unfinished matters fit and none is clearly the target, "
        "or none fits, ignore the reply. "
        "Same conversation: action attach when the candidate continues an "
        "event in open_events_same_conversation, or a confirmation "
        "resolves one. Set event_key to that event. Rewrite summary so it "
        "includes who confirmed and what remains. Set status to "
        "in_progress if work remains, or done if this message closes it. "
        "action create only when no open event in this conversation is the "
        "same matter. Leave event_key empty. A similar topic is not the "
        "same matter. "
        "Cross conversation, only for action create, and only against "
        "cross_candidates: cross_decision same only when both sides are "
        "the same specific assignment, decision or commitment. Set "
        "event_key to that candidate and change action to attach. related "
        "when the topic is similar but it is not the same instance. Words "
        'such as "报价" or "周末" are not enough. Leave event_key empty '
        "and keep action create. separate when they are different "
        "matters. If several candidates could be same and one is not "
        "clearly right, return related. For action attach or drop, set "
        "cross_decision to null. "
        "sources lists every message that supports the event, including "
        "the confirmation. conversation_title is the group or chat name, "
        "not a numeric id. role is matter or confirmation. status is "
        "open, in_progress or done. tags are at most five short labels. "
        "Name the concrete matter in title, entity and tags. Keep sender "
        "names, nicknames and shortened aliases in summary or source "
        "messages, where they can identify who did what. "
        f"Return at most {MAX_EVENTS_PER_CHUNK} events. Do not invent "
        f"facts. Write title, summary and reason in {language}. "
        f"Event granularity: {granularity}. For coarse granularity combine "
        "related developments of the same matter rather than creating "
        "fragments. "
        f"Summary style: {style}; detail: {length}."
    )


def _call_json(*, prompt, content, node_name):
    budget, count = request_budget(_model_input_budget())
    if count(prompt, content) > budget:
        raise MessageExceedsBudget(
            "The model request exceeds the input budget."
        )
    output, _usage = LLMTracker.call_and_track(
        prompt=prompt,
        content=content,
        json_mode=True,
        node_name=node_name,
        state={},
        **(
            {"model_uuid": settings.CHAT_ANALYSIS_MODEL_UUID}
            if settings.CHAT_ANALYSIS_MODEL_UUID else {}
        ),
    )
    return output if isinstance(output, dict) else None


def _note_summary_prompt(language, preferences=None):
    preferences = preferences or {}
    style = preferences.get("summary_style", "concise")
    length = preferences.get("summary_length", "standard")
    return (
        "Summarize one chunk of chat messages. Return JSON with exactly the "
        "keys facts, actions, risks and decisions. Every item must be an "
        "object with a short text field. Do not include events. Do not "
        f"invent facts. Write all text in {language}. "
        f"Summary style: {style}; level of detail: {length}."
    )


def _summarize_note(payload, language, preferences=None):
    return _call_json(
        prompt=_note_summary_prompt(language, preferences),
        content=json.dumps(payload, ensure_ascii=False),
        node_name="chat_note_structuring",
    )


def _event_content(title, payload, open_events, cross):
    return json.dumps(
        {
            "conversation_title": title,
            "messages": payload,
            "open_events_same_conversation": open_events,
            "cross_candidates": cross,
        },
        ensure_ascii=False,
    )


def _extract_events(job, messages, payload, language):
    preferences = (job.specification or {}).get(
        "chat_analysis_preferences", {}
    )
    conversation = job.conversation
    conversation_title = (
        conversation.title or conversation.identity_key
    )
    prompt = _event_extraction_prompt(language, preferences)
    open_events = _open_events_same_conversation(job.space, conversation)
    if _defer_event_publication(job):
        prior_ids = {
            message.reply_to_id for message in messages if message.reply_to_id
        } | {
            message.pk for message in messages
            if getattr(message, "analysis_fragment_offset", 0)
        }
        if prior_ids:
            drafts = EventSuggestion.objects.filter(
                analysis_job=job, status=EventSuggestion.Status.PENDING,
                note__evidence__message_id__in=prior_ids,
            ).order_by("-pk").distinct()[:CROSS_CANDIDATE_LIMIT]
            open_events = [
                {
                    "event_key": draft.event_key,
                    "title": draft.title,
                    "summary": draft.summary,
                    "status": draft.proposed_status,
                    "entity": draft.entity_key,
                    "conversation_title": conversation_title,
                }
                for draft in drafts
            ] + open_events
    cross = _cross_candidates(job.space, conversation, messages)
    anchors = _anchored_events(job.space, messages)
    anchor_keys = {event.event_key for event in anchors}
    for event in reversed(anchors):
        other_title = _other_conversation_title(event, conversation.pk)
        same_chat = any(
            link.message.conversation_id == conversation.pk
            for link in event.evidence.all()
        )
        candidates = open_events if same_chat else cross
        candidates[:] = [
            item for item in candidates if item["event_key"] != event.event_key
        ]
        candidates.insert(0, _event_prompt_item(
            event, conversation_title if same_chat else other_title,
        ))
    budget, count = request_budget(_model_input_budget())
    content = _event_content(conversation_title, payload, open_events, cross)
    while count(prompt, content) > budget and (cross or open_events):
        for pool in (cross, open_events):
            if pool and pool[-1]["event_key"] not in anchor_keys:
                pool.pop()
                break
        else:
            (cross or open_events).pop()
        content = _event_content(
            conversation_title, payload, open_events, cross
        )
    output = _call_json(
        prompt=prompt,
        content=content,
        node_name="chat_event_extraction",
    )
    events = output.get("events") if output is not None else None
    if not isinstance(events, list):
        return None
    if _defer_event_publication(job):
        allowed = {item["event_key"] for item in open_events + cross}
        validated = []
        for event in events:
            if not isinstance(event, dict):
                continue
            action = str(event.get("action") or "create").strip().lower()
            key = canonical_event_key(event.get("event_key"))
            if action in ("attach", "drop") and key in allowed:
                validated.append(
                    {**event, "action": action, "event_key": key}
                )
            elif action != "drop":
                validated.append(
                    {**event, "action": "create", "event_key": ""}
                )
        return validated
    return events


def _defer_event_publication(job):
    return (
        (job.specification or {}).get("scheduled_message_scope") is True
        and settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS
    )


def _store_events(job, note, messages, events):
    by_seq = {message.ingest_seq: message for message in messages}
    senders = {
        message.sender_name or message.sender_key for message in messages
    }
    for index, event in enumerate(events[:MAX_EVENTS_PER_CHUNK]):
        if not isinstance(event, dict):
            continue
        action = str(event.get("action") or "create").strip().lower()
        if action not in ("create", "attach", "drop"):
            action = "create"
        if action == "drop":
            key = str(event.get("event_key") or "").strip()
            if key:
                _reject_pending_false_positive(
                    actor=job.created_by,
                    space=note.space,
                    event_key=key,
                )
            continue
        title = str(event.get("title") or "").strip()
        summary = str(event.get("summary") or "").strip()
        if not title or not summary:
            continue
        status = str(event.get("status") or "").strip().lower()
        if status not in Event.Status.values:
            status = Event.Status.OPEN
        source_messages, roles = _cited_messages(event, by_seq)
        confirmation_only = bool(roles) and all(
            role == "confirmation" for role in roles
        )
        if status == Event.Status.DONE and confirmation_only:
            status = Event.Status.IN_PROGRESS
        raw_tags = event.get("tags")
        title, entity, tags = participant_metadata(
            title, event.get("entity"),
            raw_tags if isinstance(raw_tags, list) else (), summary, senders,
        )
        if not title:
            continue
        first = messages[0]
        fallback = (
            f"{job.uuid}:{first.ingest_seq}:{slugify_key(title)}"
            if hasattr(first, "analysis_fragment_offset")
            else f"{job.uuid}:event:{first.ingest_seq}:{index}"
        )
        event_key = str(event.get("event_key") or fallback)[:255]
        suggestion = create_event_suggestion(
            actor=job.created_by,
            note=note,
            analysis_job=job,
            event_key=event_key,
            entity_key=entity,
            title=title,
            summary=summary,
            status=status,
            tags=tags,
            source_seqs=[
                message.ingest_seq for message in source_messages
            ],
        )
        if (
            settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS
            and not _defer_event_publication(job)
        ):
            suggestion = review_event_suggestion(
                actor=job.created_by,
                suggestion=suggestion,
                decision=EventSuggestion.Status.ACCEPTED,
            )
            if suggestion.event_id and not source_messages:
                refresh_event_window(suggestion.event, messages=messages)
            if (
                suggestion.event_id
                and action == "attach"
                and source_messages
                and getattr(first, "analysis_fragment_offset", 0)
            ):
                previous = EventSuggestion.objects.filter(
                    event_id=suggestion.event_id,
                    analysis_job=job,
                    note__evidence__message=first,
                    status=EventSuggestion.Status.ACCEPTED,
                ).exclude(pk=suggestion.pk).order_by("-id").first()
                if previous:
                    Event.objects.filter(
                        pk=suggestion.event_id, content=previous.summary
                    ).update(
                        content=suggestion.summary, updated_at=timezone.now()
                    )


def _reduction_progress(
    job,
    candidates,
    *,
    publication=False,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    time_limit=None,
):
    source_ids = [item.pk for item in candidates]
    saved = (job.checkpoint or {}).get("event_reduction", {})
    progress = (
        saved.get("progress")
        if saved.get("source_ids") == source_ids else None
    )
    started_at = monotonic()
    seconds = (
        max(1, settings.CHAT_ANALYSIS_BATCH_SECONDS)
        if time_limit is None
        else max(0, time_limit)
    )

    def save_progress(value):
        with dispatch_lock():
            locked = _lock_job(job.pk)
            if publication:
                if not renew_publication_slot(job):
                    raise AnalysisLeaseLost("Event publication lease expired.")
            else:
                _ensure_lease(locked, job.lease_owner, job.fencing_token)
            checkpoint = {
                **locked.checkpoint,
                "event_reduction": {
                    "source_ids": source_ids, "progress": value,
                },
            }
            if publication:
                locked.checkpoint = checkpoint
                locked.save(update_fields=("checkpoint", "updated_at"))
            else:
                renew_analysis_lease(
                    locked,
                    worker_id=job.lease_owner,
                    fencing_token=job.fencing_token,
                    lease_seconds=lease_seconds,
                    checkpoint=checkpoint,
                )
            job.checkpoint = checkpoint
        if value.get("phase") != 3 and monotonic() - started_at >= seconds:
            raise AnalysisBatchYield()

    return progress, save_progress


def _clear_reduction_progress(job):
    checkpoint = dict(job.checkpoint or {})
    checkpoint.pop("event_reduction", None)
    checkpoint.pop("publication_failures", None)
    AnalysisJob.objects.filter(pk=job.pk).update(
        checkpoint=checkpoint, error="",
    )
    job.checkpoint = checkpoint
    job.error = ""


def _publish_reduced_events(job, lease_seconds):
    candidates = list(
        EventSuggestion.objects.filter(
            analysis_job=job,
            status=EventSuggestion.Status.PENDING,
        )
        .select_related("note", "analysis_job")
        .order_by("pk")
    )
    if not candidates:
        return
    job = renew_analysis_lease(
        job,
        worker_id=job.lease_owner,
        fencing_token=job.fencing_token,
        lease_seconds=lease_seconds,
    )
    progress, save_progress = _reduction_progress(
        job,
        candidates,
        lease_seconds=lease_seconds,
    )
    groups = prepare_event_reduction(
        job,
        candidates,
        call_json=_call_json,
        progress=progress,
        save_progress=save_progress,
    )
    with transaction.atomic():
        locked = _lock_job(job.pk)
        _ensure_lease(locked, job.lease_owner, job.fencing_token)
        Space.objects.select_for_update().only("pk").get(pk=job.space_id)
        _apply_reduced_groups(job, candidates, groups)
        _clear_reduction_progress(job)


def _apply_reduced_groups(job, candidates, groups):
    existing_keys = set(
        Event.objects.filter(
            space_id=job.space_id,
            event_key__in={item.event_key for item in candidates},
        ).values_list("event_key", flat=True)
    )
    for group in groups:
        destinations = {item.event_key for item in group} & existing_keys
        if len(destinations) > 1:
            for item in group:
                _accept_reduced_group(job, [item], item.event_key)
            continue
        key = next(iter(destinations), group[0].event_key)
        _accept_reduced_group(job, group, key)


def _pending_batch_candidates():
    return EventSuggestion.objects.filter(
        status=EventSuggestion.Status.PENDING,
        analysis_job__state=AnalysisJob.State.READY,
        analysis_job__checkpoint__event_map_ready=True,
        analysis_job__specification__boundary__isnull=False,
    )


def _active_batch_jobs(space_id, boundary):
    specs = AnalysisJob.objects.filter(
        space_id=space_id,
        state__in=(AnalysisJob.State.QUEUED, AnalysisJob.State.RUNNING),
    ).values_list("specification", flat=True)
    return any(
        spec.get("scheduled_message_scope") is True
        and spec.get("boundary") == boundary
        for spec in specs
    )


def _publish_event_batch(space_id, boundary, *, time_limit=None):
    pending = _pending_batch_candidates().filter(space_id=space_id)

    def current_candidates():
        return [
            item
            for item in pending.select_related(
                "note",
                "analysis_job__conversation",
                "analysis_job__created_by",
            ).order_by("pk")
            if item.analysis_job.specification.get("boundary") == boundary
        ]

    if _active_batch_jobs(space_id, boundary):
        return False
    candidates = current_candidates()
    if not candidates:
        return False
    job = claim_publication_slot(candidates[0].analysis_job_id)
    if job is None:
        return False
    try:
        progress, save_progress = _reduction_progress(
            job,
            candidates,
            publication=True,
            time_limit=time_limit,
        )
        groups = prepare_event_reduction(
            job,
            candidates,
            call_json=_call_json,
            progress=progress,
            save_progress=save_progress,
        )
        with dispatch_lock():
            Space.objects.select_for_update().only("pk").get(pk=space_id)
            if not publication_slot_valid(job):
                raise AnalysisLeaseLost("Event publication lease expired.")
            if _active_batch_jobs(space_id, boundary) or [
                item.pk for item in candidates
            ] != [item.pk for item in current_candidates()]:
                return False
            _apply_reduced_groups(job, candidates, groups)
            _clear_reduction_progress(job)
        return True
    except Exception as error:
        with dispatch_lock():
            if publication_slot_valid(job):
                locked = _lock_job(job.pk)
                locked.checkpoint = {
                    **locked.checkpoint,
                    "resume_after": next_analysis_hour(),
                }
                if not isinstance(error, AnalysisBatchYield):
                    failures = locked.checkpoint.get(
                        "publication_failures", 0,
                    ) + 1
                    locked.checkpoint["publication_failures"] = failures
                    locked.error = (
                        f"event_publication_failed: {type(error).__name__}: "
                        f"{error}"
                    )[:4000]
                    if failures >= DEFAULT_MAX_ATTEMPTS:
                        locked.state = AnalysisJob.State.FAILED
                        locked.checkpoint.pop("resume_after", None)
                locked.save(
                    update_fields=(
                        "checkpoint", "state", "error", "updated_at",
                    ),
                )
        if isinstance(error, AnalysisBatchYield):
            return False
        raise
    finally:
        release_publication_slot(job)


def publish_ready_event_batches(
    *,
    space_id=None,
    boundary=None,
    time_limit=None,
):
    """Publish ready batches within the caller's remaining time budget."""
    if not (
        settings.CHAT_ANALYSIS_LLM_ENABLED
        and settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS
    ):
        return 0
    seconds = (
        max(1, settings.CHAT_ANALYSIS_BATCH_SECONDS)
        if time_limit is None
        else max(0, time_limit)
    )
    if seconds == 0:
        return 0
    started = monotonic()
    candidates = (
        _pending_batch_candidates()
        .order_by("pk")
        .values_list(
            "space_id",
            "analysis_job__specification",
        )
    )
    if space_id is not None:
        candidates = candidates.filter(space_id=space_id)
    if boundary is not None:
        candidates = candidates.filter(
            analysis_job__specification__boundary=boundary,
        )
    batches = dict.fromkeys(
        (space_id, spec["boundary"])
        for space_id, spec in candidates
        if spec.get("boundary")
    )
    published = 0
    for space_id, boundary in batches:
        remaining = seconds - (monotonic() - started)
        if remaining <= 0:
            break
        try:
            published += _publish_event_batch(
                space_id,
                boundary,
                time_limit=remaining,
            )
        except Exception:
            logger.exception(
                "Event reduction failed for space %s at %s", space_id, boundary
            )
    return published


def _accept_reduced_group(job, group, event_key):
    event = (
        Event.objects.select_for_update()
        .filter(
            space_id=job.space_id,
            event_key=event_key,
        )
        .first()
    )
    previous_activity = event.last_activity_at if event else None
    same_job = (
        event is not None
        and event.suggestion_sources.filter(
            analysis_job=job,
        ).exists()
    )
    applied = []
    for item in group:
        if not EventSuggestion.objects.filter(
            pk=item.pk,
            status=EventSuggestion.Status.PENDING,
        ).exists():
            continue
        suggestion = review_event_suggestion(
            actor=item.analysis_job.created_by, suggestion=item,
            decision=EventSuggestion.Status.ACCEPTED,
            target_event_key=event_key,
        )
        if suggestion.event_id:
            applied.append(suggestion)
    if not applied:
        return
    updated = applied[-1].event
    updated.refresh_from_db(fields=("last_activity_at", "content"))
    if updated.last_activity_at is not None and (
        previous_activity is None
        or previous_activity < updated.last_activity_at
        or (same_job and previous_activity == updated.last_activity_at)
    ):
        if all(item.event_key == event_key for item in applied):
            summary = applied[-1].summary
        else:
            summaries = dict.fromkeys(item.summary for item in applied)
            summary = "\n".join(summaries)
        if updated.content != summary:
            updated.content = summary
            updated.save(update_fields=("content", "updated_at"))


def _prepare_chunk(job, messages):
    """Keep model calls and usage tracking outside the result transaction."""
    if not settings.CHAT_ANALYSIS_LLM_ENABLED or not any(
        _message_texts(message) for message in messages
    ):
        return None, None
    payload = _message_payload(messages)
    language = _output_language(job.space)
    try:
        summary = _summarize_note(
            payload,
            language,
            (job.specification or {}).get("chat_analysis_preferences"),
        )
        events = _extract_events(job, messages, payload, language)
        if summary is None or events is None:
            raise ValueError("The model returned an incomplete result.")
    except Exception:
        logger.exception("LLM chat analysis failed for job %s", job.pk)
        raise RuntimeError("LLM chat analysis failed") from None
    return summary, events


def _messages_from_note(note):
    messages = [
        evidence.message
        for evidence in note.evidence.select_related("message").order_by(
            "message__ingest_seq"
        )
    ]
    if messages and ":offset:" in note.note_key:
        start, end = map(
            int, note.note_key.rsplit(":offset:", 1)[1].split("-")
        )
        messages[0].analysis_fragment_offset = start
        messages[0].analysis_fragment_text = note.content[-(end - start):]
    return messages


def _enrich_note_with_llm(job, note, messages):
    """Backfill an existing automatic Note."""
    summary, events = _prepare_chunk(job, messages)
    with transaction.atomic():
        _persist_enrichment(job, note, messages, summary, events)


def run_rule_based_analysis(
    job,
    *,
    lease_seconds=DEFAULT_LEASE_SECONDS,
    message_limit=None,
    time_limit=None,
):
    """Deterministic extractor: chunked Notes plus message evidence.

    It resumes after ``checkpoint["last_ingest_seq"]`` and renews the lease
    after each chunk, so a crashed attempt can be retried without duplicating
    Notes or evidence.
    """
    _ensure_job_runnable(job)
    checkpoint = dict(job.checkpoint or {})
    last_seq = int(checkpoint.get("last_ingest_seq", job.start_seq))
    messages_processed = int(checkpoint.get("messages_processed", 0))
    notes_written = int(checkpoint.get("notes_written", 0))
    partial = bool(checkpoint.get("partial", False))
    started_at = monotonic()
    initial_processed = messages_processed
    chunks_processed = 0
    yielded = False
    message_limit = max(
        1, message_limit or settings.CHAT_ANALYSIS_BATCH_MESSAGES
    )
    time_limit = max(1, time_limit or settings.CHAT_ANALYSIS_BATCH_SECONDS)

    preferences = (job.specification or {}).get("chat_analysis_preferences")
    cutoff = (job.specification or {}).get("analysis_cutoff")
    conversation_types = (
        preferences.get("conversation_types", []) if preferences else []
    )
    if not isinstance(conversation_types, list):
        conversation_types = []
    kind = job.conversation.kind
    snapshot_kind = (job.specification or {}).get("analysis_conversation_kind")
    if snapshot_kind is not None and snapshot_kind != kind:
        raise AnalysisJobRejected(
            "Conversation kind changed after the analysis job was created."
        )
    unknown_chat_is_restricted = (
        kind == "unknown"
        and not all(
            item in conversation_types for item in ("direct", "group")
        )
    )
    excluded = bool(
        preferences
        and (
            (kind in ("direct", "group") and kind not in conversation_types)
            or unknown_chat_is_restricted
        )
    )
    batches = job.upload_batches.all()
    scheduled_scope = (job.specification or {}).get(
        "scheduled_message_scope"
    ) is True
    if scheduled_scope and not getattr(
        settings, "CHAT_ANALYSIS_LLM_ENABLED", False
    ):
        raise RuntimeError(
            "Scheduled event analysis requires the LLM to be enabled."
        )
    while not excluded:
        offset = checkpoint.get("fragment_offset")
        query = Message.objects.filter(
            conversation_id=job.conversation_id,
            ingest_seq__gt=last_seq,
            ingest_seq__lte=job.end_seq,
            orphaned_at__isnull=True,
        )
        if scheduled_scope:
            query = (
                query.filter(
                    scheduled_analysis__job=job,
                    scheduled_analysis__completed_at__isnull=True,
                    scheduled_analysis__error="",
                )
                .annotate(
                    readable=Exists(readable_text_parts(OuterRef("pk"))),
                )
                .filter(readable=True)
            )
        if not scheduled_scope and cutoff:
            query = query.filter(occurred_at__gte=cutoff)
        if not scheduled_scope and batches.exists():
            query = query.filter(
                origins__upload_item__batch__in=batches
            ).distinct()
        if offset is not None:
            query = query.filter(ingest_seq=checkpoint["fragment_seq"])
        processed = messages_processed - initial_processed
        if chunks_processed and (
            processed >= message_limit
            or monotonic() - started_at >= time_limit
        ):
            yielded = query.exists()
            break
        messages = list(
            query.select_related("reply_to")
            .prefetch_related("parts")
            .order_by("ingest_seq")[
                :min(ANALYSIS_CHUNK_SIZE, message_limit - processed)
            ]
        )
        if not messages:
            if offset is not None:
                raise ValueError(
                    "The original message for the saved fragment "
                    "is unavailable."
                )
            break
        next_offset = None
        if getattr(settings, "CHAT_ANALYSIS_LLM_ENABLED", False):
            if offset is None:
                try:
                    messages = _messages_for_model(job, messages)
                except MessageExceedsBudget:
                    offset = 0
            if offset is not None:
                body = " / ".join(_message_texts(messages[0]))
                digest = sha256(body.encode("utf-8")).hexdigest()
                if checkpoint.get("fragment_digest", digest) != digest:
                    raise RuntimeError(
                        "The original message changed after analysis started."
                    )
                fragment, next_offset = _message_fragment(
                    job, messages[0], offset, body
                )
                messages = [fragment]
        elif offset is not None:
            raise RuntimeError(
                "Continuing a fragmented message requires the LLM."
            )

        job = renew_analysis_lease(
            job,
            worker_id=job.lease_owner,
            fencing_token=job.fencing_token,
            lease_seconds=lease_seconds,
        )
        summary, events = None, None
        if (
            not settings.CHAT_ANALYSIS_LLM_ENABLED
            or not Note.objects.filter(
                space=job.space,
                note_key=_chunk_note_key(job, messages),
                origin=Note.Origin.MANUAL,
            ).exists()
        ):
            summary, events = _prepare_chunk(job, messages)
        with transaction.atomic():
            locked = _lock_job(job.pk)
            _ensure_lease(locked, job.lease_owner, job.fencing_token)
            written, chunk_partial = _write_chunk_note(
                job, messages, summary, events
            )
            if chunk_partial and offset is not None:
                raise RuntimeError(
                    "The model returned an incomplete message fragment."
                )
            if scheduled_scope and chunk_partial:
                partial = True
                break
            partial = partial or chunk_partial
            notes_written += int(written)
            if next_offset is None:
                messages_processed += len(messages)
                last_seq = messages[-1].ingest_seq
                if scheduled_scope:
                    AnalysisJobMessage.objects.filter(
                        job=job,
                        message__in=messages,
                        completed_at__isnull=True,
                    ).update(completed_at=timezone.now())
            checkpoint = {
                "last_ingest_seq": last_seq,
                "messages_processed": messages_processed,
                "notes_written": notes_written,
                "partial": partial,
            }
            if next_offset is not None:
                checkpoint.update(
                    fragment_seq=messages[0].ingest_seq,
                    fragment_offset=next_offset,
                    fragment_digest=digest,
                )
            job = renew_analysis_lease(
                job,
                worker_id=job.lease_owner,
                fencing_token=job.fencing_token,
                lease_seconds=lease_seconds,
                checkpoint=checkpoint,
            )
            chunks_processed += 1

    incomplete = (
        not yielded
        and scheduled_scope
        and (
            AnalysisJobMessage.objects.filter(
                job=job, completed_at__isnull=True
            ).exists()
        )
    )
    if _defer_event_publication(job) and not incomplete and not yielded:
        if (job.specification or {}).get("boundary"):
            checkpoint["event_map_ready"] = True
        else:
            try:
                _publish_reduced_events(job, lease_seconds)
            except AnalysisBatchYield:
                yielded = True
            checkpoint = AnalysisJob.objects.values_list(
                "checkpoint", flat=True,
            ).get(pk=job.pk)

    if incomplete:
        partial = True

    return {
        "checkpoint": checkpoint,
        "yielded": yielded,
        "partial": partial,
        "result_ref": {
            "messages_processed": messages_processed,
            "notes_written": notes_written,
            "last_ingest_seq": last_seq,
        },
    }
