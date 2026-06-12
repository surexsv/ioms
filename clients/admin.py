from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'company_type', 'state', 'state_code',
        'gst_number', 'pan_number', 'gst_type',
    )
    list_filter = ('company_type', 'state', 'gst_type')
    search_fields = ('name', 'gst_number', 'pan_number', 'contact_person')
    fieldsets = (
        (None, {
            'fields': ('name', 'company_type', 'address', 'contact_person', 'phone'),
        }),
        ('Tax & GST', {
            'fields': ('gst_number', 'pan_number', 'state', 'state_code', 'gst_type'),
        }),
    )
