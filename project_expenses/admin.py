from django.contrib import admin

from .models import (
    ApprovalLimit,
    EmployeeAdvance,
    ExpenseApprovalHistory,
    ExpenseCategory,
    LedgerTransaction,
    PeamsSettings,
    ProjectExpense,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('code', 'name')


@admin.register(PeamsSettings)
class PeamsSettingsAdmin(admin.ModelAdmin):
    list_display = ('director_approval_threshold', 'default_currency', 'updated_at')


@admin.register(ApprovalLimit)
class ApprovalLimitAdmin(admin.ModelAdmin):
    list_display = (
        'step_code', 'step_order', 'min_amount', 'max_amount',
        'can_approve_up_to', 'is_active',
    )
    list_filter = ('step_code', 'is_active')


class ApprovalInline(admin.TabularInline):
    model = ExpenseApprovalHistory
    extra = 0
    readonly_fields = ('action', 'step_code', 'from_status', 'to_status', 'remarks', 'acted_by', 'acted_at')


@admin.register(EmployeeAdvance)
class EmployeeAdvanceAdmin(admin.ModelAdmin):
    list_display = (
        'advance_number', 'advance_date', 'employee', 'amount', 'status', 'special_project',
    )
    list_filter = ('status',)
    search_fields = ('advance_number', 'purpose')


@admin.register(ProjectExpense)
class ProjectExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'expense_number', 'expense_date', 'employee', 'category', 'amount',
        'payment_method', 'status',
    )
    list_filter = ('status', 'payment_method', 'category')
    search_fields = ('expense_number', 'description', 'vendor_name')
    raw_id_fields = ('fuel_transaction', 'advance', 'order', 'special_project')
    inlines = [ApprovalInline]


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'txn_number', 'txn_date', 'txn_type', 'employee', 'special_project',
        'debit', 'credit', 'project_cost', 'is_void',
    )
    list_filter = ('txn_type', 'is_void')
    search_fields = ('txn_number', 'description')
    raw_id_fields = (
        'employee', 'special_project', 'order', 'advance', 'expense',
        'fuel_transaction', 'daily_expense_line',
    )
