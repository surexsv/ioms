"""Active staff querysets by enterprise designation (legacy role fallback)."""

from django.db.models import Q

from accounts.enterprise_models import Employee
from accounts.models import User


def _active_staff_queryset():
    return User.objects.filter(
        is_active=True,
        is_active_employee=True,
    ).order_by('first_name', 'last_name', 'username')


def users_by_designation_or_role(designation_codes, legacy_roles=()):
    """Resolve schedulable staff from Employee designation, with legacy User.role fallback."""
    designation_codes = tuple(designation_codes)
    legacy_roles = tuple(legacy_roles)

    employee_user_ids = Employee.objects.filter(
        status=Employee.STATUS_ACTIVE,
        designation__code__in=designation_codes,
        designation__is_active=True,
        user__is_active=True,
        user__is_active_employee=True,
    ).values_list('user_id', flat=True)

    criteria = Q(pk__in=employee_user_ids)
    if legacy_roles:
        criteria |= Q(role__in=legacy_roles, is_active_employee=True)
    return _active_staff_queryset().filter(criteria).distinct()


def project_manager_queryset():
    return users_by_designation_or_role(['PROJECT_MANAGER'], ['PROJECT_MANAGER'])


def supervisor_queryset():
    return users_by_designation_or_role(['TEAM_LEADER'], ['SUPERVISOR', 'Supervisor'])


def engineer_queryset():
    return users_by_designation_or_role(['ENGINEER'], ['ENGINEER'])


def technician_queryset():
    return users_by_designation_or_role(['TECHNICIAN'], ['TECHNICIAN', 'Technician'])


def team_leader_queryset():
    return users_by_designation_or_role(
        ['TEAM_LEADER', 'ENGINEER', 'OPERATIONS_MANAGER'],
        ['SUPERVISOR', 'Supervisor', 'ENGINEER', 'TECHNICIAN', 'Technician', 'OPERATIONS'],
    )


def field_staff_queryset():
    return users_by_designation_or_role(
        ['ENGINEER', 'TECHNICIAN'],
        ['ENGINEER', 'TECHNICIAN', 'Technician'],
    )


def order_team_initial(order):
    """Prefill schedule team fields from order assignments."""
    initial = {}
    if order.assigned_project_manager_id:
        initial['project_manager'] = order.assigned_project_manager_id
    if order.assigned_supervisor_id:
        initial['supervisor'] = order.assigned_supervisor_id
    if order.assigned_to_id:
        initial['lead_engineer'] = order.assigned_to_id
    return initial
