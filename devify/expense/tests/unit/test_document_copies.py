"""Repeated forwards must not repeat files in detail or export."""

from types import SimpleNamespace

import pytest

from expense.services.invoices import unique_documents

pytestmark = pytest.mark.unit


def document(pk, md5="", path=""):
    return SimpleNamespace(
        pk=pk,
        email_attachment=SimpleNamespace(content_md5=md5, file_path=path),
        source_file=None,
    )


def test_repeated_primary_and_alternate_formats_are_shown_once():
    primary = document(1, "ofd")
    pdf = document(2, "pdf")
    xml = document(3, "xml")
    itinerary = document(4, "itinerary")
    copies = [pdf, xml, itinerary, document(5, "ofd"), document(6, "pdf")]

    assert unique_documents(copies, primary) == [pdf, xml, itinerary]


def test_paths_deduplicate_when_hash_is_missing():
    first = document(1, path="/files/invoice.pdf")
    copies = [first, document(2, path="/files/invoice.pdf")]
    assert unique_documents(copies) == [first]


def test_documents_without_files_keep_separate_identities():
    copies = [document(1), document(2)]
    assert unique_documents(copies) == copies
