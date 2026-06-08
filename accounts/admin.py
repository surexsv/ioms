from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserApprovalAuditLog


class UserApprovalAuditLogInline(admin.TabularInline):
    model = UserApprovalAuditLog
    fk_name = 'user'
    extra = 0
    readonly_fields = ('action', 'performed_by', 'notes', 'created_at')
    can_delete = False


@admin.register(UserApprovalAuditLog)
class UserApprovalAuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'performed_by', 'created_at')
    list_filter = ('action',)
    search_fields = ('user__username', 'notes')
    readonly_fields = ('user', 'action', 'performed_by', 'notes', 'created_at')


class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'role', 'approval_status',
        'is_active', 'is_active_employee', 'date_joined',
    )
    list_filter = ('approval_status', 'role', 'is_active', 'is_active_employee')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'employee_id')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Employment', {
            'fields': (
                'role', 'phone', 'is_active_employee',
                'employee_id', 'department', 'designation', 'role_requested',
            ),
        }),
        ('Profile', {
            'fields': ('address', 'city', 'state', 'pin_code', 'profile_photo'),
        }),
        ('Approval Workflow', {
            'fields': (
                'approval_status', 'approved_by', 'approved_date',
                'rejection_reason', 'resubmission_date',
            ),
        }),
    )

    inlines = [UserApprovalAuditLogInline]


admin.site.register(User, CustomUserAdmin)
