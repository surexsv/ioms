from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import User, UserApprovalAuditLog
from .enterprise_models import (
    Branch,
    Department,
    Designation,
    Employee,
    EmployeePermissionGrant,
    ModulePermission,
)
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


# --- Enterprise user management (Phase 1) ---


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('sort_order', 'name')


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('sort_order', 'name')


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'city', 'state', 'is_head_office', 'is_active')
    list_filter = ('is_active', 'is_head_office')
    search_fields = ('name', 'code', 'city')


@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'codename', 'category', 'sort_order', 'is_active', 'is_system')
    list_filter = ('category', 'is_active', 'is_system')
    search_fields = ('name', 'codename')
    ordering = ('sort_order', 'name')
    readonly_fields = ('is_system',)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_system:
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)


class EmployeePermissionGrantInline(admin.TabularInline):
    model = EmployeePermissionGrant
    extra = 1
    autocomplete_fields = ('permission',)
    fields = ('permission', 'is_active', 'granted_by', 'granted_at', 'notes')
    readonly_fields = ('granted_at',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_code', 'employee_name', 'department', 'designation',
        'branch', 'employment_type', 'status', 'reporting_manager',
    )
    list_filter = ('status', 'employment_type', 'department', 'designation', 'branch')
    search_fields = (
        'employee_code', 'user__username', 'user__first_name',
        'user__last_name', 'user__email', 'mobile',
    )
    autocomplete_fields = ('user', 'department', 'designation', 'reporting_manager', 'branch')
    inlines = [EmployeePermissionGrantInline]
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Identity', {
            'fields': ('user', 'employee_code', 'status'),
        }),
        ('Organization', {
            'fields': ('department', 'designation', 'reporting_manager', 'branch', 'employment_type'),
        }),
        ('Contact & Dates', {
            'fields': ('mobile', 'joining_date'),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Employee Name')
    def employee_name(self, obj):
        return obj.employee_name

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, EmployeePermissionGrant) and not instance.granted_by_id:
                instance.granted_by = request.user
            instance.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()
        if form.instance and form.instance.user_id:
            try:
                from accounts.enterprise_permissions import invalidate_enterprise_permission_cache
                invalidate_enterprise_permission_cache(form.instance.user_id)
            except ImportError:
                pass


@admin.register(EmployeePermissionGrant)
class EmployeePermissionGrantAdmin(admin.ModelAdmin):
    list_display = ('employee', 'permission', 'is_active', 'granted_by', 'granted_at')
    list_filter = ('is_active', 'permission__category')
    search_fields = ('employee__employee_code', 'employee__user__username', 'permission__codename')
    autocomplete_fields = ('employee', 'permission', 'granted_by')
    readonly_fields = ('granted_at',)


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


class EmployeeProfileInline(admin.StackedInline):
    model = Employee
    fk_name = 'user'
    can_delete = False
    extra = 0
    max_num = 1
    autocomplete_fields = ('department', 'designation', 'reporting_manager', 'branch')
    readonly_fields = ('created_at', 'updated_at')
    verbose_name = 'Employee Profile (Enterprise)'
    verbose_name_plural = 'Employee Profile (Enterprise)'


class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'role', 'approval_status',
        'is_active', 'is_active_employee', 'attendance_required', 'is_superuser', 'date_joined',
    )
    list_filter = ('approval_status', 'role', 'is_active', 'is_active_employee', 'attendance_required', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'employee_id')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Employment (Legacy — deprecated)', {
            'fields': (
                'role', 'reports_to', 'phone', 'is_active_employee', 'attendance_required',
                'employee_id', 'department', 'designation', 'role_requested',
            ),
            'description': 'Legacy fields retained for backward compatibility. '
                           'Use Employee Profile for Phase 2+ access control.',
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

    inlines = [EmployeeProfileInline, UserApprovalAuditLogInline]

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.append('attendance_required')
        return readonly


admin.site.register(User, CustomUserAdmin)
