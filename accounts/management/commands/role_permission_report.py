"""Generate Role-Permission Matrix report as JSON."""

import json
from types import SimpleNamespace

from django.core.management.base import BaseCommand

from accounts import permissions as ap
from accounts.context_processors import oms_navigation
from accounts.permissions import allowed_dashboard_url_name
from billing import permissions as bp
from company_settings import permissions as cp
from document_generator import permissions as dp
from productivity import permissions as pp
from quotations import permissions as qp
from scheduling import permissions as sp


ROLES = [
    ('SUPERUSER', 'Admin / Super User', True),
    ('DIRECTOR', 'Director', False),
    ('OPERATIONS', 'Operations Manager', False),
    ('PROJECT_MANAGER', 'Project Manager', False),
    ('SUPERVISOR', 'Project Supervisor', False),
    ('ENGINEER', 'Field Engineer', False),
    ('Technician', 'Field Technician', False),
    ('ACCOUNTS', 'Accounts Manager', False),
    ('ACCOUNTS_EXECUTIVE', 'Accounts Executive', False),
    ('BACK_OFFICE', 'Back Office Staff', False),
]

MODULE_CHECKS = [
    ('Dashboard', 'dashboard', 'View', lambda u: ap.can_view_dashboard(u)),
    ('Director Dashboard', 'dashboard_director', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_DIRECTOR)),
    ('Operations Dashboard', 'dashboard_operations', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_OPERATIONS)),
    ('Accounts Dashboard', 'dashboard_accounts', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_ACCOUNTS)),
    ('Field Team Dashboard', 'dashboard_engineer', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_ENGINEER)),
    ('Supervisor Dashboard', 'dashboard_supervisor', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_SUPERVISOR)),
    ('PM Dashboard', 'dashboard_project_manager', 'View', lambda u: ap.can_access(u, ap.MODULE_DASHBOARD_PROJECT_MANAGER)),
    ('Clients', 'clients', 'View', ap.can_view_clients),
    ('Clients', 'clients', 'Create', ap.can_view_clients),
    ('Clients', 'clients', 'Edit', ap.can_view_clients),
    ('Clients', 'clients', 'Delete', lambda u: False),
    ('Enquiries', 'enquiries', 'View', ap.can_view_enquiries),
    ('Enquiries', 'enquiries', 'Create', ap.can_manage_enquiries),
    ('Enquiries', 'enquiries', 'Edit', ap.can_manage_enquiries),
    ('Enquiries', 'enquiries', 'Delete', lambda u: False),
    ('Enquiries', 'enquiries', 'Convert to Order', ap.can_manage_enquiries),
    ('Estimate BOQ', 'estimate_boq', 'View', ap.can_view_estimate_boq),
    ('Estimate BOQ', 'estimate_boq', 'Create/Edit', lambda u: ap.can_view_estimate_boq(u) and ap.can_manage_enquiries(u)),
    ('Orders', 'orders', 'View', ap.can_view_orders),
    ('Orders', 'orders', 'Create', ap.can_create_orders),
    ('Orders', 'orders', 'Edit', ap.can_view_orders),
    ('Orders', 'orders', 'Delete', lambda u: False),
    ('Schedules', 'scheduling', 'View', sp.can_view_scheduling),
    ('Schedules', 'scheduling', 'Create/Manage', sp.can_manage_scheduling),
    ('Schedules', 'scheduling', 'Edit (Management)', sp.can_manage_scheduling),
    ('Schedules', 'scheduling', 'Field Update (Assigned)', lambda u: ap.can_access(u, ap.MODULE_SCHEDULING_FIELD_UPDATE)),
    ('Schedules', 'scheduling', 'Delete', lambda u: False),
    ('WCR', 'wcr', 'View', ap.can_view_wcr),
    ('WCR', 'wcr', 'Create/Submit', ap.can_view_wcr),
    ('WCR', 'wcr', 'Edit', ap.can_view_wcr),
    ('WCR', 'wcr', 'Approve', lambda u: ap.can_access(u, ap.MODULE_WCR_APPROVE)),
    ('WCR', 'wcr', 'Delete', lambda u: False),
    ('BOQ', 'boq', 'View', ap.can_view_boq),
    ('BOQ', 'boq', 'Create/Edit', ap.can_view_boq),
    ('BOQ', 'boq', 'Delete', lambda u: False),
    ('Billing / Invoices', 'manage_billing', 'View', bp.can_view_invoices),
    ('Billing / Invoices', 'manage_billing', 'Create', bp.can_create_invoice),
    ('Billing / Invoices', 'manage_billing', 'Edit', bp.can_create_invoice),
    ('Billing / Invoices', 'manage_billing', 'Approve', bp.can_approve_invoice),
    ('Billing / Invoices', 'manage_billing', 'Export PDF', bp.can_view_invoices),
    ('Billing / Invoices', 'manage_billing', 'Delete', lambda u: False),
    ('Attendance', 'attendance', 'View (Team)', ap.can_manage_attendance),
    ('Attendance', 'attendance', 'Create/Edit (Team)', ap.can_manage_attendance),
    ('Attendance', 'attendance', 'View (Own)', ap.can_view_own_attendance),
    ('Attendance', 'attendance', 'Check-In/Out', ap.can_view_own_attendance),
    ('Quotations', 'quotations', 'View', qp.can_view_quotations),
    ('Quotations', 'quotations', 'Create/Edit', qp.can_edit_quotations),
    ('Quotations', 'quotations', 'Approve', qp.can_approve_quotations),
    ('Quotations', 'quotations', 'Delete', lambda u: False),
    ('Quotation Rates', 'quotation_rates', 'View/Manage', qp.can_manage_rate_cards),
    ('Quotation Settings', 'quotations', 'Manage Templates', qp.can_manage_quotation_settings),
    ('Financial Reports', 'financial', 'View', ap.can_view_financial),
    ('Financial Reports', 'financial', 'Export', ap.can_view_financial),
    ('Document Numbers', 'document_generator', 'View', dp.can_view_document_generator),
    ('Document Numbers', 'document_generator', 'Edit', dp.can_manage_document_generator),
    ('Company Settings', 'company_settings', 'View', cp.can_view_company_settings),
    ('Company Settings', 'company_settings', 'Edit', cp.can_manage_company_settings),
    ('User Approvals', 'user_approval', 'View/Approve', ap.can_manage_user_approvals),
    ('User Management (Django Admin)', 'user_management', 'Create', ap.can_manage_users),
    ('User Management (Django Admin)', 'user_management', 'Edit', ap.can_manage_users),
    ('User Management (Django Admin)', 'user_management', 'Delete', ap.can_manage_users),
    ('User Management (Django Admin)', 'user_management', 'Activate/Deactivate', ap.can_manage_users),
    ('Site Progress', 'site_progress', 'Create', ap.can_manage_site_progress),
    ('Productivity Module', 'productivity', 'Access', pp.can_view_productivity),
    ('Productivity Dashboard', 'productivity', 'Management View', pp.can_view_management_productivity),
    ('Productivity', 'productivity', 'Company-Wide', pp.can_view_full_productivity),
    ('Productivity', 'productivity', 'Team View', pp.can_view_team_productivity),
    ('Productivity', 'productivity', 'Activity Log', pp.can_view_activity_log),
    ('GPS Dashboard', 'productivity', 'View', pp.can_view_gps_dashboard),
    ('Field Activity Log', 'productivity', 'View', pp.can_view_field_activity_log),
    ('Productivity Reports', 'productivity', 'Export CSV/PDF', pp.can_export_reports),
]

MENU_CHECKS = [
    ('Dashboard', 'show_nav_dashboard'),
    ('Enquiries', 'show_nav_enquiries'),
    ('Orders', 'show_nav_orders'),
    ('Clients', 'show_nav_clients'),
    ('Quotations', 'show_nav_quotations'),
    ('WCR', 'show_nav_wcr'),
    ('BOQ', 'show_nav_boq'),
    ('Billing', 'show_nav_billing'),
    ('My Attendance', 'show_nav_my_attendance'),
    ('Attendance Management', 'show_nav_attendance_management'),
    ('Team Attendance', 'show_nav_team_attendance'),
    ('Doc Numbers', 'show_nav_document_numbers'),
    ('Company Settings', 'show_nav_company_settings'),
    ('User Approvals', 'show_nav_user_approvals'),
    ('Schedules', 'show_nav_schedules'),
    ('Productivity', 'show_nav_productivity'),
    ('GPS Tracking', 'show_nav_gps'),
]


def _make_user(code, is_superuser):
    u = SimpleNamespace()
    u.is_authenticated = True
    u.is_superuser = is_superuser
    u.is_active = True
    u.is_active_employee = True
    u.is_profile_approved = True
    u.approval_status = 'APPROVED'
    u.role = 'DIRECTOR' if code == 'SUPERUSER' else code
    u.username = code.lower()
    u.get_role_display = lambda: code
    u.get_full_name = lambda: code
    return u


class _Req(SimpleNamespace):
    path = '/'


class Command(BaseCommand):
    help = 'Export Role-Permission Matrix to ROLE_PERMISSION_MATRIX.json'

    def handle(self, *args, **options):
        permissions = []
        menus = []
        dashboards = []

        for code, name, is_su in ROLES:
            user = _make_user(code, is_su)
            nav = oms_navigation(_Req(user=user))
            dashboards.append({
                'role': name,
                'role_code': code,
                'default_dashboard': allowed_dashboard_url_name(user),
            })
            for label, key in MENU_CHECKS:
                menus.append({
                    'role': name,
                    'role_code': code,
                    'menu': label,
                    'visible': bool(nav.get(key)),
                })
            for module, perm_key, action, check in MODULE_CHECKS:
                permissions.append({
                    'role': name,
                    'role_code': code,
                    'module': module,
                    'permission_key': perm_key,
                    'action': action,
                    'allowed': bool(check(user)),
                })

        report = {
            'title': 'IOMS Role-Permission Matrix',
            'version': '1.4.1',
            'roles': [{'code': c, 'name': n} for c, n, _ in ROLES],
            'dashboards': dashboards,
            'menus': menus,
            'permissions': permissions,
        }

        path = 'ROLE_PERMISSION_MATRIX.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        self.stdout.write(self.style.SUCCESS(f'Wrote {path} ({len(permissions)} permission cells)'))
