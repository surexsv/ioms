from accounts.permissions import can_access
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    user_role,
)

MODULE_FLEET = 'fleet'


def can_view_fleet(user):
    return can_access(user, MODULE_FLEET)


def can_create_fuel_entry(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return can_access(user, MODULE_FLEET)


def can_manage_fleet(user):
    """Vehicle/card masters, recharge, petty cash, reimbursement actions."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_ACCOUNTS, ROLE_PROJECT_MANAGER,
    )


def can_edit_fuel_entry(user, fuel):
    if not can_create_fuel_entry(user):
        return False
    if fuel.is_locked:
        return can_manage_fleet(user)
    if can_manage_fleet(user):
        return True
    # Technicians: own unlocked entries only
    return fuel.created_by_id == user.pk or fuel.driver_id == user.pk
