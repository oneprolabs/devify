"""
Invoice routing node for email processing.

An invoice notification is a document delivery, not a conversation, and
summarizing it produces something nobody reads. This node recognizes the
invoices in place, so one email costs one pass and one credit instead of a
generic summary now and a separate recognition later.

If nothing in the email turns out to be an invoice the node changes
nothing, and the workflow carries on down the normal path on the same
charge. That fallback is what makes a wrong guess survivable.
"""

import logging

from threadline.agents.email_state import EmailState
from threadline.agents.nodes.base_node import BaseLangGraphNode

logger = logging.getLogger(__name__)

# How many invoices to name in the summary before summarizing the rest.
SUMMARY_LINE_LIMIT = 5


class InvoiceNode(BaseLangGraphNode):
    progress_stage = "invoice"

    """
    Recognize invoices attached to or linked from this email.

    State Input Requirements:
    - id: Email message id

    Responsibilities:
    - Decide, without spending anything, whether this is an invoice email
    - Recognize the invoices without charging again
    - Write what was found as the summary, so the email record says
      something true instead of a generic paraphrase
    - Leave the state untouched when nothing was found, so the workflow
      falls back to normal processing
    """

    def __init__(self):
        super().__init__("invoice_node")

    def execute_processing(self, state: EmailState) -> EmailState:
        # Deferred: the expense services pull the decoders, and a mailbox
        # with the app switched off should never pay that import cost.
        from expense.services.recognition import recognize_email
        from expense.services.routing import should_route_to_invoices
        from threadline.models import EmailMessage

        state["invoice_count"] = 0
        email = EmailMessage.objects.get(id=state.get("id"))
        attachments = list(email.attachments.all())

        if not should_route_to_invoices(email, attachments):
            self._record_progress_step(
                self.workflow_stage,
                "INVOICE_SKIP",
                "Not an invoice email",
                state=state,
                ratio=1.0,
            )
            return state

        # The workflow has already charged for this email, so recognition
        # must not charge for it a second time.
        stats = recognize_email(email, bill=False)
        found = stats.get("extracted", 0)

        if not found:
            logger.info(
                "Email %s looked like an invoice but held none; "
                "falling back to normal processing",
                email.id,
            )
            self._record_progress_step(
                self.workflow_stage,
                "INVOICE_NONE",
                "No invoice found, continuing normally",
                state=state,
                ratio=1.0,
            )
            return state

        state["invoice_count"] = found
        state["summary_title"] = self._title(found)
        state["summary_content"] = self._content(email)
        self._record_progress_step(
            self.workflow_stage,
            "INVOICE_DONE",
            f"Recognized {found} invoices",
            state=state,
            ratio=1.0,
        )
        return state

    def _title(self, found: int) -> str:
        return f"发票 · {found} 张"

    def _content(self, email) -> str:
        """
        State the facts rather than paraphrase them.

        The seller, the amount and the date are the only things anyone
        wants from this email, and they are now known exactly, so writing
        them down beats asking a model to describe the notification.
        """
        from expense.models import Invoice

        rows = list(
            Invoice.objects.filter(
                email_message=email, status=Invoice.Status.EXTRACTED
            ).order_by("expense_date", "id")
        )

        lines = []
        for invoice in rows[:SUMMARY_LINE_LIMIT]:
            spent_on = invoice.expense_date or invoice.issue_date
            lines.append(
                "%s · %s · ¥%s"
                % (
                    spent_on.isoformat() if spent_on else "日期未知",
                    invoice.seller_name or "销售方未识别",
                    invoice.total_amount,
                )
            )
        if len(rows) > SUMMARY_LINE_LIMIT:
            lines.append(f"…… 另有 {len(rows) - SUMMARY_LINE_LIMIT} 张")

        total = sum(
            (invoice.total_amount or 0) for invoice in rows
        )
        lines.append(f"合计 ¥{total}，已归入发票管家。")
        return "\n".join(lines)


def route_after_invoice(state: EmailState) -> str:
    """
    Continue normally unless the invoices were actually found.

    Everything that can go wrong - not an invoice email, a wrong guess, a
    failed read - leaves the count at zero and lands here, so the fallback
    needs no separate error path.
    """
    return (
        "workflow_finalize"
        if state.get("invoice_count")
        else "image_intent"
    )
