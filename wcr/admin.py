from django.contrib import admin

from .models import WorkCompletionReport


@admin.register(WorkCompletionReport)
class WorkCompletionReportAdmin(admin.ModelAdmin):
    list_display = ('wcr_number', 'order', 'submitted_by', 'submitted_date', 'approved')
    list_filter = ('approved',)
    fieldsets = (
        (None, {
            'fields': (
                'order', 'wcr_number', 'work_description', 'material_used',
                'photo', 'submitted_by', 'submitted_date', 'approved',
            ),
        }),
        ('Authorized Signatory', {
            'fields': (
                'authorized_signatory_name', 'authorized_signatory_designation',
                'signature_image',
            ),
        }),
    )
