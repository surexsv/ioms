"""Schedule access control."""

from accounts.permissions import (
    MODULE_SCHEDULING,
    MODULE_SCHEDULING_FIELD_UPDATE,
    MODULE_SCHEDULING_MANAGE,
    can_access,
)
from accounts.roles import LEGACY_SUPERVISOR, ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, user_role


def can_view_scheduling(user):
    return can_access(user, MODULE_SCHEDULING)


def can_manage_scheduling(user):
    return can_access(user, MODULE_SCHEDULING_MANAGE)


def can_field_update_schedule(user, schedule):
    """Assigned field team may update status and remarks on their schedules."""
    if not can_access(user, MODULE_SCHEDULING_FIELD_UPDATE):
        return False
    if can_manage_scheduling(user):
        return False
    from scheduling.engine import user_on_schedule_team
    return user_on_schedule_team(schedule, user)


def can_view_schedule(user, schedule):
    if not can_view_scheduling(user):
        return False
    if user.is_superuser:
        return True
    role = user_role(user)
    raw = getattr(user, 'role', None)
    if role in (ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER):
        return True
    if role == ROLE_SUPERVISOR or raw == LEGACY_SUPERVISOR:
        return True
    from scheduling.engine import user_on_schedule_team
    if user_on_schedule_team(schedule, user):
        return True
    return can_manage_scheduling(user)
