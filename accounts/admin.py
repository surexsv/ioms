from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import User, UserApprovalAuditLog
from .rbac_models import ActionPermission, MenuItem, RolePermission, SystemPermission, SystemRole
from .rbac_service import invalidate_rbac_cache


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ('permission',)


@admin.register(SystemRole)
class SystemRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'hierarchy_level', 'is_system', 'is_active')
    list_filter = ('is_active', 'is_system')
    search_fields = ('name', 'codename')
    inlines = [RolePermissionInline]


@admin.register(SystemPermission)
class SystemPermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'codename')


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'url_name', 'nav_key', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('label', 'url_name')


@admin.register(ActionPermission)
class ActionPermissionAdmin(admin.ModelAdmin):
    list_display = ('label', 'url_pattern', 'view_name', 'permission', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('url_pattern', 'view_name', 'label')


@receiver(post_save, sender=RolePermission)
@receiver(post_delete, sender=RolePermission)
@receiver(post_save, sender=SystemRole)
@receiver(post_save, sender=SystemPermission)
def _rbac_cache_bust(*args, **kwargs):
    invalidate_rbac_cache()


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
        'is_active', 'is_active_employee', 'attendance_required', 'is_superuser', 'date_joined',
    )
    list_filter = ('approval_status', 'role', 'is_active', 'is_active_employee', 'attendance_required', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'employee_id')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Employment', {
            'fields': (
                'role', 'reports_to', 'phone', 'is_active_employee', 'attendance_required',
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

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.append('attendance_required')
        return readonly


admin.site.register(User, CustomUserAdmin)
