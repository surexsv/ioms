from django.core.management.base import BaseCommand

from accounts.permissions import _ACCESS
from accounts.rbac_models import MenuItem, RolePermission, SystemPermission, SystemRole
from accounts.rbac_service import invalidate_rbac_cache
from accounts.roles import (
    ROLE_ACCOUNTS,
    ROLE_ACCOUNTS_EXECUTIVE,
    ROLE_BACK_OFFICE,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
)

ROLE_META = {
    ROLE_DIRECTOR: (10, 'Director'),
    ROLE_OPERATIONS: (20, 'Operations Manager'),
    ROLE_PROJECT_MANAGER: (30, 'Project Manager'),
    ROLE_SUPERVISOR: (40, 'Project Supervisor'),
    ROLE_ENGINEER: (50, 'Field Engineer'),
    ROLE_TECHNICIAN: (51, 'Field Technician'),
    ROLE_ACCOUNTS: (60, 'Accounts Manager'),
    ROLE_ACCOUNTS_EXECUTIVE: (70, 'Accounts Executive'),
    ROLE_BACK_OFFICE: (80, 'Back Office Staff'),
}

PERMISSION_LABELS = {
    'dashboard_director': 'Director Dashboard',
    'dashboard_operations': 'Operations Dashboard',
    'dashboard_accounts': 'Accounts Dashboard',
    'dashboard_engineer': 'Field Team Dashboard',
    'dashboard_supervisor': 'Project Supervisor Dashboard',
    'dashboard_project_manager': 'Project Manager Dashboard',
    'clients': 'View Clients',
    'enquiries': 'View Enquiries',
    'enquiries_manage': 'Manage Enquiries',
    'estimate_boq': 'Estimate BOQ',
    'orders': 'View Orders',
    'orders_create': 'Create Orders',
    'wcr': 'Work Completion Reports',
    'wcr_approve': 'Approve WCR',
    'boq': 'BOQ',
    'manage_billing': 'Manage Billing',
    'attendance_manage': 'Manage Attendance',
    'attendance_self': 'Own Attendance (My Attendance)',
    'attendance_team': 'Team Attendance Monitoring',
    'attendance_supervisor_team': 'Assigned Team Attendance View',
    'view_attendance_audit_data': 'View Attendance Audit Data (Photos & GPS)',
    'quotations': 'Quotations',
    'quotation_rates': 'Quotation Rates',
    'financial': 'Financial Reports',
    'document_generator': 'Document Numbers',
    'company_settings': 'Company Settings',
    'scheduling': 'View Schedules',
    'scheduling_manage': 'Manage Schedules',
    'scheduling_field_update': 'Field Team Schedule Updates',
    'user_approval': 'User Approvals',
    'user_management': 'User Management (Admin)',
    'site_progress': 'Site Progress',
    'productivity': 'Productivity Module',
    'case_intelligence': 'Case Intelligence',
    'daily_meetings': 'Daily Meetings',
    'daily_meetings_manage': 'Manage Daily Meetings',
    'erms': 'Employee Requests',
    'erms_approve': 'Approve Employee Requests',
    'erms_view_all': 'View All Employee Requests',
    'erms_financial_approve': 'Approve Financial Employee Requests',
    'preventive_maintenance': 'Preventive Maintenance',
    'preventive_maintenance_approve': 'Approve Preventive Maintenance',
}

MENU_SEED = [
    ('Dashboard', 'dashboard', 'bi-speedometer2', None, 10),
    ('Orders', 'order_list', 'bi-clipboard-check', 'orders', 20),
    ('Scheduling', 'schedule_list', 'bi-calendar-event', 'scheduling', 25),
    ('Preventive Maintenance', 'pm_dashboard', 'bi-tools', 'preventive_maintenance', 26),
    ('BOQ', 'boq_list', 'bi-list-check', 'boq', 30),
    ('WCR', 'wcr_list', 'bi-file-earmark-text', 'wcr', 35),
    ('Clients', 'client_list', 'bi-people', 'clients', 40),
    ('Quotations', 'quotation_list', 'bi-file-earmark-ruled', 'quotations', 50),
    ('Billing', 'invoice_list', 'bi-receipt', 'manage_billing', 60),
    ('Manual Invoice Import', 'invoice_import_upload', 'bi-upload', 'manage_billing', 62),
    ('Invoice Import History', 'invoice_import_history', 'bi-clock-history', 'manage_billing', 63),
    ('Payments', 'invoice_list', 'bi-cash-coin', 'manage_billing', 61),
    ('Attendance Management', 'attendance_dashboard', 'bi-calendar-check', 'attendance_manage', 90),
    ('My Attendance', 'my_attendance', 'bi-person-check', 'attendance_self', 91),
    ('Team Attendance', 'attendance_team', 'bi-people', 'attendance_team', 92),
    ('Productivity', 'productivity_dashboard', 'bi-graph-up-arrow', 'productivity', 110),
    ('GPS Tracking', 'gps_dashboard', 'bi-geo-alt', 'productivity', 120),
    ('Company Settings', 'company_settings', 'bi-building-gear', 'company_settings', 130),
    ('User Approvals', 'user_approval_list', 'bi-person-check', 'user_approval', 140),
    ('Case Intelligence', 'case_stuck_dashboard', 'bi-diagram-3', 'case_intelligence', 145),
    ('Daily Meetings', 'dom_dashboard', 'bi-people-fill', 'daily_meetings', 148),
    ('Requests', 'erms_dashboard', 'bi-inbox', 'erms', 149),
    ('My Requests', 'erms_my_requests', 'bi-file-earmark-person', 'erms', 150),
    ('Pending Approvals', 'erms_pending_approvals', 'bi-hourglass-split', 'erms_approve', 151),
    ('Request Reports', 'erms_reports', 'bi-clipboard-data', 'erms', 152),
]


class Command(BaseCommand):
    help = 'Seed RBAC roles, permissions, role-permission map, and menu items from static _ACCESS.'

    def handle(self, *args, **options):
        # Superuser pseudo-role for admin UI reference
        SystemRole.objects.update_or_create(
            codename='SUPERUSER',
            defaults={
                'name': 'Admin / Super User',
                'hierarchy_level': 0,
                'is_system': True,
                'description': 'Highest authority — full system control via Django superuser flag.',
            },
        )

        for codename, (level, name) in ROLE_META.items():
            SystemRole.objects.update_or_create(
                codename=codename,
                defaults={'name': name, 'hierarchy_level': level, 'is_system': True},
            )

        all_perm_codes = set()
        for perms in _ACCESS.values():
            all_perm_codes.update(perms)
        all_perm_codes.add('scheduling_field_update')
        all_perm_codes.add('user_management')

        for code in sorted(all_perm_codes):
            category = code.split('_')[0] if '_' in code else 'general'
            SystemPermission.objects.update_or_create(
                codename=code,
                defaults={
                    'name': PERMISSION_LABELS.get(code, code.replace('_', ' ').title()),
                    'category': category,
                },
            )

        # Field team schedule update permission
        field_roles = (ROLE_ENGINEER, ROLE_TECHNICIAN)
        for role_code, perm_set in _ACCESS.items():
            role = SystemRole.objects.get(codename=role_code)
            RolePermission.objects.filter(role=role).delete()
            codes = set(perm_set)
            if role_code in field_roles:
                codes.add('scheduling_field_update')
            for code in codes:
                perm = SystemPermission.objects.get(codename=code)
                RolePermission.objects.get_or_create(role=role, permission=perm)

        # Director gets user_management for delegation tracking (actual access: superuser)
        director = SystemRole.objects.get(codename=ROLE_DIRECTOR)
        um, _ = SystemPermission.objects.get_or_create(
            codename='user_management',
            defaults={'name': 'User Management', 'category': 'admin'},
        )
        RolePermission.objects.get_or_create(role=director, permission=um)

        MenuItem.objects.all().delete()
        for label, url_name, icon, nav_key, order in MENU_SEED:
            perm_code = nav_key or 'dashboard_director'
            if label == 'Dashboard':
                perm_code = None
            perm = None
            if perm_code:
                perm = SystemPermission.objects.filter(codename=perm_code).first()
            MenuItem.objects.create(
                label=label,
                url_name=url_name,
                icon=icon,
                permission=perm,
                sort_order=order,
                nav_key=nav_key or 'dashboard',
            )

        invalidate_rbac_cache()
        self.stdout.write(self.style.SUCCESS('RBAC seeded successfully.'))
