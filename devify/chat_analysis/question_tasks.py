"""Asynchronous grounded question answering."""

from celery import shared_task

from chat_analysis.models import QuestionAnswer
from chat_analysis.topic_services import answer_question


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
            **question.scope,
        )
    except Exception as error:
        question.status = QuestionAnswer.Status.FAILED
        question.error = str(error)[:2000]
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
