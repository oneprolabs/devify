"""Expense API URLs."""

from django.urls import path

from expense.views import ExpenseConfigAPIView


urlpatterns = [
    path(
        "apps/expense/config",
        ExpenseConfigAPIView.as_view(),
        name="expense-config",
    ),
]
