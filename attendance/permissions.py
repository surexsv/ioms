"""Attendance eligibility and RBAC-driven view helpers."""

from accounts.permissions import (
    MODULE_ATTENDANCE_SELF,
    MODULE_ATTENDANCE_SUPERVISOR_TEAM,
    MODULE_ATTENDANCE_TEAM,
    can_manage_attendance,
    can_view_attendance_audit_data as rbac_can_view_attendance_audit_data,
    can_view_team_attendance as rbac_can_view_team_attendance,
    has_full_access,
)
from accounts.rbac_service import user_has_permission
from accounts.roles import user_role


DEFAULT_ATTENDANCE_REQUIRED = {
    'DIRECTOR': False,
    'OPERATIONS': True,
    'PROJECT_MANAGER': True,
    'SUPERVISOR': True,
    'ENGINEER': True,
    'Technician': True,
    'ACCOUNTS': True,
    'ACCOUNTS_EXECUTIVE': True,
    'BACK_OFFICE': True,
    'Supervisor': True,
}


def default_attendance_required_for_role(role):
    if not role:
        return True
    return DEFAULT_ATTENDANCE_REQUIRED.get(role, True)


def user_requires_attendance(user):
    """Personal attendance — controlled by attendance_required profile flag."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    if hasattr(user, 'attendance_required'):
        return bool(user.attendance_required)
    return default_attendance_required_for_role(user_role(user))


def show_attendance_nav(user):
    from accounts.permissions import (
        show_nav_my_attendance,
        show_nav_attendance_management,
        show_nav_team_attendance,
    )
    return (
        show_nav_my_attendance(user)
        or show_nav_attendance_management(user)
        or show_nav_team_attendance(user)
    )


def can_mark_own_attendance(user):
    return user_requires_attendance(user)


def can_view_team_attendance(user):
    return rbac_can_view_team_attendance(user)


def can_view_team_attendance_page(user):
    """Team attendance monitoring — Ops, PM, or Supervisor scoped team."""
    if can_manage_attendance(user):
        return True
    return user_has_permission(user, MODULE_ATTENDANCE_TEAM) or user_has_permission(
        user, MODULE_ATTENDANCE_SUPERVISOR_TEAM,
    )


def can_view_all_operational_attendance(user):
    return user_has_permission(user, MODULE_ATTENDANCE_TEAM) or can_manage_attendance(user)


def can_correct_attendance(user):
    return has_full_access(user)


def can_edit_attendance_records(user):
    return can_manage_attendance(user) or has_full_access(user)


def can_view_attendance_audit_data(user):
    """Director and Admin/Superuser only — photos, GPS, address, maps, audit details."""
    return rbac_can_view_attendance_audit_data(user)


def user_in_attendance_scope(viewer, employee):
    """Whether viewer may open a specific employee's attendance record."""
    if can_manage_attendance(viewer):
        return True
    if viewer.pk == employee.pk and user_requires_attendance(viewer):
        return True
    from attendance.services import employees_for_manager
    return employees_for_manager(viewer).filter(pk=employee.pk).exists()


def user_can_view_attendance_detail(user, record):
    """Non-audit attendance detail — manage, team scope, or own record."""
    if can_manage_attendance(user):
        return True
    if user.pk == record.employee_id and user_requires_attendance(user):
        return True
    if user_has_permission(user, MODULE_ATTENDANCE_TEAM) or user_has_permission(
        user, MODULE_ATTENDANCE_SUPERVISOR_TEAM,
    ):
        from attendance.services import employees_for_manager
        return employees_for_manager(user).filter(pk=record.employee_id).exists()
    return False
