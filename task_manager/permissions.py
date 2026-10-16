from accounts.permissions import can_access
from accounts.roles import (
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)

MODULE_TASK_MANAGER = 'task_manager'

_TEAM_ROLES = (
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
)


def can_use_task_manager(user):
    if not user or not user.is_authenticated:
        return False
    return can_access(user, MODULE_TASK_MANAGER)


def can_view_all_tasks(user):
    """Supervisors and above can see and move any team task."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in _TEAM_ROLES


def can_view_task(user, task):
    if not can_use_task_manager(user):
        return False
    if can_view_all_tasks(user):
        return True
    return task.assignee_id == user.id or task.created_by_id == user.id


def can_act_on_task(user, task):
    if not can_view_task(user, task):
        return False
    return task.status != task.STATUS_CLOSED
