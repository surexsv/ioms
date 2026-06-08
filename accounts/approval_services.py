from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import User, UserApprovalAuditLog


def log_approval_action(user, action, performed_by=None, notes=''):
    UserApprovalAuditLog.objects.create(
        user=user,
        action=action,
        performed_by=performed_by,
        notes=notes,
    )


def _send_notification(subject, message, recipient_email):
    if not recipient_email:
        return
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    if not from_email:
        return
    try:
        send_mail(subject, message, from_email, [recipient_email], fail_silently=True)
    except Exception:
        pass


def approve_user(user, approved_by):
    user.approval_status = User.APPROVAL_APPROVED
    user.approved_by = approved_by
    user.approved_date = timezone.now()
    user.rejection_reason = ''
    user.is_active = True
    user.is_active_employee = True
    if user.role_requested and not user.role:
        user.role = user.map_requested_role()
    elif user.role_requested:
        user.role = user.map_requested_role()
    user.save()
    log_approval_action(
        user,
        UserApprovalAuditLog.ACTION_APPROVED,
        performed_by=approved_by,
        notes=f'Approved by {approved_by.username}',
    )
    _send_notification(
        'Profile Approved — IOMS',
        'Your IOMS account has been approved. You may now sign in.',
        user.email,
    )


def reject_user(user, rejected_by, reason):
    user.approval_status = User.APPROVAL_REJECTED
    user.rejection_reason = reason.strip()
    user.approved_by = None
    user.approved_date = None
    user.is_active = False
    user.save()
    log_approval_action(
        user,
        UserApprovalAuditLog.ACTION_REJECTED,
        performed_by=rejected_by,
        notes=reason.strip(),
    )
    _send_notification(
        'Profile Rejected — IOMS',
        f'Your registration has been rejected.\n\nReason:\n{reason.strip()}',
        user.email,
    )


def mark_resubmitted(user):
    user.approval_status = User.APPROVAL_PENDING
    user.resubmission_date = timezone.now()
    user.is_active = False
    user.save()
    log_approval_action(
        user,
        UserApprovalAuditLog.ACTION_RESUBMITTED,
        performed_by=user,
        notes='User resubmitted profile for review.',
    )
