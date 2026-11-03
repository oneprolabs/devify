"""One end-to-end chain over the real HTTP surface.

upload → parse → Note + evidence → Event suggestion → accepted Event →
report → question with citations, plus the "import succeeded, analysis
failed" branch that the product must keep recoverable.

External services stay mocked: the archive comes from the shared fixture and
the LLM tracker is replaced with a deterministic stand-in, so the test is
about the chain and its data links, not about a provider.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from chat_analysis.execution import AnalysisJobRejected
from chat_analysis.models import (
    AnalysisJob,
    Event,
    EventNote,
    EventSuggestion,
    QuestionAnswer,
    Report,
)
from chat_domain.models import Conversation, Message, MessageOrigin
from chat_ingestion.models import UploadBatch
from chat_ingestion.tests.archives import build_archive
from core.tracking import LLMTracker
from spaces.models import Space, SpaceMembership

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

EVENT_KEY = "quote-risk"


@pytest.fixture(autouse=True)
def chain(settings, tmp_path):
    settings.CHAT_UPLOAD_ARCHIVE_DIR = str(tmp_path / "chat_archives")
    settings.CHAT_UPLOAD_PARSE_INLINE = True
    settings.CHAT_UPLOAD_ANALYSIS_INLINE = True
    settings.CHAT_ANALYSIS_LLM_ENABLED = True
    settings.CHAT_ANALYSIS_AUTO_CREATE_EVENTS = False


@pytest.fixture
def llm(monkeypatch):
    """Deterministic stand-in for every node in the chain."""

    state = {"event_id": None}

    def call_and_track(*, node_name, **_kwargs):
        if node_name == "chat_note_structuring":
            return {"facts": [{"text": "客户要求降价百分之十"}]}, {
                "model": "test-model"
            }
        if node_name == "chat_event_extraction":
            return {
                "events": [
                    {
                        "event_key": EVENT_KEY,
                        "title": "报价风险",
                        "summary": "客户要求降价百分之十，等待确认。",
                        "status": "open",
                        "source_seqs": [1],
                        "tags": ["customer"],
                    }
                ]
            }, {"model": "test-model"}
        if node_name == "chat_report_generation":
            return {
                "body": "# 周报\n\n报价风险仍在等待确认。",
                "sections": [
                    {
                        "section_key": "risks",
                        "title": "风险",
                        "items": [
                            {
                                "title": "报价风险",
                                "summary": "客户要求降价百分之十。",
                            }
                        ],
                    }
                ],
            }, {"model": "test-model"}
        if node_name == "chat_question_answering":
            return {
                "answer": "有一条未完成的报价风险。",
                "citations": [
                    {
                        "kind": "event",
                        "id": state["event_id"],
                        "title": "报价风险",
                        "excerpt": "等待确认",
                    }
                ],
            }, {"model": "test-model"}
        raise AssertionError(f"unexpected LLM node {node_name}")

    monkeypatch.setattr(LLMTracker, "call_and_track", call_and_track)
    return state


def make_space(owner, slug="e2e-chain-team"):
    space = Space.objects.create(
        name=slug, slug=slug, kind=Space.Kind.TEAM, owner=owner
    )
    SpaceMembership.objects.create(
        space=space, user=owner, role=SpaceMembership.Role.OWNER
    )
    return space


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def upload_and_complete(client, space, key="e2e-chain"):
    created = client.post(
        f"/api/v1/spaces/{space.pk}/chat/uploads",
        {"source_type": "wechat", "idempotency_key": key},
        format="json",
    )
    assert created.status_code == 201
    batch = UploadBatch.objects.get(pk=created.data["data"]["id"])
    uploaded = client.put(
        f"/api/v1/chat/uploads/{batch.pk}/archive",
        {
            "archive": SimpleUploadedFile(
                "package.zip", build_archive(), content_type="application/zip"
            )
        },
        format="multipart",
    )
    assert uploaded.status_code == 200
    completed = client.post(f"/api/v1/chat/uploads/{batch.pk}/complete")
    assert completed.status_code == 200, completed.data
    batch.refresh_from_db()
    return batch


def test_upload_parse_note_event_report_and_question(monkeypatch, llm):
    owner = User.objects.create_user(username="e2e-chain-owner")
    space = make_space(owner)
    client = client_for(owner)

    batch = upload_and_complete(client, space)

    # 1. The package became queryable data with full provenance.
    assert batch.status == UploadBatch.Status.COMPLETED
    assert batch.message_count == 2
    conversation = Conversation.objects.get(space=space)
    assert conversation.message_count == 2
    message = Message.objects.get(
        conversation=conversation, message_key="srv:1"
    )
    origin = MessageOrigin.objects.get(message=message)
    assert origin.upload_item.batch_id == batch.pk

    messages = client.get(
        f"/api/v1/spaces/{space.pk}/conversations/"
        f"{conversation.pk}/messages"
    )
    assert messages.status_code == 200
    assert len(messages.data["data"]["list"]) == 2

    # 2. Rule-based analysis wrote a Note backed by message evidence.
    job = AnalysisJob.objects.get(conversation=conversation)
    assert job.state in (AnalysisJob.State.READY, AnalysisJob.State.PARTIAL)
    note = job.notes.get()
    assert note.evidence.count() == 2
    assert note.structured_data["facts"][0]["text"] == "客户要求降价百分之十"

    # 3. The suggestion is reviewed through the API, not created directly.
    suggestion = EventSuggestion.objects.get(space=space)
    reviewed = client.post(
        f"/api/v1/event-suggestions/{suggestion.pk}/review",
        {"decision": "accepted"},
        format="json",
    )
    assert reviewed.status_code == 200
    event = Event.objects.get(space=space, event_key=EVENT_KEY)
    llm["event_id"] = event.pk
    assert EventNote.objects.filter(event=event, note=note).exists()

    # 4. A report snapshot picks the event up and the page sections match
    #    what the generator returned.
    monkeypatch.setattr(
        "chat_analysis.report_views.transaction.on_commit",
        lambda callback: callback(),
    )
    monkeypatch.setattr(
        "chat_analysis.report_views.dispatch_report_generation",
        lambda report: _run_report(report),
    )
    created = client.post(
        f"/api/v1/spaces/{space.pk}/reports",
        {"request_key": "e2e-chain-report", "title": "周报"},
        format="json",
    )
    assert created.status_code == 202
    report = Report.objects.get(pk=created.data["data"]["id"])
    report.refresh_from_db()
    assert report.status == Report.Status.READY
    assert report.sections.get().section_key == "risks"
    assert report.body.startswith("# 周报")

    detail = client.get(f"/api/v1/reports/{report.pk}")
    assert detail.status_code == 200
    items = detail.data["data"]["sections"][0]["items"]
    assert items[0]["title"] == "报价风险"

    # 5. A question answers from the same data and cites the event.
    monkeypatch.setattr(
        "chat_analysis.api_views.transaction.on_commit",
        lambda callback: callback(),
    )
    monkeypatch.setattr(
        "chat_analysis.api_views.dispatch_question_answer",
        lambda question: _run_question(question),
    )
    asked = client.post(
        f"/api/v1/spaces/{space.pk}/questions",
        {"question": "还有哪些未完成的风险？"},
        format="json",
    )
    assert asked.status_code == 202
    answer = QuestionAnswer.objects.get(pk=asked.data["data"]["id"])
    answer.refresh_from_db()
    assert answer.status == QuestionAnswer.Status.READY
    assert answer.answer == "有一条未完成的报价风险。"
    assert answer.citations == [
        {
            "kind": "event",
            "id": event.pk,
            "title": "报价风险",
            "excerpt": "客户要求降价百分之十，等待确认。",
        }
    ]


def _run_report(report):
    from chat_analysis.report_tasks import generate_report_task

    return generate_report_task.run(report.pk)


def _run_question(question):
    from chat_analysis.question_tasks import answer_question_task

    return answer_question_task.run(question.pk)


def test_import_succeeds_even_when_analysis_fails_and_can_be_retried(
    monkeypatch, llm
):
    owner = User.objects.create_user(username="e2e-chain-retry-owner")
    space = make_space(owner, slug="e2e-chain-retry-team")
    client = client_for(owner)

    from chat_analysis import execution

    healthy = execution.run_rule_based_analysis
    failing = {"on": True}

    def flaky(job, **kwargs):
        if failing["on"]:
            raise AnalysisJobRejected("the source conversation was removed")
        return healthy(job, **kwargs)

    monkeypatch.setattr(execution, "run_rule_based_analysis", flaky)

    batch = upload_and_complete(client, space, key="e2e-chain-retry")

    # Import stands on its own: raw messages stay readable.
    assert batch.status == UploadBatch.Status.COMPLETED
    conversation = Conversation.objects.get(space=space)
    assert Message.objects.filter(conversation=conversation).count() == 2
    listing = client.get(
        f"/api/v1/spaces/{space.pk}/conversations/"
        f"{conversation.pk}/messages"
    )
    assert listing.status_code == 200

    job = AnalysisJob.objects.get(conversation=conversation)
    assert job.state == AnalysisJob.State.FAILED
    assert "removed" in job.error

    # Retrying after the cause is fixed fills in the analysis.
    failing["on"] = False
    from chat_analysis.execution import execute_analysis_job
    from chat_analysis.services import retry_analysis_job

    requeued = retry_analysis_job(actor=owner, job=job)
    execute_analysis_job(requeued.pk, worker_id="test:retry")

    requeued.refresh_from_db()
    assert requeued.state in (
        AnalysisJob.State.READY,
        AnalysisJob.State.PARTIAL,
    )
    assert requeued.notes.exists()
