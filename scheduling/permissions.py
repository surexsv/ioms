from accounts.permissions import can_access, MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE


def can_view_scheduling(user):
    return can_access(user, MODULE_SCHEDULING)


def can_manage_scheduling(user):
    return can_access(user, MODULE_SCHEDULING_MANAGE)


def can_view_schedule(user, schedule):
    if not can_view_scheduling(user):
        return False
    if user.is_superuser or user.role in ('DIRECTOR', 'OPERATIONS', 'Supervisor', 'ACCOUNTS', 'PROJECT_MANAGER'):
        return True
    from scheduling.engine import user_on_schedule_team
    if user_on_schedule_team(schedule, user):
        return True
    return can_manage_scheduling(user)
