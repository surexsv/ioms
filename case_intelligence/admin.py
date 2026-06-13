from django.contrib import admin

from case_intelligence.models import CaseActivityLog


@admin.register(CaseActivityLog)
class CaseActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'activity_at', 'module', 'document_number', 'description',
        'user', 'new_status',
    )
    list_filter = ('module', 'document_type')
    search_fields = ('document_number', 'description', 'remarks')
    readonly_fields = ('activity_at',)
    date_hierarchy = 'activity_at'
