"""ERMS business logic and notifications."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)

from .constants import (
    EDITABLE_STATUSES,
    FINANCIAL_TYPE_CODES,
    PENDING_STATUSES,
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DRAFT,
    STATUS_REJECTED,
    STATUS_RETURNED,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
)
from .models import EmployeeRequest, PortalNotification, RequestApprovalHistory, RequestType


def _log_history(request_obj, action, user, from_status, to_status, remarks=''):
    RequestApprovalHistory.objects.create(
        request=request_obj,
        action=action,
        from_status=from_status or '',
        to_status=to_status or '',
        performed_by=user,
        remarks=remarks or '',
    )


def _notify(user, title, message, request_obj=None):
    if not user or not user.is_active:
        return
    link = ''
    if request_obj:
        link = reverse('erms_request_detail', kwargs={'pk': request_obj.pk})
    PortalNotification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
        related_request=request_obj,
    )


def approver_users_for_type(request_type, exclude_user=None):
    """Users eligible in Submitted To dropdown for a request type."""
    hints = []
    if request_type and request_type.approver_role_hints:
        hints = [h.strip() for h in request_type.approver_role_hints.split(',') if h.strip()]
    if not hints:
        hints = [ROLE_SUPERVISOR, ROLE_PROJECT_MANAGER, ROLE_OPERATIONS, ROLE_ACCOUNTS, ROLE_DIRECTOR]

    qs = User.objects.filter(
        is_active=True,
        is_profile_approved=True,
        role__in=hints,
    ).order_by('first_name', 'last_name', 'username')
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return qs


def requests_for_user(user):
    """Requests visible to user (own + assigned + view-all)."""
    from .permissions import can_view_all_requests

    qs = EmployeeRequest.objects.select_related(
        'request_type', 'requested_by', 'submitted_to',
    )
    if user.is_superuser or can_view_all_requests(user):
        return qs
    return qs.filter(Q(requested_by=user) | Q(submitted_to=user))


def my_requests_qs(user):
    return EmployeeRequest.objects.filter(requested_by=user).select_related(
        'request_type', 'submitted_to',
    )


def pending_approvals_qs(user):
    return EmployeeRequest.objects.filter(
        submitted_to=user,
        status__in=PENDING_STATUSES,
    ).select_related('request_type', 'requested_by')


def can_user_approve(user, request_obj):
    from .permissions import can_approve_requests, can_approve_financial_request

    if not can_approve_requests(user):
        return False
    if request_obj.submitted_to_id != user.pk and not user.is_superuser:
        return False
    if request_obj.status not in PENDING_STATUSES:
        return False
    code = request_obj.request_type.codename
    if code in FINANCIAL_TYPE_CODES:
        return can_approve_financial_request(user) or user.is_superuser
    return True


def dashboard_summary(user):
    mine = my_requests_qs(user)
    pending = pending_approvals_qs(user)
    today = timezone.localdate()
    return {
        'my_open': mine.exclude(status__in=(STATUS_COMPLETED, STATUS_CANCELLED, STATUS_REJECTED)).count(),
        'my_pending_approval': pending.count(),
        'my_approved': mine.filter(status=STATUS_APPROVED).count(),
        'my_rejected': mine.filter(status=STATUS_REJECTED).count(),
        'my_completed': mine.filter(status=STATUS_COMPLETED).count(),
        'pending_approvals': pending.count(),
        'recent_approved': EmployeeRequest.objects.filter(
            submitted_to=user, status=STATUS_APPROVED,
        ).select_related('request_type', 'requested_by').order_by('-updated_at')[:5],
        'recent_rejected': EmployeeRequest.objects.filter(
            submitted_to=user, status=STATUS_REJECTED,
        ).select_related('request_type', 'requested_by').order_by('-updated_at')[:5],
        'overdue': pending.filter(request_date__lt=today - timedelta(days=3)).count(),
    }


@transaction.atomic
def submit_request(request_obj, user, remarks=''):
    if request_obj.requested_by_id != user.pk and not user.is_superuser:
        raise PermissionError('Not your request.')
    if request_obj.status not in (STATUS_DRAFT, STATUS_RETURNED):
        raise ValueError('Request cannot be submitted in current status.')
    if not request_obj.submitted_to_id:
        raise ValueError('Submitted To is required.')
    old = request_obj.status
    request_obj.status = STATUS_SUBMITTED
    request_obj.remarks = remarks or request_obj.remarks
    request_obj.save()
    _log_history(request_obj, 'SUBMIT', user, old, STATUS_SUBMITTED, remarks)
    title = f'New {request_obj.request_type.name} Pending Approval'
    _notify(
        request_obj.submitted_to,
        title,
        f'{request_obj.subject} — submitted by {user.get_full_name() or user.username}',
        request_obj,
    )
    return request_obj


@transaction.atomic
def approve_request(request_obj, user, remarks=''):
    if not can_user_approve(user, request_obj):
        raise PermissionError('Cannot approve this request.')
    old = request_obj.status
    request_obj.status = STATUS_APPROVED
    request_obj.save()
    _log_history(request_obj, 'APPROVE', user, old, STATUS_APPROVED, remarks)
    _notify(
        request_obj.requested_by,
        f'{request_obj.request_type.name} Approved',
        remarks or f'Request {request_obj.request_number} has been approved.',
        request_obj,
    )
    return request_obj


@transaction.atomic
def reject_request(request_obj, user, remarks=''):
    if not can_user_approve(user, request_obj):
        raise PermissionError('Cannot reject this request.')
    old = request_obj.status
    request_obj.status = STATUS_REJECTED
    request_obj.save()
    _log_history(request_obj, 'REJECT', user, old, STATUS_REJECTED, remarks)
    _notify(
        request_obj.requested_by,
        f'{request_obj.request_type.name} Rejected',
        remarks or f'Request {request_obj.request_number} has been rejected.',
        request_obj,
    )
    return request_obj


@transaction.atomic
def return_request(request_obj, user, remarks=''):
    if not can_user_approve(user, request_obj):
        raise PermissionError('Cannot return this request.')
    old = request_obj.status
    request_obj.status = STATUS_RETURNED
    request_obj.save()
    _log_history(request_obj, 'RETURN', user, old, STATUS_RETURNED, remarks)
    _notify(
        request_obj.requested_by,
        f'{request_obj.request_type.name} Returned for Correction',
        remarks or 'Please update and resubmit your request.',
        request_obj,
    )
    return request_obj


@transaction.atomic
def complete_request(request_obj, user, remarks=''):
    if request_obj.status != STATUS_APPROVED:
        raise ValueError('Only approved requests can be completed.')
    old = request_obj.status
    request_obj.status = STATUS_COMPLETED
    request_obj.save()
    _log_history(request_obj, 'COMPLETE', user, old, STATUS_COMPLETED, remarks)
    return request_obj


def register_list_qs(user, filters=None):
    from .permissions import can_view_all_requests

    filters = filters or {}
    if can_view_all_requests(user):
        qs = EmployeeRequest.objects.all()
    else:
        qs = EmployeeRequest.objects.filter(
            Q(requested_by=user) | Q(submitted_to=user),
        )
    qs = qs.select_related('request_type', 'requested_by', 'submitted_to')
    if filters.get('request_type'):
        qs = qs.filter(request_type_id=filters['request_type'])
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    if filters.get('department'):
        qs = qs.filter(department__icontains=filters['department'])
    if filters.get('employee'):
        qs = qs.filter(requested_by_id=filters['employee'])
    return qs.order_by('-request_date', '-created_at')
