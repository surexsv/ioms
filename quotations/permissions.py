from accounts.permissions import (
    can_access,
    MODULE_QUOTATIONS,
    MODULE_QUOTATION_RATES,
)


def can_view_quotations(user):
    return can_access(user, MODULE_QUOTATIONS)


def can_edit_quotations(user):
    return can_access(user, MODULE_QUOTATIONS) and (
        user.is_superuser or user.role in ('DIRECTOR', 'OPERATIONS')
    )


def can_approve_quotations(user):
    return can_access(user, MODULE_QUOTATIONS) and (
        user.is_superuser or user.role in ('DIRECTOR', 'OPERATIONS')
    )


def can_manage_rate_cards(user):
    return can_access(user, MODULE_QUOTATION_RATES)


def can_view_quotation_settings(user):
    return can_view_quotations(user)


def can_manage_quotation_settings(user):
    return user.is_authenticated and (
        user.is_superuser or user.role == 'DIRECTOR'
    )
