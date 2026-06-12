from django.contrib import admin
from .models import Enquiry, SiteProgressUpdate


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = (
        'enquiry_number', 'client', 'enquiry_type', 'status',
        'assigned_project_manager', 'enquiry_date',
    )
    list_filter = ('status', 'enquiry_type', 'source')
    search_fields = ('enquiry_number', 'contact_person', 'mobile', 'client__name')


@admin.register(SiteProgressUpdate)
class SiteProgressUpdateAdmin(admin.ModelAdmin):
    list_display = ('update_date', 'supervisor', 'enquiry', 'order', 'progress_percent', 'verified')
    list_filter = ('verified',)
