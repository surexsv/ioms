from accounts.permissions import (
    can_access,
    MODULE_QUOTATIONS,
    MODULE_QUOTATION_RATES,
)
from accounts.roles import (
    user_role,
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
)


def can_view_quotations(user):
    return can_access(user, MODULE_QUOTATIONS)


def can_edit_quotations(user):
    return can_access(user, MODULE_QUOTATIONS) and (
        user.is_superuser or user_role(user) in (
            ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_ACCOUNTS,
        )
    )


def can_approve_quotations(user):
    return can_access(user, MODULE_QUOTATIONS) and (
        user.is_superuser or user_role(user) in (ROLE_DIRECTOR, ROLE_OPERATIONS)
    )


def can_manage_rate_cards(user):
    return can_access(user, MODULE_QUOTATION_RATES)


def can_view_quotation_settings(user):
    return can_view_quotations(user)


def can_manage_quotation_settings(user):
    return user.is_authenticated and (
        user.is_superuser or user.role == 'DIRECTOR'
    )


def can_view_purchase_rates(user):
    """Purchase Rates is limited to Director, Accounts Manager, and superusers."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False
    return user_role(user) in (ROLE_DIRECTOR, ROLE_ACCOUNTS)


def can_edit_purchase_margin(user):
    """Profit margin % can be changed by Director and superusers only."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return user_role(user) == ROLE_DIRECTOR
