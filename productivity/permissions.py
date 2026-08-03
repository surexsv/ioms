"""Role-based access for productivity module."""

from accounts.enterprise_permissions import has_enterprise_permission, has_employee_profile
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_ACCOUNTS_EXECUTIVE,
    ROLE_BACK_OFFICE,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    user_role,
)

MODULE_PRODUCTIVITY = 'productivity'
MODULE_PRODUCTIVITY_FULL = 'productivity_full'
MODULE_PRODUCTIVITY_TEAM = 'productivity_team'
MODULE_PRODUCTIVITY_SELF = 'productivity_self'


def _legacy_role(user):
    return user_role(user)


def can_view_productivity(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'reports')
    return _legacy_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER,
        ROLE_SUPERVISOR, ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE,
        ROLE_BACK_OFFICE, ROLE_ENGINEER, ROLE_TECHNICIAN,
    )


def can_view_full_productivity(user):
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'reports') and has_enterprise_permission(user, 'orders')
    return _legacy_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS)


def can_view_team_productivity(user):
    if can_view_full_productivity(user):
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'reports') and has_enterprise_permission(user, 'scheduling')
    return _legacy_role(user) in (ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR)


def can_view_management_productivity(user):
    """Company-wide productivity dashboard — not for field-only roles."""
    if not can_view_productivity(user):
        return False
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        perms = {'reports', 'orders', 'scheduling', 'billing', 'accounts', 'approval'}
        from accounts.enterprise_permissions import get_user_permission_codenames
        user_perms = get_user_permission_codenames(user)
        if not (user_perms & perms):
            return False
        if user_perms & {'billing', 'accounts'} and 'orders' not in user_perms:
            return True
        if user_perms & {'approval', 'scheduling'} and 'quotation' not in user_perms:
            return True
        return bool(user_perms & {'reports', 'orders', 'billing'})
    return _legacy_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER,
        ROLE_SUPERVISOR, ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE,
        ROLE_BACK_OFFICE,
    )


def can_view_gps_dashboard(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'gps_tracking')
    if not can_view_productivity(user):
        return False
    return _legacy_role(user) == ROLE_DIRECTOR


def can_view_field_activity_log(user):
    return can_view_gps_dashboard(user)


def can_view_activity_log(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'gps_tracking')
    return _legacy_role(user) == ROLE_DIRECTOR


def can_export_reports(user):
    return can_view_full_productivity(user) or _legacy_role(user) in (ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE)


def can_view_full_gps(user):
    """Director and Admin — full GPS and movement visibility."""
    if user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'gps_tracking')
    return _legacy_role(user) == ROLE_DIRECTOR


def productivity_scope_users(user):
    """Return User queryset visible to this user for productivity filters."""
    from django.db import models
    from accounts.models import User
    if user.is_superuser or _legacy_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS):
        return User.objects.filter(is_active_employee=True)
    if has_employee_profile(user) and has_enterprise_permission(user, 'reports'):
        if has_enterprise_permission(user, 'orders') and not has_enterprise_permission(user, 'billing'):
            return User.objects.filter(is_active_employee=True)
    if _legacy_role(user) == ROLE_PROJECT_MANAGER:
        return User.objects.filter(
            is_active_employee=True,
        ).filter(
            models.Q(role__in=(ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR))
            | models.Q(pk=user.pk),
        )
    if _legacy_role(user) == ROLE_SUPERVISOR:
        return User.objects.filter(
            is_active_employee=True,
            role__in=(ROLE_ENGINEER, ROLE_TECHNICIAN),
        ) | User.objects.filter(pk=user.pk)
    if _legacy_role(user) == ROLE_ENGINEER:
        return User.objects.filter(
            pk=user.pk,
        ) | User.objects.filter(role=ROLE_TECHNICIAN, is_active_employee=True)
    return User.objects.filter(pk=user.pk)
