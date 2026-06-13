"""Daily Meetings RBAC helpers."""

from accounts.permissions import (
    MODULE_DAILY_MEETINGS,
    MODULE_DAILY_MEETINGS_MANAGE,
    can_access,
    has_full_access,
)
from accounts.roles import (
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    user_role,
)

MANAGE_ROLES = (ROLE_OPERATIONS, ROLE_PROJECT_MANAGER)
PARTICIPATE_ROLES = (
    ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR,
    ROLE_ENGINEER, ROLE_TECHNICIAN, 'ACCOUNTS', 'ACCOUNTS_EXECUTIVE', 'BACK_OFFICE',
)


def can_access_daily_meetings(user):
    return can_access(user, MODULE_DAILY_MEETINGS) or has_full_access(user)


def can_manage_meetings(user):
    if has_full_access(user):
        return True
    return can_access(user, MODULE_DAILY_MEETINGS_MANAGE)


def can_view_all_meetings(user):
    if has_full_access(user):
        return True
    role = user_role(user)
    return role in (ROLE_DIRECTOR,) or can_manage_meetings(user)


def can_create_meeting(user):
    return can_manage_meetings(user)


def can_edit_meeting(user, meeting=None):
    if has_full_access(user):
        return True
    if not can_manage_meetings(user):
        return False
    if meeting and meeting.status == meeting.STATUS_COMPLETED:
        return has_full_access(user)
    return True


def can_update_actions(user):
    if has_full_access(user):
        return True
    role = user_role(user)
    return can_manage_meetings(user) or role == ROLE_SUPERVISOR


def can_view_action(user, action):
    if has_full_access(user) or can_view_all_meetings(user):
        return True
    if action.assigned_to_id == user.pk:
        return True
    if can_manage_meetings(user):
        return True
    role = user_role(user)
    if role == ROLE_SUPERVISOR and action.assigned_to:
        return action.assigned_to.reports_to_id == user.pk
    return False


def field_team_action_only(user):
    """Field engineers/technicians see action tracker only."""
    if has_full_access(user):
        return False
    return user_role(user) in (ROLE_ENGINEER, ROLE_TECHNICIAN)


def can_manage_agenda_template(user):
    return has_full_access(user)


def can_manage_open_items(user):
    return can_manage_meetings(user) or has_full_access(user)
