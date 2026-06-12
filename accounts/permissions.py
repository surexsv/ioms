"""
Central role-based access control for IOMS.
Superusers always have full access (except explicit admin-only paths).
"""

from .roles import (
    ROLE_ACCOUNTS,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    user_role,
)

# Module keys used by decorators and middleware
MODULE_DASHBOARD_DIRECTOR = 'dashboard_director'
MODULE_DASHBOARD_OPERATIONS = 'dashboard_operations'
MODULE_DASHBOARD_ACCOUNTS = 'dashboard_accounts'
MODULE_DASHBOARD_ENGINEER = 'dashboard_engineer'
MODULE_DASHBOARD_SUPERVISOR = 'dashboard_supervisor'
MODULE_DASHBOARD_PROJECT_MANAGER = 'dashboard_project_manager'
MODULE_CLIENTS = 'clients'
MODULE_ENQUIRIES = 'enquiries'
MODULE_ENQUIRIES_MANAGE = 'enquiries_manage'
MODULE_ESTIMATE_BOQ = 'estimate_boq'
MODULE_ORDERS = 'orders'
MODULE_ORDERS_CREATE = 'orders_create'
MODULE_WCR = 'wcr'
MODULE_WCR_APPROVE = 'wcr_approve'
MODULE_BOQ = 'boq'
MODULE_BILLING = 'billing'
MODULE_BILLING_VIEW = 'billing_view'
MODULE_BILLING_CREATE = 'billing_create'
MODULE_ATTENDANCE_MANAGE = 'attendance_manage'
MODULE_ATTENDANCE_SELF = 'attendance_self'
MODULE_QUOTATIONS = 'quotations'
MODULE_QUOTATION_RATES = 'quotation_rates'
MODULE_FINANCIAL = 'financial'
MODULE_DOCUMENT_GENERATOR = 'document_generator'
MODULE_COMPANY_SETTINGS = 'company_settings'
MODULE_SCHEDULING = 'scheduling'
MODULE_SCHEDULING_MANAGE = 'scheduling_manage'
MODULE_USER_APPROVAL = 'user_approval'
MODULE_SITE_PROGRESS = 'site_progress'

# Role → allowed modules
_ACCESS = {
    ROLE_DIRECTOR: {
        MODULE_DASHBOARD_DIRECTOR,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ENQUIRIES_MANAGE, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ, MODULE_BILLING,
        MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF,
        MODULE_QUOTATIONS, MODULE_QUOTATION_RATES, MODULE_FINANCIAL,
        MODULE_DOCUMENT_GENERATOR, MODULE_COMPANY_SETTINGS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_USER_APPROVAL, MODULE_SITE_PROGRESS,
    },
    ROLE_OPERATIONS: {
        MODULE_DASHBOARD_OPERATIONS,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ENQUIRIES_MANAGE, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ,
        MODULE_BILLING_CREATE,
        MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF,
        MODULE_QUOTATIONS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_SITE_PROGRESS,
    },
    ROLE_PROJECT_MANAGER: {
        MODULE_DASHBOARD_PROJECT_MANAGER,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE,
        MODULE_QUOTATIONS,
        MODULE_BILLING_VIEW,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF,
        MODULE_SITE_PROGRESS,
    },
    ROLE_SUPERVISOR: {
        MODULE_DASHBOARD_SUPERVISOR,
        MODULE_CLIENTS, MODULE_ENQUIRIES,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ,
        MODULE_BILLING_VIEW,
        MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF,
        MODULE_QUOTATIONS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_SITE_PROGRESS,
    },
    ROLE_ACCOUNTS: {
        MODULE_DASHBOARD_ACCOUNTS,
        MODULE_CLIENTS, MODULE_BOQ, MODULE_BILLING,
        MODULE_ATTENDANCE_SELF,
        MODULE_QUOTATION_RATES, MODULE_FINANCIAL,
        MODULE_SCHEDULING,
    },
    ROLE_ENGINEER: {
        MODULE_DASHBOARD_ENGINEER,
        MODULE_ORDERS, MODULE_WCR, MODULE_ATTENDANCE_SELF,
        MODULE_SCHEDULING,
    },
    ROLE_TECHNICIAN: {
        MODULE_DASHBOARD_ENGINEER,
        MODULE_ORDERS, MODULE_WCR, MODULE_ATTENDANCE_SELF,
        MODULE_SCHEDULING,
    },
}

_ALL_MODULES = set().union(*_ACCESS.values())


def has_full_access(user):
    return user.is_authenticated and user.is_superuser


def can_access(user, module_key):
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False
    role = user_role(user)
    return module_key in _ACCESS.get(role, set())


def user_modules(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return _ALL_MODULES
    return _ACCESS.get(user_role(user), set())


def can_view_dashboard(user):
    return has_full_access(user) or bool(
        user_modules(user)
        & {
            MODULE_DASHBOARD_DIRECTOR,
            MODULE_DASHBOARD_OPERATIONS,
            MODULE_DASHBOARD_ACCOUNTS,
            MODULE_DASHBOARD_ENGINEER,
            MODULE_DASHBOARD_SUPERVISOR,
            MODULE_DASHBOARD_PROJECT_MANAGER,
        }
    )


def can_view_clients(user):
    return can_access(user, MODULE_CLIENTS)


def can_view_enquiries(user):
    return can_access(user, MODULE_ENQUIRIES)


def can_manage_enquiries(user):
    return can_access(user, MODULE_ENQUIRIES_MANAGE)


def can_view_estimate_boq(user):
    return can_access(user, MODULE_ESTIMATE_BOQ)


def can_view_orders(user):
    return can_access(user, MODULE_ORDERS)


def can_create_orders(user):
    return can_access(user, MODULE_ORDERS_CREATE)


def can_view_wcr(user):
    return can_access(user, MODULE_WCR)


def can_view_boq(user):
    return can_access(user, MODULE_BOQ)


def can_view_billing(user):
    return (
        can_access(user, MODULE_BILLING)
        or can_access(user, MODULE_BILLING_VIEW)
        or can_access(user, MODULE_BILLING_CREATE)
    )


def can_manage_attendance(user):
    return can_access(user, MODULE_ATTENDANCE_MANAGE)


def can_view_own_attendance(user):
    return can_access(user, MODULE_ATTENDANCE_SELF)


def can_view_quotations(user):
    return can_access(user, MODULE_QUOTATIONS)


def can_manage_quotation_rates(user):
    return can_access(user, MODULE_QUOTATION_RATES)


def can_view_financial(user):
    return can_access(user, MODULE_FINANCIAL)


def can_view_company_settings(user):
    return can_access(user, MODULE_COMPANY_SETTINGS)


def can_manage_user_approvals(user):
    return user.is_authenticated and (
        user.is_superuser or user_role(user) == ROLE_DIRECTOR
    )


def can_manage_site_progress(user):
    return can_access(user, MODULE_SITE_PROGRESS)


def attendance_nav_url(user):
    if can_manage_attendance(user):
        return 'attendance_dashboard'
    return 'my_attendance'


def resolve_path_module(path):
    if path.startswith('/billing/'):
        return MODULE_BILLING
    if path.startswith('/enquiries/'):
        return MODULE_ENQUIRIES
    if path.startswith('/estimate-boq/'):
        return MODULE_ESTIMATE_BOQ
    if path.startswith('/clients/'):
        return MODULE_CLIENTS
    if path.startswith('/orders/'):
        return MODULE_ORDERS
    if path.startswith('/wcr/'):
        return MODULE_WCR
    if path.startswith('/boq/'):
        return MODULE_BOQ
    if path.startswith('/quotations/rates/'):
        return MODULE_QUOTATION_RATES
    if path.startswith('/quotations/'):
        return MODULE_QUOTATIONS
    if path.startswith('/attendance/'):
        self_paths = ('/attendance/my/', '/attendance/check-in/', '/attendance/check-out/')
        if any(path.startswith(p) for p in self_paths):
            return MODULE_ATTENDANCE_SELF
        return MODULE_ATTENDANCE_MANAGE
    if path.startswith('/document-generator/'):
        return MODULE_DOCUMENT_GENERATOR
    if path.startswith('/company-settings/'):
        return MODULE_COMPANY_SETTINGS
    if path.startswith('/scheduling/'):
        return MODULE_SCHEDULING
    if path.startswith('/user-approvals/'):
        return MODULE_USER_APPROVAL
    if path.startswith('/dashboard/'):
        if path.startswith('/dashboard/project-manager'):
            return MODULE_DASHBOARD_PROJECT_MANAGER
        if path.startswith('/dashboard/engineer'):
            return MODULE_DASHBOARD_ENGINEER
        if path.startswith('/dashboard/supervisor'):
            return MODULE_DASHBOARD_SUPERVISOR
        if path.startswith('/dashboard/operations'):
            return MODULE_DASHBOARD_OPERATIONS
        if path.startswith('/dashboard/accounts'):
            return MODULE_DASHBOARD_ACCOUNTS
        return MODULE_DASHBOARD_DIRECTOR
    return None


def allowed_dashboard_url_name(user):
    if has_full_access(user) or user_role(user) == ROLE_DIRECTOR:
        return 'director_dashboard'
    if user_role(user) == ROLE_OPERATIONS:
        return 'operations_dashboard'
    if user_role(user) == ROLE_ACCOUNTS:
        return 'accounts_dashboard'
    if user_role(user) == ROLE_PROJECT_MANAGER:
        return 'project_manager_dashboard'
    if user_role(user) in (ROLE_ENGINEER, ROLE_TECHNICIAN):
        return 'engineer_dashboard'
    if user_role(user) == ROLE_SUPERVISOR:
        return 'supervisor_dashboard'
    return 'login'
