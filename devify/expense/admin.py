"""Expense admin registrations."""

from django.contrib import admin

from expense.models import (
    CategoryRule,
    ExpenseAppConfig,
    ExpenseGroup,
    ExpenseGroupItem,
    ExpenseUserConfig,
    Invoice,
    InvoiceScanRun,
    InvoiceSourceFile,
    TripSuggestion,
)


@admin.register(ExpenseAppConfig)
class ExpenseAppConfigAdmin(admin.ModelAdmin):
    list_display = ["workflow_key", "scan_schedule", "is_active", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ExpenseUserConfig)
class ExpenseUserConfigAdmin(admin.ModelAdmin):
    list_display = ["user", "enabled", "enabled_at", "last_scanned_at"]
    list_filter = ["enabled"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "uuid",
        "user",
        "invoice_type",
        "seller_name",
        "total_amount",
        "issue_date",
        "category",
        "status",
    ]
    list_filter = ["status", "invoice_type", "category", "needs_review"]
    search_fields = ["invoice_no", "seller_name", "buyer_name", "dedup_key"]
    readonly_fields = ["uuid", "raw_extraction", "created_at", "updated_at"]


@admin.register(InvoiceSourceFile)
class InvoiceSourceFileAdmin(admin.ModelAdmin):
    list_display = ["uuid", "user", "source_url", "fetch_status", "created_at"]
    list_filter = ["fetch_status"]
    search_fields = ["source_url", "content_md5"]
    readonly_fields = ["uuid", "created_at"]


@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "match_type",
        "match_value",
        "category",
        "hit_count",
    ]
    list_filter = ["match_type", "category", "created_from"]
    search_fields = ["match_value"]


class ExpenseGroupItemInline(admin.TabularInline):
    model = ExpenseGroupItem
    extra = 0


@admin.register(ExpenseGroup)
class ExpenseGroupAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "status",
        "trip_type",
        "invoice_count",
        "total_amount",
    ]
    list_filter = ["status", "trip_type"]
    search_fields = ["name", "external_ref", "user__username"]
    readonly_fields = ["uuid", "created_at", "updated_at"]
    inlines = [ExpenseGroupItemInline]


@admin.register(TripSuggestion)
class TripSuggestionAdmin(admin.ModelAdmin):
    list_display = [
        "destination_city",
        "user",
        "start_date",
        "end_date",
        "total_amount",
        "status",
    ]
    list_filter = ["status"]
    readonly_fields = ["uuid", "created_at", "updated_at"]


@admin.register(InvoiceScanRun)
class InvoiceScanRunAdmin(admin.ModelAdmin):
    list_display = [
        "uuid",
        "user",
        "trigger",
        "status",
        "candidate_emails",
        "invoices_created",
        "credits_consumed",
        "started_at",
    ]
    list_filter = ["trigger", "status"]
    readonly_fields = ["uuid", "started_at", "details"]
