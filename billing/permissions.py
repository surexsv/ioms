"""Billing permissions — RBAC via manage_billing only."""

from accounts.permissions import can_manage_billing


def can_override_invoice_gst(user):
    return can_manage_billing(user)


def can_view_invoices(user):
    return can_manage_billing(user)


def can_create_invoice(user):
    return can_manage_billing(user)


def can_edit_invoice(user, invoice=None):
    if not can_manage_billing(user):
        return False
    if invoice is None:
        return True
    from billing.approval import EDITABLE_STATUSES, LOCKED_STATUSES
    return invoice.approval_status in EDITABLE_STATUSES and invoice.approval_status not in LOCKED_STATUSES


def can_unlock_invoice(user, invoice=None):
    if not can_manage_billing(user):
        return False
    if invoice is None:
        return True
    from billing.approval import LOCKED_STATUSES, STATUS_APPROVED
    return invoice.approval_status in LOCKED_STATUSES and invoice.approval_status == STATUS_APPROVED


def can_submit_invoice(user, invoice=None):
    if not can_manage_billing(user):
        return False
    if invoice is None:
        return True
    from billing.approval import SUBMITTABLE_STATUSES
    return invoice.approval_status in SUBMITTABLE_STATUSES


def can_approve_invoice(user, invoice=None):
    if not can_manage_billing(user):
        return False
    if invoice is None:
        return True
    from billing.approval import APPROVABLE_STATUSES
    return invoice.approval_status in APPROVABLE_STATUSES


def can_download_invoice_pdf(user, invoice):
    from billing.approval import can_generate_pdf, PDF_BLOCKED_MESSAGE
    if not can_manage_billing(user):
        return False, 'You do not have permission to access invoices.'
    if not can_generate_pdf(invoice):
        return False, PDF_BLOCKED_MESSAGE
    return True, ''
