from accounts.permissions import can_access

MODULE_SPECIAL_PROJECTS = 'special_projects'


def can_view_special_projects(user):
    return can_access(user, MODULE_SPECIAL_PROJECTS)


def can_manage_special_projects(user):
    """Create/open project and edit daily logs — managers and above."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from accounts.roles import (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, user_role,
    )
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR,
    )


def can_submit_daily_log(user):
    """Field staff and managers can add/update daily entries."""
    if can_manage_special_projects(user):
        return True
    from accounts.roles import ROLE_ENGINEER, ROLE_TECHNICIAN, user_role
    return user_role(user) in (ROLE_ENGINEER, ROLE_TECHNICIAN)
