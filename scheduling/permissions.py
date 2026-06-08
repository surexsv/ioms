from accounts.permissions import can_access, MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE


def can_view_scheduling(user):
    return can_access(user, MODULE_SCHEDULING)


def can_manage_scheduling(user):
    return can_access(user, MODULE_SCHEDULING_MANAGE)


def can_view_schedule(user, schedule):
    if not can_view_scheduling(user):
        return False
    if user.is_superuser or user.role in ('DIRECTOR', 'OPERATIONS', 'Supervisor', 'ACCOUNTS'):
        return True
    if user.role in ('ENGINEER', 'Technician'):
        return schedule.assigned_engineers.filter(pk=user.pk).exists()
    return can_manage_scheduling(user)
