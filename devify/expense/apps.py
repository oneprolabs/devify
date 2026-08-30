"""Django app config for Expense."""

from django.apps import AppConfig


class ExpenseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "expense"
    verbose_name = "Expense"

    def ready(self):
        from core.app_registry import APP_REGISTRY

        APP_REGISTRY.register(
            key="expense",
            name="Expense",
            name_zh="发票管家",
            path="/apps/expense",
            description=(
                "Collect invoices from email, classify them and package "
                "them for reimbursement."
            ),
        )
