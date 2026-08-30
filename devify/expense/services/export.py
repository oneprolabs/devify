"""
Package a reimbursement group as a zip with a readable manifest.

Files are written into a temporary archive on disk rather than assembled
in memory, so a large claim cannot take the worker down. The caller
streams that file and deletes it afterwards.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
import zipfile

from django.utils.translation import gettext as _

from expense.constants import (
    CATEGORY_LABELS_CN,
    INVOICE_TYPE_LABELS_CN,
    ExpenseCategory,
)
from expense.models import ExpenseGroupItem
from expense.services import naming

logger = logging.getLogger(__name__)

MAX_FILES = 200
MAX_TOTAL_BYTES = 500 * 1024 * 1024

MANIFEST_NAME = "manifest.csv"
MANIFEST_HEADERS = [
    "序号",
    "开票日期",
    "票种",
    "分类",
    "销售方",
    "城市",
    "价税合计",
    "税额",
    "发票号码",
    "文件名",
]

# Folder names follow the same stable labels as the filenames.
CATEGORY_LABELS = CATEGORY_LABELS_CN


class ExportError(Exception):
    """The group cannot be packaged as requested."""


def group_invoices(group):
    return [
        item.invoice
        for item in ExpenseGroupItem.objects.filter(group=group)
        .select_related(
            "invoice",
            "invoice__email_attachment",
            "invoice__source_file",
        )
        .order_by("sort_order", "id")
    ]


def source_path(invoice) -> str:
    source = invoice.email_attachment or invoice.source_file
    path = getattr(source, "file_path", "") if source else ""
    return path if path and os.path.exists(path) else ""


def plan_export(group, template: str = "", by_category: bool = True):
    """
    Work out every archive entry before writing anything.

    Returning the plan lets the UI preview the exact filenames, which is
    the only way a naming template is reviewable before it is used.
    """
    invoices = group_invoices(group)
    if not invoices:
        raise ExportError(_("This group has no invoices to export."))

    taken: set[str] = set()
    entries = []
    total_bytes = 0
    missing = 0

    for index, invoice in enumerate(invoices, start=1):
        filename = naming.render(invoice, template, taken)
        path = source_path(invoice)
        if not path:
            missing += 1

        size = os.path.getsize(path) if path else 0
        total_bytes += size

        category = invoice.category or ExpenseCategory.OTHER
        folder = CATEGORY_LABELS.get(category, category)
        arcname = f"{folder}/{filename}" if by_category else filename

        entries.append(
            {
                "index": index,
                "invoice": invoice,
                "filename": filename,
                "arcname": arcname,
                "path": path,
                "size": size,
            }
        )

    if len(entries) > MAX_FILES:
        raise ExportError(
            _("A single export is limited to %(count)d files.")
            % {"count": MAX_FILES}
        )
    if total_bytes > MAX_TOTAL_BYTES:
        raise ExportError(
            _("A single export is limited to %(mb)d MB.")
            % {"mb": MAX_TOTAL_BYTES // (1024 * 1024)}
        )

    return {
        "entries": entries,
        "total_bytes": total_bytes,
        "missing_files": missing,
    }


def build_manifest(entries) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(MANIFEST_HEADERS)

    for entry in entries:
        invoice = entry["invoice"]
        category = invoice.category or ExpenseCategory.OTHER
        writer.writerow(
            [
                entry["index"],
                invoice.issue_date.isoformat() if invoice.issue_date else "",
                INVOICE_TYPE_LABELS_CN.get(
                    invoice.invoice_type, invoice.invoice_type
                ),
                CATEGORY_LABELS.get(category, category),
                invoice.seller_name,
                invoice.city,
                invoice.total_amount
                if invoice.total_amount is not None
                else "",
                invoice.tax_amount if invoice.tax_amount is not None else "",
                invoice.invoice_no,
                entry["filename"],
            ]
        )

    return buffer.getvalue()


def write_archive(group, template: str = "", by_category: bool = True) -> str:
    """Build the archive on disk and return its path."""
    plan = plan_export(group, template, by_category)

    handle, archive_path = tempfile.mkstemp(
        prefix="expense_export_", suffix=".zip"
    )
    os.close(handle)

    try:
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            # Excel on Windows reads CSV as the system codepage unless the
            # file starts with a BOM, which mangles Chinese seller names.
            archive.writestr(
                MANIFEST_NAME,
                "﻿" + build_manifest(plan["entries"]),
            )

            for entry in plan["entries"]:
                if not entry["path"]:
                    continue
                archive.write(entry["path"], arcname=entry["arcname"])
    except Exception:
        os.unlink(archive_path)
        raise

    return archive_path
