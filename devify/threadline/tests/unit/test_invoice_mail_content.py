"""Keep invoice links and receipt dates available to the workflow."""

from email.message import EmailMessage

import pytest

from threadline.agents.nodes.summary_node import SummaryNode
from threadline.utils.email.parsers.enhanced import EmailFlankerParser


@pytest.mark.unit
@pytest.mark.parametrize(
    "subtype,multipart", [("html", False), ("plain", False), ("html", True)]
)
def test_invoice_body_survives_mime_parsing(tmp_path, subtype, multipart):
    message = EmailMessage()
    message["Subject"] = "Electronic invoice"
    message["From"] = "billing@example.com"
    message["To"] = "customer@example.com"
    message["Date"] = "Wed, 21 Oct 2026 12:44:05 +0800"
    url = "https://invoices.example.com/download?format=PDF&number=123"
    body = (
        f'<a href="{url}">Download invoice</a>' if subtype == "html" else url
    )
    message.set_content(body, subtype=subtype)
    if multipart:
        message.add_attachment(
            b"%PDF-1.4",
            maintype="application",
            subtype="pdf",
            filename="invoice.pdf",
        )

    parsed = EmailFlankerParser(str(tmp_path)).parse_from_bytes(
        message.as_bytes()
    )

    assert parsed is not None
    if subtype == "html":
        assert url in parsed["html_content"]
        assert "Download invoice" in parsed["text_content"]
    else:
        assert url in parsed["text_content"]
    assert len(parsed["attachments"]) == int(multipart)


@pytest.mark.unit
def test_summary_distinguishes_receipt_date_from_processing_time():
    context = SummaryNode()._build_prompt_context(
        {
            "subject": "Invoice notification",
            "llm_content": "Invoice 123",
            "received_at": "2026-10-21T04:44:05+00:00",
            "user_timezone": "Asia/Shanghai",
        }
    )

    assert "Received at: 2026-10-21T04:44:05+00:00" in context
    assert "not the receipt date" in context
