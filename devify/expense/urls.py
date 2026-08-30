"""Expense API URLs."""

from django.urls import path

from expense.views import (
    ExpenseConfigAPIView,
    ExpenseInvoiceDetailAPIView,
    ExpenseInvoiceFileAPIView,
    ExpenseInvoiceListAPIView,
    ExpenseInvoiceReextractAPIView,
    ExpenseLinkAllowAPIView,
    ExpenseLinkListAPIView,
    ExpenseScanAPIView,
    ExpenseScanPreviewAPIView,
    ExpenseScanRunDetailAPIView,
    ExpenseScanRunListAPIView,
)


urlpatterns = [
    path(
        "apps/expense/config",
        ExpenseConfigAPIView.as_view(),
        name="expense-config",
    ),
    path(
        "apps/expense/scan",
        ExpenseScanAPIView.as_view(),
        name="expense-scan",
    ),
    path(
        "apps/expense/scan/preview",
        ExpenseScanPreviewAPIView.as_view(),
        name="expense-scan-preview",
    ),
    path(
        "apps/expense/scan-runs",
        ExpenseScanRunListAPIView.as_view(),
        name="expense-scan-runs",
    ),
    path(
        "apps/expense/scan-runs/<uuid:uuid>",
        ExpenseScanRunDetailAPIView.as_view(),
        name="expense-scan-run-detail",
    ),
    path(
        "apps/expense/invoices",
        ExpenseInvoiceListAPIView.as_view(),
        name="expense-invoices",
    ),
    path(
        "apps/expense/invoices/<uuid:uuid>",
        ExpenseInvoiceDetailAPIView.as_view(),
        name="expense-invoice-detail",
    ),
    path(
        "apps/expense/invoices/<uuid:uuid>/reextract",
        ExpenseInvoiceReextractAPIView.as_view(),
        name="expense-invoice-reextract",
    ),
    path(
        "apps/expense/invoices/<uuid:uuid>/file",
        ExpenseInvoiceFileAPIView.as_view(),
        name="expense-invoice-file",
    ),
    path(
        "apps/expense/links",
        ExpenseLinkListAPIView.as_view(),
        name="expense-links",
    ),
    path(
        "apps/expense/links/<uuid:uuid>/allow",
        ExpenseLinkAllowAPIView.as_view(),
        name="expense-link-allow",
    ),
]
