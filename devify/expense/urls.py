"""Expense API URLs."""

from django.urls import path

from expense.views import (
    ExpenseConfigAPIView,
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
]
