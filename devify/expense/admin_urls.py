"""Expense admin API URLs."""

from django.urls import path

from expense.views import ExpenseAdminConfigAPIView


urlpatterns = [
    path(
        "expense/config",
        ExpenseAdminConfigAPIView.as_view(),
        name="expense-admin-config",
    ),
]
