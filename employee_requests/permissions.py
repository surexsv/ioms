"""ERMS RBAC helpers."""

from accounts.permissions import (
    MODULE_ERMS,
    MODULE_ERMS_APPROVE,
    MODULE_ERMS_FINANCIAL_APPROVE,
    MODULE_ERMS_VIEW_ALL,
    can_access,
)
from accounts.rbac_service import user_has_permission

from .constants import FINANCIAL_TYPE_CODES


def can_access_erms(user):
    return can_access(user, MODULE_ERMS)


def can_approve_requests(user):
    return can_access(user, MODULE_ERMS_APPROVE) or user.is_superuser


def can_view_all_requests(user):
    return can_access(user, MODULE_ERMS_VIEW_ALL) or user.is_superuser


def can_approve_financial_request(user):
    return user.is_superuser or user_has_permission(user, MODULE_ERMS_FINANCIAL_APPROVE)


def can_view_request(user, request_obj):
    if not can_access_erms(user):
        return False
    if user.is_superuser or can_view_all_requests(user):
        return True
    return request_obj.requested_by_id == user.pk or request_obj.submitted_to_id == user.pk


def is_financial_type(request_type):
    return request_type.codename in FINANCIAL_TYPE_CODES
