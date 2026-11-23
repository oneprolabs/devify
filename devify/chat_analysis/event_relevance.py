"""Ground participant evidence and project shared events for a viewer."""

import re
from collections import defaultdict
from hashlib import sha256

from django.db.models import F, Q

from chat_analysis.models import (
    Event,
    EventEvidence,
    EventParticipantEvidence,
    EventSuggestion,
)
from chat_domain.models import (
    Conversation,
    ConversationIdentity,
    Message,
    MessageOrigin,
)
from chat_ingestion.models import UploadBatch

MAX_UPDATES = 12
MAX_ACTION_CONTEXT = 12
MAX_VIEWER_EVIDENCE = 20
ACKNOWLEDGMENTS = frozenset({"1", "收到", "好的", "ok", "嗯", "知道了"})
# A request to another participant can end with the sender's own handoff.
_HANDOFF = re.compile(
    r"^@\S{1,80}\s+[^。！？?!\n]*?(?:帮我|麻烦|请)[^。！？?!\n]+?"
    r"(?:吧\s+|[，,；;]\s*)"
    r"(?P<quote>我(?:会|将|来)?(?P<action>(?:转发|发送|发)给"
    r"\s*[\w-]{1,40}))\s*[。.!！]?$"
)


def _open_actions(records):
    completed = {
        item["reference"] for item in records if item["state"] == "done"
    }
    return {
        item["reference"]: item
        for item in records
        if item["state"] == "open" and item["reference"] not in completed
    }


def add_action_context(job, candidates):
    """Load unfinished actions for the events already in the prompt."""
    if not candidates:
        return {}
    keys = {item["event_key"] for item in candidates}
    records = defaultdict(list)
    rows = (
        EventParticipantEvidence.objects.filter(
            Q(
                suggestion__event__space_id=job.space_id,
                suggestion__event__event_key__in=keys,
                suggestion__status=EventSuggestion.Status.ACCEPTED,
            )
            | Q(
                suggestion__analysis_job=job,
                suggestion__event_key__in=keys,
                suggestion__status=EventSuggestion.Status.PENDING,
            ),
            message__orphaned_at__isnull=True,
        )
        .order_by("id")
        .values(
            "suggestion__event__event_key",
            "suggestion__event_key",
            "reference",
            "action",
            "state",
            "sender_key",
            "sender_name",
            conversation_id=F("message__conversation_id"),
            occurred_at=F("message__occurred_at"),
        )
    )
    for item in rows:
        key = (
            item["suggestion__event__event_key"]
            or item["suggestion__event_key"]
        )
        records[key].append(item)
    by_event = {}
    for candidate in candidates:
        key = candidate["event_key"]
        actions = list(_open_actions(records[key]).values())[
            :MAX_ACTION_CONTEXT
        ]
        if actions:
            candidate["open_actions"] = [
                {
                    "ref": item["reference"],
                    "action": item["action"],
                    "person": item["sender_name"],
                }
                for item in actions
            ]
            by_event[key] = {item["reference"]: item for item in actions}
    return by_event


def _named_in_quote(quote, name):
    # Match a delimited name, including ordinary @mentions.
    return bool(
        name
        and re.search(
            r"(?<!\w)" + re.escape(name) + r"(?=$|\W)",
            quote,
        )
    )


def _unique_named_sender(source, name):
    keys = list(
        Message.objects.filter(
            conversation_id=source.conversation_id,
            sender_name=name,
        )
        .exclude(sender_key="")
        .order_by()
        .values_list(
            "sender_key",
            flat=True,
        )
        .distinct()[:2]
    )
    return keys[0] if len(keys) == 1 else ""


def _grounded_person(source, sender_key, name, link, quote, named_sender):
    if not sender_key:
        return False
    if link in ("speaker", "commitment"):
        return source.sender_key == sender_key
    if link == "reply":
        reply = source.reply_to
        return bool(
            reply
            and reply.conversation_id == source.conversation_id
            and reply.sender_key == sender_key
        )
    if link == "direct":
        if source.conversation.kind != Conversation.Kind.DIRECT:
            return False
        participants = set(
            Message.objects.filter(
                conversation_id=source.conversation_id,
                orphaned_at__isnull=True,
            )
            .exclude(sender_key="")
            .order_by()
            .values_list(
                "sender_key",
                flat=True,
            )
            .distinct()[:3]
        )
        return source.sender_key != sender_key and participants == {
            sender_key,
            source.sender_key,
        }
    return (
        link == "name"
        and _named_in_quote(quote, name)
        and named_sender(source, name) == sender_key
    )


def resolve_participant_evidence(
    updates,
    messages,
    cited,
    roles,
    texts,
    actions,
    *,
    recover_handoffs=False,
):
    """Resolve model references against cited text in this chunk."""
    if not isinstance(updates, list):
        return []
    by_seq = {message.ingest_seq: message for message in messages}
    cited_by_seq = {message.ingest_seq: message for message in cited}
    confirmations = {
        message.ingest_seq
        for message, role in zip(cited, roles)
        if role == "confirmation"
    }
    named_senders = {}

    def named_sender(source, name):
        if name not in named_senders:
            named_senders[name] = _unique_named_sender(source, name)
        return named_senders[name]

    results = []
    for update in updates[:MAX_UPDATES]:
        if not isinstance(update, dict) or type(update.get("seq")) is not int:
            continue
        source = cited_by_seq.get(update["seq"])
        quote = update.get("quote")
        state = update.get("state")
        if source is None or not isinstance(quote, str):
            continue
        text_parts = texts(source)
        normalized_quote = " ".join(quote.split())
        if (
            len(normalized_quote) < 2
            or len(quote.strip()) > 280
            or not any(
                normalized_quote in " ".join(text.split())
                for text in text_parts
            )
            or state not in ("open", "done", "related")
        ):
            continue
        ref = update.get("ref")
        link = update.get("link")
        if update["seq"] in confirmations or all(
            text.strip(" .!。！").casefold() in ACKNOWLEDGMENTS
            for text in text_parts
        ):
            if ref:
                continue
            state = "related"
        if state == "open" and link == "speaker":
            state = "related"
        previous = actions.get(ref) if isinstance(ref, str) and ref else None
        if ref and (state != "done" or previous is None):
            continue
        if previous is not None:
            if (
                previous["conversation_id"] != source.conversation_id
                or not source.occurred_at
                or not previous["occurred_at"]
                or source.occurred_at < previous["occurred_at"]
            ):
                continue
            person = previous["sender_key"]
            name = previous["sender_name"]
        else:
            seq = update.get("person_seq")
            participant = by_seq.get(seq) if type(seq) is int else None
            name = update.get("name")
            if link == "name" and isinstance(name, str) and name:
                if not 1 <= len(name) <= 255 or not _named_in_quote(
                    quote, name
                ):
                    continue
                person = named_sender(source, name)
            elif participant is not None:
                person, name = participant.sender_key, participant.sender_name
            elif link == "commitment" and seq is None:
                person, name = source.sender_key, source.sender_name
            elif link == "reply" and source.reply_to_id:
                person = source.reply_to.sender_key
                name = source.reply_to.sender_name
            else:
                continue
        if not _grounded_person(
            source,
            person,
            name,
            link,
            quote,
            named_sender,
        ):
            continue
        action = update.get("action")
        if state == "open":
            if not isinstance(action, str) or not action.strip():
                continue
            action = action.strip()[:160]
            if any(
                item["sender_key"] == person
                and item["conversation_id"] == source.conversation_id
                and item["action"].casefold() == action.casefold()
                for item in actions.values()
            ):
                continue
            digest = sha256(
                f"{person}\0{action.casefold()}".encode()
            ).hexdigest()
            ref = f"{source.pk}-{digest[:12]}"
        results.append(
            {
                "state": state,
                "reference": ref or "",
                "sender_key": person,
                "sender_name": name,
                "action": action if state == "open" else "",
                "message_id": source.pk,
            }
        )
    if recover_handoffs and len(results) < MAX_UPDATES:
        handoffs = _missing_handoffs(cited, confirmations, texts, results)
        if handoffs:
            results.extend(resolve_participant_evidence(
                handoffs[:MAX_UPDATES - len(results)], messages,
                cited, roles, texts, actions,
            ))
    return results


def _missing_handoffs(cited, confirmations, texts, updates):
    handoffs = []
    for source in cited:
        if (
            not source.sender_key or source.ingest_seq in confirmations
            or hasattr(source, "analysis_fragment_offset")
            or any(
                item["sender_key"] == source.sender_key
                and (
                    item["state"] == "done"
                    or item["state"] == "open"
                    and item["message_id"] == source.pk
                )
                for item in updates
            )
        ):
            continue
        for text in texts(source):
            text = text.strip()
            if len(text) > 280:
                continue
            match = _HANDOFF.fullmatch(text)
            if match and not match["action"].endswith(
                ("了", "过", "吗", "么", "吧", "呢", "啦", "嘛")
            ):
                handoffs.append({
                    "seq": source.ingest_seq,
                    "quote": match["quote"],
                    "link": "commitment",
                    "state": "open",
                    "action": match["action"],
                })
                break
    return handoffs


def legacy_identity_origins(user_id):
    """Find the viewer's outgoing identities from verified old imports."""
    return MessageOrigin.objects.filter(
        message__direction=Message.Direction.OUTGOING,
        message__orphaned_at__isnull=True,
        upload_item__batch__uploaded_by_id=user_id,
        upload_item__batch__space_id=F("message__conversation__space_id"),
        upload_item__batch__status=UploadBatch.Status.COMPLETED,
        upload_item__batch__source_type=F("message__conversation__platform"),
        upload_item__batch__source_account_id=F("message__sender_key"),
    ).exclude(message__sender_key="")


def event_relevance(events, user_id):
    """Return labels and original evidence IDs for one page of Events."""
    event_ids = [event.pk for event in events]
    evidence = defaultdict(dict)
    for event_id, message_id, conversation_id, sender_key in (
        EventEvidence.objects.filter(
            event_id__in=event_ids,
            message__orphaned_at__isnull=True,
        )
        .values_list(
            "event_id",
            "message_id",
            "message__conversation_id",
            "message__sender_key",
        )
        .order_by("id")
    ):
        evidence[event_id][message_id] = (conversation_id, sender_key)
    if not evidence:
        return {}

    conversation_ids = {
        conversation_id
        for items in evidence.values()
        for conversation_id, _ in items.values()
    }
    identities = set(
        ConversationIdentity.objects.filter(
            user_id=user_id,
            conversation_id__in=conversation_ids,
        ).values_list("conversation_id", "sender_key")
    )
    missing = conversation_ids - {
        conversation_id for conversation_id, _ in identities
    }
    if missing:
        # Old exports can establish the same identity via their completed
        # batch's source account and an exact outgoing sender key.
        identities.update(
            legacy_identity_origins(user_id)
            .filter(message__conversation_id__in=missing)
            .order_by()
            .values_list(
                "message__conversation_id",
                "message__sender_key",
            )
            .distinct()
        )
    if not identities:
        return {}

    updates = defaultdict(list)
    rows = (
        EventParticipantEvidence.objects.filter(
            suggestion__event_id__in=event_ids,
            suggestion__status=EventSuggestion.Status.ACCEPTED,
            sender_key__in={key for _, key in identities},
            message__orphaned_at__isnull=True,
        )
        .order_by("id")
        .values(
            "suggestion__event_id",
            "message_id",
            "sender_key",
            "state",
            "reference",
        )
    )
    for item in rows:
        event_id = item["suggestion__event_id"]
        message = evidence[event_id].get(item["message_id"])
        if message and (message[0], item["sender_key"]) in identities:
            updates[event_id].append(item)

    result = {}
    for event in events:
        items = updates[event.pk]
        pending = (
            _open_actions(items) if event.status != Event.Status.DONE else {}
        )
        if pending:
            ids = list(
                dict.fromkeys(item["message_id"] for item in pending.values())
            )
            result[event.pk] = ("my_todo", ids[:MAX_VIEWER_EVIDENCE])
            continue
        ids = list(
            dict.fromkeys(
                [item["message_id"] for item in items]
                + [
                    message_id
                    for message_id, identity in evidence[event.pk].items()
                    if identity in identities
                ]
            )
        )
        if ids:
            result[event.pk] = ("related", ids[:MAX_VIEWER_EVIDENCE])
    return result
