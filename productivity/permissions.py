"""Role-based access for productivity module."""

from accounts.permissions import can_access
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


def can_view_productivity(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER,
        ROLE_SUPERVISOR, ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE,
        ROLE_BACK_OFFICE, ROLE_ENGINEER, ROLE_TECHNICIAN,
    )


def can_view_full_productivity(user):
    if user.is_superuser:
        return True
    return user_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS)


def can_view_team_productivity(user):
    if can_view_full_productivity(user):
        return True
    return user_role(user) in (ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR)


def can_view_management_productivity(user):
    """Company-wide productivity dashboard — not for field-only roles."""
    if not can_view_productivity(user):
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER,
        ROLE_SUPERVISOR, ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE,
        ROLE_BACK_OFFICE,
    )


def can_view_gps_dashboard(user):
    if not can_view_productivity(user):
        return False
    if user.is_superuser:
        return True
    return user_role(user) == ROLE_DIRECTOR


def can_view_field_activity_log(user):
    return can_view_gps_dashboard(user)


def can_view_activity_log(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) == ROLE_DIRECTOR


def can_export_reports(user):
    return can_view_full_productivity(user) or user_role(user) in (ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE)


def can_view_full_gps(user):
    """Director and Admin — full GPS and movement visibility."""
    if user.is_superuser:
        return True
    return user_role(user) == ROLE_DIRECTOR


def productivity_scope_users(user):
    """Return User queryset visible to this user for productivity filters."""
    from django.db import models
    from accounts.models import User
    if user.is_superuser or user_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS):
        return User.objects.filter(is_active_employee=True)
    if user_role(user) == ROLE_PROJECT_MANAGER:
        return User.objects.filter(
            is_active_employee=True,
        ).filter(
            models.Q(role__in=(ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR))
            | models.Q(pk=user.pk),
        )
    if user_role(user) == ROLE_SUPERVISOR:
        return User.objects.filter(
            is_active_employee=True,
            role__in=(ROLE_ENGINEER, ROLE_TECHNICIAN),
        ) | User.objects.filter(pk=user.pk)
    if user_role(user) == ROLE_ENGINEER:
        return User.objects.filter(
            pk=user.pk,
        ) | User.objects.filter(role=ROLE_TECHNICIAN, is_active_employee=True)
    return User.objects.filter(pk=user.pk)
