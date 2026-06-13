from django.contrib import admin

from .models import (
    EmployeeRequest,
    PortalNotification,
    RequestApprovalHistory,
    RequestAttachment,
    RequestType,
)


@admin.register(RequestType)
class RequestTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'requires_amount', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'codename')


class RequestAttachmentInline(admin.TabularInline):
    model = RequestAttachment
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by')


class RequestApprovalHistoryInline(admin.TabularInline):
    model = RequestApprovalHistory
    extra = 0
    readonly_fields = ('action', 'from_status', 'to_status', 'performed_by', 'remarks', 'created_at')
    can_delete = False


@admin.register(EmployeeRequest)
class EmployeeRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_number', 'request_type', 'requested_by', 'submitted_to',
        'status', 'priority', 'request_date',
    )
    list_filter = ('status', 'request_type', 'priority')
    search_fields = ('request_number', 'subject', 'requested_by__username')
    readonly_fields = ('request_number', 'created_at', 'updated_at')
    inlines = [RequestAttachmentInline, RequestApprovalHistoryInline]


@admin.register(PortalNotification)
class PortalNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)
