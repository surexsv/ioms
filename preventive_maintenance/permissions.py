from accounts.permissions import can_access
from accounts.roles import (
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    user_role,
)

MODULE_PREVENTIVE_MAINTENANCE = 'preventive_maintenance'
MODULE_PM_APPROVE = 'preventive_maintenance_approve'

_CREATE_ROLES = (
    ROLE_TECHNICIAN,
    ROLE_ENGINEER,
    ROLE_SUPERVISOR,
    ROLE_PROJECT_MANAGER,
    ROLE_OPERATIONS,
    ROLE_DIRECTOR,
)

_APPROVE_ROLES = (
    ROLE_SUPERVISOR,
    ROLE_PROJECT_MANAGER,
    ROLE_OPERATIONS,
    ROLE_DIRECTOR,
)


def can_view_pm(user):
    if not user or not user.is_authenticated:
        return False
    if can_access(user, MODULE_PREVENTIVE_MAINTENANCE):
        return True
    # Existing field/ops users already have Order/Schedule/WCR access.
    from accounts.permissions import MODULE_ORDERS, MODULE_SCHEDULING, MODULE_WCR
    if user_role(user) in _CREATE_ROLES and (
        can_access(user, MODULE_ORDERS)
        or can_access(user, MODULE_SCHEDULING)
        or can_access(user, MODULE_WCR)
    ):
        return True
    return False


def can_create_pm(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not can_view_pm(user):
        return False
    return user_role(user) in _CREATE_ROLES


def can_approve_pm(user):
    """Review, approve, create/link orders, and close PM records."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not can_view_pm(user):
        return False
    if can_access(user, MODULE_PM_APPROVE):
        return user_role(user) in _APPROVE_ROLES or user.is_superuser
    return user_role(user) in _APPROVE_ROLES


def can_close_pm(user):
    return can_approve_pm(user)
