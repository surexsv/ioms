from django.contrib import admin
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'order', 'amount', 'gst', 'total',
        'invoice_date', 'payment_status',
    )
    list_filter = ('payment_status', 'invoice_date')
    search_fields = ('invoice_number', 'order__order_no', 'po_number')
    fieldsets = (
        (None, {
            'fields': (
                'order', 'boq', 'invoice_number', 'number_mode', 'service_title',
                'po_number', 'po_date', 'due_date', 'amount', 'gst', 'total',
                'payment_status',
            ),
        }),
        ('Authorized Signatory', {
            'fields': (
                'authorized_signatory_name', 'authorized_signatory_designation',
                'signature_image',
            ),
        }),
    )
