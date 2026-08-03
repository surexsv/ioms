"""
Central role-based access control for IOMS.
Superusers always have full access (except explicit admin-only paths).
"""

from .roles import (
    ROLE_ACCOUNTS,
    ROLE_ACCOUNTS_EXECUTIVE,
    ROLE_BACK_OFFICE,
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
MODULE_MANAGE_BILLING = 'manage_billing'
# Legacy keys — retained for migration references only; not assigned in _ACCESS.
MODULE_BILLING = 'billing'
MODULE_BILLING_VIEW = 'billing_view'
MODULE_BILLING_CREATE = 'billing_create'
MODULE_ATTENDANCE_MANAGE = 'attendance_manage'
MODULE_ATTENDANCE_SELF = 'attendance_self'
MODULE_ATTENDANCE_TEAM = 'attendance_team'
MODULE_ATTENDANCE_SUPERVISOR_TEAM = 'attendance_supervisor_team'
MODULE_VIEW_ATTENDANCE_AUDIT_DATA = 'view_attendance_audit_data'
MODULE_QUOTATIONS = 'quotations'
MODULE_QUOTATION_RATES = 'quotation_rates'
MODULE_FINANCIAL = 'financial'
MODULE_DOCUMENT_GENERATOR = 'document_generator'
MODULE_COMPANY_SETTINGS = 'company_settings'
MODULE_SCHEDULING = 'scheduling'
MODULE_SCHEDULING_MANAGE = 'scheduling_manage'
MODULE_SCHEDULING_FIELD_UPDATE = 'scheduling_field_update'
MODULE_USER_APPROVAL = 'user_approval'
MODULE_USER_MANAGEMENT = 'user_management'
MODULE_SITE_PROGRESS = 'site_progress'
MODULE_PRODUCTIVITY = 'productivity'
MODULE_GPS_TRACKING = 'gps_tracking'
MODULE_CASE_INTELLIGENCE = 'case_intelligence'
MODULE_DAILY_MEETINGS = 'daily_meetings'
MODULE_DAILY_MEETINGS_MANAGE = 'daily_meetings_manage'
MODULE_ERMS = 'erms'
MODULE_ERMS_APPROVE = 'erms_approve'
MODULE_ERMS_VIEW_ALL = 'erms_view_all'
MODULE_ERMS_FINANCIAL_APPROVE = 'erms_financial_approve'
MODULE_SPECIAL_PROJECTS = 'special_projects'
MODULE_FLEET = 'fleet'
MODULE_PROJECT_EXPENSES = 'project_expenses'
MODULE_PROJECT_EXPENSES_APPROVE = 'project_expenses_approve'
MODULE_PROJECT_EXPENSES_MANAGE = 'project_expenses_manage'

# Role → allowed modules
_ACCESS = {
    ROLE_DIRECTOR: {
        MODULE_DASHBOARD_DIRECTOR,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ENQUIRIES_MANAGE, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ,
        MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF,
        MODULE_VIEW_ATTENDANCE_AUDIT_DATA,
        MODULE_QUOTATIONS, MODULE_QUOTATION_RATES, MODULE_FINANCIAL,
        MODULE_DOCUMENT_GENERATOR, MODULE_COMPANY_SETTINGS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_USER_APPROVAL, MODULE_SITE_PROGRESS, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS, MODULE_DAILY_MEETINGS_MANAGE,
        MODULE_ERMS, MODULE_ERMS_VIEW_ALL,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES, MODULE_PROJECT_EXPENSES_APPROVE, MODULE_PROJECT_EXPENSES_MANAGE,
    },
    ROLE_OPERATIONS: {
        MODULE_DASHBOARD_OPERATIONS,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ENQUIRIES_MANAGE, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ,
        MODULE_ATTENDANCE_SELF, MODULE_ATTENDANCE_TEAM,
        MODULE_QUOTATIONS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_SITE_PROGRESS, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS, MODULE_DAILY_MEETINGS_MANAGE,
        MODULE_ERMS, MODULE_ERMS_APPROVE,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES, MODULE_PROJECT_EXPENSES_APPROVE, MODULE_PROJECT_EXPENSES_MANAGE,
    },
    ROLE_PROJECT_MANAGER: {
        MODULE_DASHBOARD_PROJECT_MANAGER,
        MODULE_CLIENTS, MODULE_ENQUIRIES, MODULE_ESTIMATE_BOQ,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE,
        MODULE_QUOTATIONS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_ATTENDANCE_SELF, MODULE_ATTENDANCE_TEAM,
        MODULE_SITE_PROGRESS, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS, MODULE_DAILY_MEETINGS_MANAGE,
        MODULE_ERMS, MODULE_ERMS_APPROVE,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES, MODULE_PROJECT_EXPENSES_APPROVE, MODULE_PROJECT_EXPENSES_MANAGE,
    },
    ROLE_SUPERVISOR: {
        MODULE_DASHBOARD_SUPERVISOR,
        MODULE_CLIENTS, MODULE_ENQUIRIES,
        MODULE_ORDERS, MODULE_ORDERS_CREATE,
        MODULE_WCR, MODULE_WCR_APPROVE, MODULE_BOQ,
        MODULE_ATTENDANCE_SELF, MODULE_ATTENDANCE_SUPERVISOR_TEAM,
        MODULE_QUOTATIONS,
        MODULE_SCHEDULING, MODULE_SCHEDULING_MANAGE,
        MODULE_SITE_PROGRESS, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_ERMS, MODULE_ERMS_APPROVE,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES, MODULE_PROJECT_EXPENSES_APPROVE,
    },
    ROLE_ACCOUNTS: {
        MODULE_DASHBOARD_ACCOUNTS,
        MODULE_CLIENTS, MODULE_BOQ, MODULE_MANAGE_BILLING,
        MODULE_ATTENDANCE_SELF, MODULE_ATTENDANCE_MANAGE,
        MODULE_QUOTATION_RATES, MODULE_FINANCIAL,
        MODULE_SCHEDULING, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS,
        MODULE_ERMS, MODULE_ERMS_APPROVE, MODULE_ERMS_FINANCIAL_APPROVE,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES, MODULE_PROJECT_EXPENSES_APPROVE, MODULE_PROJECT_EXPENSES_MANAGE,
    },
    ROLE_ENGINEER: {
        MODULE_DASHBOARD_ENGINEER,
        MODULE_ORDERS, MODULE_WCR, MODULE_ATTENDANCE_SELF,
        MODULE_SCHEDULING, MODULE_SCHEDULING_FIELD_UPDATE, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS,
        MODULE_ERMS,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES,
    },
    ROLE_TECHNICIAN: {
        MODULE_DASHBOARD_ENGINEER,
        MODULE_ORDERS, MODULE_WCR, MODULE_ATTENDANCE_SELF,
        MODULE_SCHEDULING, MODULE_SCHEDULING_FIELD_UPDATE, MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS,
        MODULE_ERMS,
        MODULE_SPECIAL_PROJECTS,
        MODULE_FLEET,
        MODULE_PROJECT_EXPENSES,
    },
    ROLE_ACCOUNTS_EXECUTIVE: {
        MODULE_DASHBOARD_ACCOUNTS,
        MODULE_ATTENDANCE_SELF,
        MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS,
        MODULE_ERMS,
    },
    ROLE_BACK_OFFICE: {
        MODULE_DASHBOARD_OPERATIONS,
        MODULE_ENQUIRIES,
        MODULE_ATTENDANCE_SELF,
        MODULE_PRODUCTIVITY,
        MODULE_CASE_INTELLIGENCE,
        MODULE_DAILY_MEETINGS,
        MODULE_ERMS,
    },
}

_ALL_MODULES = set().union(*_ACCESS.values())


def has_full_access(user):
    return user.is_authenticated and user.is_superuser


def can_access(user, module_key):
    from accounts.enterprise_permissions import can_access_via_enterprise
    if module_key in (MODULE_ATTENDANCE_TEAM, MODULE_ATTENDANCE_SUPERVISOR_TEAM):
        if can_access_via_enterprise(user, MODULE_ATTENDANCE_MANAGE):
            return True
        if module_key == MODULE_ATTENDANCE_TEAM and can_access_via_enterprise(user, MODULE_ATTENDANCE_TEAM):
            return True
        if module_key == MODULE_ATTENDANCE_SUPERVISOR_TEAM and can_access_via_enterprise(user, MODULE_ATTENDANCE_SUPERVISOR_TEAM):
            return True
    return can_access_via_enterprise(user, module_key)


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


def can_manage_billing(user):
    """Finance-only billing module — Admin/Superuser and Accounts Manager."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False
    return can_access(user, MODULE_MANAGE_BILLING)


def can_view_billing(user):
    return can_manage_billing(user)


def can_manage_attendance(user):
    return can_access(user, MODULE_ATTENDANCE_MANAGE)


def can_view_attendance_audit_data(user):
    """Photos, GPS, address, maps, and attendance audit details — Director and Admin only."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False
    return can_access(user, MODULE_VIEW_ATTENDANCE_AUDIT_DATA)


def can_view_team_attendance(user):
    return can_access(user, MODULE_ATTENDANCE_TEAM)


def show_nav_my_attendance(user):
    from attendance.permissions import user_requires_attendance
    return user_requires_attendance(user)


def show_nav_attendance_management(user):
    return can_manage_attendance(user)


def show_nav_team_attendance(user):
    """Team monitoring menu — for roles with team view but not full management."""
    return can_view_team_attendance(user) and not can_manage_attendance(user)


def can_view_own_attendance(user):
    from attendance.permissions import user_requires_attendance
    if user_requires_attendance(user):
        return True
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
    from accounts.enterprise_permissions import has_enterprise_permission, has_employee_profile
    if user.is_authenticated and user.is_superuser:
        return True
    if has_employee_profile(user):
        return (
            has_enterprise_permission(user, 'approval')
            or has_enterprise_permission(user, 'user_management')
        )
    return user.is_authenticated and user_role(user) == ROLE_DIRECTOR


def can_manage_users(user):
    """Full user CRUD — requires user_management permission or superuser."""
    from accounts.enterprise_permissions import has_enterprise_permission, has_employee_profile
    if user.is_authenticated and user.is_superuser:
        return True
    if has_employee_profile(user):
        return has_enterprise_permission(user, 'user_management')
    return False


def can_manage_site_progress(user):
    return can_access(user, MODULE_SITE_PROGRESS)


def can_view_productivity(user):
    from productivity.permissions import can_view_productivity as _can
    return can_access(user, MODULE_PRODUCTIVITY) and _can(user)


def attendance_nav_url(user):
    """Legacy single-link helper — prefer separate nav items."""
    if show_nav_my_attendance(user):
        return 'my_attendance'
    if show_nav_attendance_management(user):
        return 'attendance_dashboard'
    if can_view_team_attendance(user):
        return 'attendance_team'
    return 'my_attendance'


def resolve_path_module(path):
    if path.startswith('/billing/'):
        return MODULE_MANAGE_BILLING
    if path.startswith('/enquiries/'):
        return None
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
        if path.startswith('/attendance/photos/'):
            return MODULE_VIEW_ATTENDANCE_AUDIT_DATA
        if '/reports/location' in path or '/reports/photo' in path:
            return MODULE_VIEW_ATTENDANCE_AUDIT_DATA
        self_paths = ('/attendance/my/', '/attendance/check-in/', '/attendance/check-out/')
        if any(path.startswith(p) for p in self_paths):
            return MODULE_ATTENDANCE_SELF
        if path.startswith('/attendance/team'):
            return None
        import re
        if re.match(r'^/attendance/\d+/?$', path):
            return None
        return MODULE_ATTENDANCE_MANAGE
    if path.startswith('/document-generator/'):
        return MODULE_DOCUMENT_GENERATOR
    if path.startswith('/company-settings/'):
        return MODULE_COMPANY_SETTINGS
    if path.startswith('/scheduling/'):
        return MODULE_SCHEDULING
    if path.startswith('/productivity/gps') or path.startswith('/productivity/field-activities'):
        return MODULE_GPS_TRACKING
    if path.startswith('/productivity/'):
        return MODULE_PRODUCTIVITY
    if path.startswith('/case-intelligence/'):
        return MODULE_CASE_INTELLIGENCE
    if path.startswith('/daily-meetings/'):
        manage_paths = (
            '/daily-meetings/meetings/create/',
            '/daily-meetings/meetings/today/',
            '/daily-meetings/agenda-template/',
            '/daily-meetings/open-items/create/',
        )
        if any(path.startswith(p) for p in manage_paths) or '/edit/' in path:
            return MODULE_DAILY_MEETINGS_MANAGE
        return MODULE_DAILY_MEETINGS
    if path.startswith('/requests/'):
        approve_paths = ('/requests/pending/', '/requests/reports/pending/')
        action_paths = ('/approve/', '/reject/', '/return/')
        if any(path.startswith(p) for p in approve_paths) or any(p in path for p in action_paths):
            return MODULE_ERMS_APPROVE
        return MODULE_ERMS
    if path.startswith('/special-projects/'):
        return MODULE_SPECIAL_PROJECTS
    if path.startswith('/fleet/'):
        return MODULE_FLEET
    if path.startswith('/project-expenses/'):
        return MODULE_PROJECT_EXPENSES
    if path.startswith('/user-approvals/'):
        return MODULE_USER_APPROVAL
    if path.startswith('/dashboard/'):
        if path.startswith('/dashboard/project-manager'):
            return MODULE_DASHBOARD_PROJECT_MANAGER
        if path.startswith('/dashboard/engineer') or path.startswith('/dashboard/field-team'):
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
    from accounts.enterprise_permissions import allowed_dashboard_for_user
    return allowed_dashboard_for_user(user)
