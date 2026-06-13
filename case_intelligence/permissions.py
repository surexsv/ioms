"""Case intelligence RBAC."""

from accounts.permissions import can_access, MODULE_CASE_INTELLIGENCE
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

MODULE_CASE_INTELLIGENCE_FULL = 'case_intelligence_full'


def can_view_case_intelligence(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return can_access(user, MODULE_CASE_INTELLIGENCE)


def can_view_all_cases(user):
    if user.is_superuser:
        return True
    return user_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS)


def can_view_operational_cases(user):
    if can_view_all_cases(user):
        return True
    return user_role(user) in (ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR)


def can_view_financial_cases(user):
    if user.is_superuser:
        return True
    return user_role(user) in (ROLE_DIRECTOR, ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE)


def can_export_case_reports(user):
    return can_view_all_cases(user) or user_role(user) in (ROLE_ACCOUNTS, ROLE_ACCOUNTS_EXECUTIVE)


def is_field_role(user):
    return user_role(user) in (ROLE_ENGINEER, ROLE_TECHNICIAN)


def is_back_office(user):
    return user_role(user) == ROLE_BACK_OFFICE
