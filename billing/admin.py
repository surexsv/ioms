from django.contrib import admin

from .models import (
    Invoice,
    InvoiceApprovalAuditLog,
    InvoiceGstAuditLog,
    InvoiceImportBatch,
    InvoiceImportItem,
)


class InvoiceGstAuditLogInline(admin.TabularInline):
    model = InvoiceGstAuditLog
    extra = 0
    readonly_fields = (
        'changed_by', 'client_gst_type', 'previous_gst_type',
        'new_gst_type', 'note', 'created_at',
    )


class InvoiceApprovalAuditLogInline(admin.TabularInline):
    model = InvoiceApprovalAuditLog
    extra = 0
    readonly_fields = (
        'action', 'performed_by', 'previous_status', 'new_status',
        'remarks', 'rejection_reason', 'notification_channel',
        'notification_sent_at', 'created_at',
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'order', 'client', 'source', 'approval_status', 'gst_type',
        'amount', 'gst', 'total', 'invoice_date', 'payment_status',
    )
    list_filter = ('approval_status', 'payment_status', 'invoice_date')
    search_fields = ('invoice_number', 'order__order_no', 'client__name', 'po_number')
    fieldsets = (
        (None, {
            'fields': (
                'order', 'client', 'source', 'import_batch', 'boq', 'invoice_number', 'number_mode', 'service_title',
                'po_number', 'po_date', 'billing_period_from', 'billing_period_to', 'due_date', 'gst_type',
                'amount', 'cgst_amount', 'sgst_amount', 'igst_amount', 'gst', 'total',
                'payment_status', 'approval_status',
            ),
        }),
        ('Approval', {
            'fields': (
                'created_by', 'submitted_by', 'submitted_at',
                'approved_by', 'approved_at', 'rejected_by', 'rejected_at',
                'rejection_reason', 'approval_remarks',
            ),
        }),
        ('Authorized Signatory', {
            'fields': (
                'authorized_signatory_name', 'authorized_signatory_designation',
                'signature_image',
            ),
        }),
    )
    inlines = [InvoiceApprovalAuditLogInline, InvoiceGstAuditLogInline]


@admin.register(InvoiceGstAuditLog)
class InvoiceGstAuditLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'new_gst_type', 'client_gst_type', 'changed_by', 'created_at')
    list_filter = ('new_gst_type',)


@admin.register(InvoiceApprovalAuditLog)
class InvoiceApprovalAuditLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'action', 'performed_by', 'previous_status', 'new_status', 'created_at')
    list_filter = ('action', 'new_status')


class InvoiceImportItemInline(admin.TabularInline):
    model = InvoiceImportItem
    extra = 0
    readonly_fields = (
        'sort_order', 'invoice_number', 'status', 'client', 'created_invoice',
    )


@admin.register(InvoiceImportBatch)
class InvoiceImportBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'original_filename', 'uploaded_by', 'uploaded_at',
        'status', 'invoice_count', 'created_count', 'error_count',
    )
    list_filter = ('status',)
    inlines = [InvoiceImportItemInline]


@admin.register(InvoiceImportItem)
class InvoiceImportItemAdmin(admin.ModelAdmin):
    list_display = ('batch', 'invoice_number', 'status', 'client', 'created_invoice')
    list_filter = ('status',)
