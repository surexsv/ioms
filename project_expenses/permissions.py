from accounts.permissions import can_access
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)

from .models import ApprovalLimit, ProjectExpense

MODULE_PEAMS = 'project_expenses'
MODULE_PEAMS_APPROVE = 'project_expenses_approve'
MODULE_PEAMS_MANAGE = 'project_expenses_manage'


def can_view_peams(user):
    return can_access(user, MODULE_PEAMS)


def can_manage_peams(user):
    """Categories, advances issue, settings, settlements."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if can_access(user, MODULE_PEAMS_MANAGE):
        return True
    return user_role(user) in (
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_ACCOUNTS, ROLE_PROJECT_MANAGER,
    )


def can_create_expense(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return can_access(user, MODULE_PEAMS)


def can_approve_step(user, step_code):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = user_role(user)
    if step_code == ApprovalLimit.STEP_DIRECTOR:
        return role == ROLE_DIRECTOR
    if step_code == ApprovalLimit.STEP_ACCOUNTS:
        return role in (ROLE_ACCOUNTS, ROLE_DIRECTOR)
    if step_code == ApprovalLimit.STEP_MANAGER:
        return role in (
            ROLE_PROJECT_MANAGER, ROLE_OPERATIONS, ROLE_SUPERVISOR,
            ROLE_DIRECTOR, ROLE_ACCOUNTS,
        )
    return can_access(user, MODULE_PEAMS_APPROVE)


def can_approve_expense(user, expense):
    if expense.status in (
        ProjectExpense.STATUS_APPROVED,
        ProjectExpense.STATUS_REJECTED,
        ProjectExpense.STATUS_PAID,
        ProjectExpense.STATUS_CLOSED,
        ProjectExpense.STATUS_DRAFT,
    ):
        return False
    step = expense.current_step
    if not step:
        if expense.status == ProjectExpense.STATUS_MANAGER:
            step = ApprovalLimit.STEP_MANAGER
        elif expense.status == ProjectExpense.STATUS_ACCOUNTS:
            step = ApprovalLimit.STEP_ACCOUNTS
        elif expense.status == ProjectExpense.STATUS_DIRECTOR:
            step = ApprovalLimit.STEP_DIRECTOR
    return can_approve_step(user, step)
