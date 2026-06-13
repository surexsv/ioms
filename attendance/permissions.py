"""Attendance eligibility and RBAC-driven view helpers."""

from accounts.permissions import (
    can_manage_attendance,
    can_view_team_attendance as rbac_can_view_team_attendance,
    has_full_access,
)
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


def can_view_all_operational_attendance(user):
    from accounts.rbac_service import user_has_permission
    from accounts.permissions import MODULE_ATTENDANCE_TEAM
    return user_has_permission(user, MODULE_ATTENDANCE_TEAM) or can_manage_attendance(user)


def can_correct_attendance(user):
    return has_full_access(user)


def can_edit_attendance_records(user):
    return can_manage_attendance(user) or has_full_access(user)
