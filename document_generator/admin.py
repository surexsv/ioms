from django.contrib import admin
from .models import DocumentCounter, DocumentNumberSettings, GeneratedDocumentNumber


@admin.register(DocumentNumberSettings)
class DocumentNumberSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'company_prefix', 'serial_length', 'updated_at', 'updated_by')

    def has_add_permission(self, request):
        return not DocumentNumberSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentCounter)
class DocumentCounterAdmin(admin.ModelAdmin):
    list_display = ('document_type', 'year_series', 'last_serial', 'last_number', 'updated_at')
    list_filter = ('document_type', 'year_series')


@admin.register(GeneratedDocumentNumber)
class GeneratedDocumentNumberAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'document_type', 'year_series', 'serial', 'generated_at', 'generated_by')
    list_filter = ('document_type', 'year_series')
    search_fields = ('document_number',)
