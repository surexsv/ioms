from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)


def can_override_invoice_gst(user):
    """Director and Accounts may override GST type on invoices."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (ROLE_DIRECTOR, ROLE_ACCOUNTS)


def can_view_invoices(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_ACCOUNTS, ROLE_OPERATIONS,
        ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR,
    )


def can_create_invoice(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user_role(user) in (ROLE_DIRECTOR, ROLE_ACCOUNTS, ROLE_OPERATIONS)


def can_edit_invoice(user, invoice=None):
    if not can_create_invoice(user):
        return False
    if invoice is None:
        return True
    from billing.approval import EDITABLE_STATUSES, LOCKED_STATUSES
    return invoice.approval_status in EDITABLE_STATUSES and invoice.approval_status not in LOCKED_STATUSES


def can_unlock_invoice(user, invoice=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user_role(user) != ROLE_DIRECTOR:
        return False
    if invoice is None:
        return True
    from billing.approval import LOCKED_STATUSES, STATUS_APPROVED
    return invoice.approval_status in LOCKED_STATUSES and invoice.approval_status == STATUS_APPROVED


def can_submit_invoice(user, invoice=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user_role(user) not in (ROLE_DIRECTOR, ROLE_ACCOUNTS, ROLE_OPERATIONS):
        return False
    if invoice is None:
        return True
    from billing.approval import SUBMITTABLE_STATUSES
    return invoice.approval_status in SUBMITTABLE_STATUSES


def can_approve_invoice(user, invoice=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user_role(user) not in (ROLE_DIRECTOR, ROLE_ACCOUNTS):
        return False
    if invoice is None:
        return True
    from billing.approval import APPROVABLE_STATUSES
    return invoice.approval_status in APPROVABLE_STATUSES


def can_download_invoice_pdf(user, invoice):
    from billing.approval import can_generate_pdf, PDF_BLOCKED_MESSAGE
    if not can_view_invoices(user):
        return False, 'You do not have permission to access invoices.'
    if not can_generate_pdf(invoice):
        return False, PDF_BLOCKED_MESSAGE
    return True, ''
