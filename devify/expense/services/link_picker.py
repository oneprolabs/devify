"""
Choose which links in an email actually fetch an invoice.

Structure gets us most of the way - a decoration the mail client renders
is never the invoice - but it cannot separate 「下载发票」 from an
advertisement, because both are anchors a person could click. That reading
is what a model is for, and it is cheap: a list of addresses and the words
they were shown as, no document content, answered by the text model.

Failure is open. Missing a real invoice is worse than fetching a page that
turns out to be an advert, so anything unexpected leaves every link in
place and the fetcher's own checks decide.
"""

from __future__ import annotations

import logging

from core.tracking import LLMTracker

from expense.prompts import LINK_PICK_PROMPT
from threadline.utils.llm import parse_json_response

logger = logging.getLogger(__name__)

NODE_NAME = "expense_link_pick"

# Enough to cover a marketing footer without turning the prompt into a
# document in its own right.
MAX_LINKS = 25


def render_links(anchors: list[dict]) -> str:
    return "\n".join(
        "%d. %s  <%s>" % (index, anchor.get("text") or "(no text)",
                          anchor.get("url", ""))
        for index, anchor in enumerate(anchors)
    )


def pick_invoice_links(subject: str, anchors: list[dict], model_uuid) -> list:
    """Return the anchors worth fetching, in their original order."""
    if not anchors:
        return []
    if not model_uuid:
        return anchors

    shortlist = anchors[:MAX_LINKS]
    prompt = LINK_PICK_PROMPT.format(
        subject=(subject or "")[:200], links=render_links(shortlist)
    )

    try:
        response, _usage = LLMTracker.call_messages_and_track(
            messages=[{"role": "user", "content": prompt}],
            json_mode=True,
            node_name=NODE_NAME,
            model_uuid=str(model_uuid),
        )
        if isinstance(response, str):
            response = parse_json_response(response)
        if not isinstance(response, dict):
            raise ValueError("model did not return an object")

        chosen = response.get("invoice_links")
        if not isinstance(chosen, list):
            raise ValueError("invoice_links missing")
    except Exception as exc:
        logger.warning(
            "Link selection failed (%s); following every link", exc
        )
        return anchors

    picked = []
    for index in chosen:
        try:
            picked.append(shortlist[int(index)])
        except (TypeError, ValueError, IndexError):
            continue

    logger.info(
        "Link selection kept %d of %d links", len(picked), len(shortlist)
    )
    return picked
