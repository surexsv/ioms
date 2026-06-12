"""Invoice approval workflow constants and helpers."""

from django.utils import timezone

STATUS_DRAFT = 'DRAFT'
STATUS_SUBMITTED = 'SUBMITTED'
STATUS_UNDER_REVIEW = 'UNDER_REVIEW'
STATUS_APPROVED = 'APPROVED'
STATUS_REJECTED = 'REJECTED'
STATUS_CANCELLED = 'CANCELLED'

APPROVAL_STATUS_CHOICES = (
    (STATUS_DRAFT, 'Draft'),
    (STATUS_SUBMITTED, 'Submitted'),
    (STATUS_UNDER_REVIEW, 'Under Review'),
    (STATUS_APPROVED, 'Approved'),
    (STATUS_REJECTED, 'Rejected'),
    (STATUS_CANCELLED, 'Cancelled'),
)

REJECTION_REASON_CHOICES = (
    ('WRONG_GST', 'Wrong GST'),
    ('WRONG_CLIENT', 'Wrong Client'),
    ('WRONG_AMOUNT', 'Wrong Amount'),
    ('WRONG_BOQ', 'Wrong BOQ'),
    ('DUPLICATE', 'Duplicate Invoice'),
    ('OTHER', 'Other'),
)

# Audit actions — extensible for future notification hooks
ACTION_CREATED = 'CREATED'
ACTION_SUBMITTED = 'SUBMITTED'
ACTION_UNDER_REVIEW = 'UNDER_REVIEW'
ACTION_APPROVED = 'APPROVED'
ACTION_REJECTED = 'REJECTED'
ACTION_RESUBMITTED = 'RESUBMITTED'
ACTION_CANCELLED = 'CANCELLED'
ACTION_EDITED = 'EDITED'
ACTION_UNLOCKED = 'UNLOCKED'

ACTION_CHOICES = (
    (ACTION_CREATED, 'Created'),
    (ACTION_SUBMITTED, 'Submitted for Approval'),
    (ACTION_UNDER_REVIEW, 'Under Review'),
    (ACTION_APPROVED, 'Approved'),
    (ACTION_REJECTED, 'Rejected'),
    (ACTION_RESUBMITTED, 'Resubmitted'),
    (ACTION_CANCELLED, 'Cancelled'),
    (ACTION_EDITED, 'Edited'),
    (ACTION_UNLOCKED, 'Unlocked for Editing'),
)

PDF_BLOCKED_STATUSES = {
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_REJECTED,
    STATUS_CANCELLED,
}

PDF_BLOCKED_MESSAGE = (
    'Invoice approval is pending. Final invoice generation is allowed only after approval.'
)

SUBMITTABLE_STATUSES = {STATUS_DRAFT, STATUS_REJECTED}
EDITABLE_STATUSES = {
    STATUS_DRAFT,
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_REJECTED,
}
LOCKED_STATUSES = {STATUS_APPROVED, STATUS_CANCELLED}
APPROVABLE_STATUSES = {STATUS_SUBMITTED, STATUS_UNDER_REVIEW}

INVOICE_LOCKED_MESSAGE = (
    'This invoice has been approved and locked from editing.'
)


def can_generate_pdf(invoice):
    return invoice.approval_status == STATUS_APPROVED


def log_approval_action(
    invoice,
    action,
    user,
    *,
    previous_status='',
    new_status='',
    remarks='',
    rejection_reason='',
    notification_channel='',
):
    from .models import InvoiceApprovalAuditLog

    return InvoiceApprovalAuditLog.objects.create(
        invoice=invoice,
        action=action,
        performed_by=user,
        previous_status=previous_status,
        new_status=new_status,
        remarks=remarks,
        rejection_reason=rejection_reason,
        notification_channel=notification_channel,
    )


def submit_invoice(invoice, user):
    previous = invoice.approval_status
    invoice.approval_status = STATUS_SUBMITTED
    invoice.submitted_by = user
    invoice.submitted_at = timezone.now()
    invoice.rejected_by = None
    invoice.rejected_at = None
    invoice.rejection_reason = ''
    invoice.save(update_fields=[
        'approval_status', 'submitted_by', 'submitted_at',
        'rejected_by', 'rejected_at', 'rejection_reason',
    ])
    action = ACTION_RESUBMITTED if previous == STATUS_REJECTED else ACTION_SUBMITTED
    log_approval_action(
        invoice, action, user,
        previous_status=previous,
        new_status=STATUS_SUBMITTED,
    )


def start_review(invoice, user):
    if invoice.approval_status != STATUS_SUBMITTED:
        return False
    previous = invoice.approval_status
    invoice.approval_status = STATUS_UNDER_REVIEW
    invoice.save(update_fields=['approval_status'])
    log_approval_action(
        invoice, ACTION_UNDER_REVIEW, user,
        previous_status=previous,
        new_status=STATUS_UNDER_REVIEW,
    )
    return True


def approve_invoice(invoice, user, remarks=''):
    previous = invoice.approval_status
    invoice.approval_status = STATUS_APPROVED
    invoice.approved_by = user
    invoice.approved_at = timezone.now()
    invoice.approval_remarks = remarks
    invoice.save(update_fields=[
        'approval_status', 'approved_by', 'approved_at', 'approval_remarks',
    ])
    log_approval_action(
        invoice, ACTION_APPROVED, user,
        previous_status=previous,
        new_status=STATUS_APPROVED,
        remarks=remarks,
    )
    invoice._sync_order_billing_status()


def unlock_invoice(invoice, user):
    previous = invoice.approval_status
    invoice.approval_status = STATUS_DRAFT
    invoice.approved_by = None
    invoice.approved_at = None
    invoice.save(update_fields=['approval_status', 'approved_by', 'approved_at'])
    log_approval_action(
        invoice, ACTION_UNLOCKED, user,
        previous_status=previous,
        new_status=STATUS_DRAFT,
        remarks='Invoice unlocked for editing.',
    )


def reject_invoice(invoice, user, rejection_reason, remarks=''):
    previous = invoice.approval_status
    invoice.approval_status = STATUS_REJECTED
    invoice.rejected_by = user
    invoice.rejected_at = timezone.now()
    invoice.rejection_reason = rejection_reason
    if remarks:
        invoice.approval_remarks = remarks
    invoice.save(update_fields=[
        'approval_status', 'rejected_by', 'rejected_at',
        'rejection_reason', 'approval_remarks',
    ])
    log_approval_action(
        invoice, ACTION_REJECTED, user,
        previous_status=previous,
        new_status=STATUS_REJECTED,
        remarks=remarks,
        rejection_reason=rejection_reason,
    )
