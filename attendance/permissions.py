"""Attendance eligibility and role-based view helpers."""

from accounts.permissions import can_manage_attendance, has_full_access
from accounts.roles import (
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)


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
    """Primary gate — attendance is controlled by the user profile flag."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    if hasattr(user, 'attendance_required'):
        return bool(user.attendance_required)
    return default_attendance_required_for_role(user_role(user))


def show_attendance_nav(user):
    """Menu visible only when attendance is required (not by role)."""
    return user_requires_attendance(user)


def can_mark_own_attendance(user):
    return user_requires_attendance(user)


def can_view_team_attendance(user):
    if has_full_access(user):
        return True
    return user_role(user) in (ROLE_SUPERVISOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER)


def can_view_all_operational_attendance(user):
    if has_full_access(user):
        return True
    return user_role(user) == ROLE_OPERATIONS


def can_correct_attendance(user):
    return has_full_access(user)


def can_edit_attendance_records(user):
    return can_manage_attendance(user) or has_full_access(user)
