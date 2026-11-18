"""Asynchronous grounded question answering."""

import logging

from celery import shared_task
from django.db.models import Q

from chat_analysis.models import QuestionAnswer
from chat_analysis.topic_services import answer_question

logger = logging.getLogger(__name__)

MODEL_FAILURE_MESSAGE = "回答生成失败，请稍后重试。"


def _failure_message(error):
    """Hide provider error dumps from users; they stay in the worker log."""
    if type(error).__module__.split(".")[0] in {"litellm", "openai"}:
        return MODEL_FAILURE_MESSAGE
    return str(error)[:2000]


def prior_question_turns(question, limit=6):
    """Earlier ready answers in the same thread, oldest first."""
    root_id = question.thread_id or question.pk
    rows = (
        QuestionAnswer.objects.filter(
            space_id=question.space_id,
            created_by_id=question.created_by_id,
        )
        .filter(Q(pk=root_id) | Q(thread_id=root_id))
        .exclude(pk=question.pk)
        .order_by("created_at", "id")
    )
    turns = []
    for item in rows:
        if (
            item.status != QuestionAnswer.Status.READY
            or not item.answer.strip()
        ):
            continue
        turns.append(
            {"question": item.question, "answer": item.answer[:1200]}
        )
    return turns[-limit:]


@shared_task(bind=True, max_retries=0)
def answer_question_task(self, question_id):
    question = QuestionAnswer.objects.select_related(
        "space", "created_by"
    ).get(pk=question_id)
    if question.status != QuestionAnswer.Status.QUEUED:
        return {"question_id": question.pk, "status": question.status}
    try:
        result = answer_question(
            actor=question.created_by,
            space=question.space,
            question=question.question,
            prior_turns=prior_question_turns(question),
            **question.scope,
        )
    except Exception as error:
        logger.exception("Question %s failed", question.pk)
        question.status = QuestionAnswer.Status.FAILED
        question.error = _failure_message(error)
        question.save(update_fields=("status", "error", "updated_at"))
        return {"question_id": question.pk, "status": question.status}
    question.answer = result["answer"]
    question.citations = result.get("citations", [])
    question.scope = result.get("scope", question.scope)
    question.usage = result.get("usage", {})
    question.status = QuestionAnswer.Status.READY
    question.save(
        update_fields=(
            "answer",
            "citations",
            "scope",
            "usage",
            "status",
            "updated_at",
        )
    )
    return {"question_id": question.pk, "status": question.status}


def dispatch_question_answer(question):
    return answer_question_task.delay(question.pk)
