"""HTTP permission matrix — every role against every major IOMS feature."""

from django.test import TestCase
from django.urls import reverse

from accounts.enterprise_permissions import build_navigation_menu
from accounts.models import User
from accounts.permissions import (
    MODULE_ATTENDANCE_MANAGE,
    MODULE_ATTENDANCE_SELF,
    MODULE_BOQ,
    MODULE_CASE_INTELLIGENCE,
    MODULE_CLIENTS,
    MODULE_COMPANY_SETTINGS,
    MODULE_DAILY_MEETINGS,
    MODULE_DAILY_MEETINGS_MANAGE,
    MODULE_DASHBOARD_ACCOUNTS,
    MODULE_DASHBOARD_DIRECTOR,
    MODULE_DASHBOARD_ENGINEER,
    MODULE_DASHBOARD_OPERATIONS,
    MODULE_DASHBOARD_PROJECT_MANAGER,
    MODULE_DASHBOARD_SUPERVISOR,
    MODULE_DOCUMENT_GENERATOR,
    MODULE_ERMS,
    MODULE_ERMS_APPROVE,
    MODULE_ESTIMATE_BOQ,
    MODULE_ORDERS,
    MODULE_ORDERS_CREATE,
    MODULE_QUOTATIONS,
    MODULE_QUOTATION_RATES,
    MODULE_SCHEDULING,
    MODULE_USER_APPROVAL,
    MODULE_WCR,
    MODULE_WCR_APPROVE,
    allowed_dashboard_url_name,
    can_access,
    can_create_orders,
    can_manage_attendance,
    can_manage_user_approvals,
    can_view_boq,
    can_view_clients,
    can_view_estimate_boq,
    can_view_orders,
    can_view_wcr,
)
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
from attendance.permissions import (
    can_mark_own_attendance,
    can_view_team_attendance_page,
    default_attendance_required_for_role,
)
from billing.permissions import can_create_invoice, can_import_invoices, can_view_invoices
from case_intelligence.permissions import can_view_case_intelligence
from company_settings.permissions import can_view_company_settings
from daily_meetings.permissions import can_access_daily_meetings, can_manage_meetings
from document_generator.permissions import can_view_document_generator
from employee_requests.permissions import can_access_erms, can_approve_requests
from fleet.permissions import can_view_fleet
from productivity.permissions import can_view_gps_dashboard, can_view_management_productivity
from project_expenses.permissions import can_view_peams
from quotations.permissions import can_manage_rate_cards, can_view_quotations
from scheduling.permissions import can_view_scheduling
from special_projects.permissions import can_view_special_projects

PASSWORD = 'testpass123'

ROLES = (
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_ACCOUNTS,
    ROLE_ENGINEER,
    ROLE_TECHNICIAN,
    ROLE_ACCOUNTS_EXECUTIVE,
    ROLE_BACK_OFFICE,
)


def _denied(response):
    if response.status_code == 403:
        return True
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.url or response.get('Location', '') or ''
        return 'access-denied' in location
    return False


def _page_failed(response):
    return response.status_code >= 500


def _feature_checks():
    return (
        ('Director Dashboard', 'director_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_DIRECTOR)),
        ('Operations Dashboard', 'operations_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_OPERATIONS)),
        ('Accounts Dashboard', 'accounts_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_ACCOUNTS)),
        ('Field Team Dashboard', 'field_team_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_ENGINEER)),
        ('Supervisor Dashboard', 'supervisor_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_SUPERVISOR)),
        ('PM Dashboard', 'project_manager_dashboard', lambda u: can_access(u, MODULE_DASHBOARD_PROJECT_MANAGER)),
        ('Clients', 'client_list', can_view_clients),
        ('Create Client', 'create_client', can_view_clients),
        ('Orders', 'order_list', can_view_orders),
        ('Create Order', 'create_order', can_create_orders),
        ('Estimate BOQ', 'estimate_boq_list', can_view_estimate_boq),
        ('Schedules', 'schedule_list', can_view_scheduling),
        ('WCR', 'wcr_list', can_view_wcr),
        ('Create WCR', 'create_wcr', lambda u: can_access(u, MODULE_WCR)),
        ('BOQ', 'boq_list', can_view_boq),
        ('Create BOQ', 'create_boq', can_view_boq),
        ('Billing / Invoices', 'invoice_list', can_view_invoices),
        ('Create Invoice', 'create_invoice', can_create_invoice),
        ('Manual Invoice Import', 'invoice_import_upload', can_import_invoices),
        ('Invoice Import History', 'invoice_import_history', can_import_invoices),
        ('Invoice Import Template', 'invoice_import_template', can_import_invoices),
        ('Quotations', 'quotation_list', can_view_quotations),
        ('Create Quotation', 'quotation_create', can_view_quotations),
        ('Quotation Rates', 'service_rate_list', can_manage_rate_cards),
        ('My Attendance', 'my_attendance', lambda u: can_access(u, MODULE_ATTENDANCE_SELF)),
        ('Attendance Check-In', 'attendance_check_in', can_mark_own_attendance),
        ('Attendance Management', 'attendance_dashboard', can_manage_attendance),
        ('Team Attendance', 'attendance_team', can_view_team_attendance_page),
        ('Document Numbers', 'document_control_panel', lambda u: can_access(u, MODULE_DOCUMENT_GENERATOR)),
        ('Company Settings', 'company_settings', lambda u: can_access(u, MODULE_COMPANY_SETTINGS)),
        ('User Approvals', 'user_approval_list', can_manage_user_approvals),
        ('Productivity Dashboard', 'productivity_dashboard', can_view_management_productivity),
        ('GPS Tracking', 'gps_dashboard', can_view_gps_dashboard),
        ('Case Intelligence', 'case_stuck_dashboard', can_view_case_intelligence),
        ('Case Reports', 'case_reports', can_view_case_intelligence),
        ('Daily Meetings', 'dom_dashboard', can_access_daily_meetings),
        ('Create Daily Meeting', 'dom_meeting_create', can_manage_meetings),
        ('Employee Requests', 'erms_dashboard', can_access_erms),
        ('ERMS Pending Approvals', 'erms_pending_approvals', can_approve_requests),
        ('Special Projects', 'special_project_list', can_view_special_projects),
        ('Fleet & Fuel', 'fleet_dashboard', can_view_fleet),
        ('Project Expenses', 'peams_dashboard', can_view_peams),
    )


class RoleFeaturePermissionTests(TestCase):
    def setUp(self):
        self.users = {}
        for role in ROLES:
            username = role.lower().replace('_', '-')
            user = User.objects.create_user(
                username=username,
                password=PASSWORD,
                role=role,
                is_active_employee=True,
                approval_status=User.APPROVAL_APPROVED,
                attendance_required=default_attendance_required_for_role(role),
            )
            self.users[role] = user
        self.superuser = User.objects.create_superuser(
            username='admin',
            password=PASSWORD,
            email='admin@example.com',
        )

    def _assert_feature(self, user, label, url_name, allowed):
        url = reverse(url_name)
        self.client.force_login(user)
        response = self.client.get(url)
        identity = f'{user.username} → {label} ({url})'
        if _page_failed(response):
            self.fail(f'{identity} crashed with HTTP {response.status_code}')
        if allowed:
            self.assertFalse(
                _denied(response),
                msg=f'{identity} should be allowed, got HTTP {response.status_code} → {getattr(response, "url", "")}',
            )
            self.assertIn(
                response.status_code,
                {200, 301, 302, 303},
                msg=f'{identity} unexpected status {response.status_code}',
            )
        else:
            self.assertTrue(
                _denied(response),
                msg=f'{identity} should be denied, got HTTP {response.status_code} → {getattr(response, "url", "")}',
            )

    def test_every_role_against_every_feature(self):
        failures = []
        for role, user in self.users.items():
            for label, url_name, check in _feature_checks():
                allowed = bool(check(user))
                try:
                    self._assert_feature(user, label, url_name, allowed)
                except AssertionError as exc:
                    failures.append(str(exc))
        self.assertEqual(failures, [], msg='\n'.join(failures))

    def test_superuser_can_open_all_features_except_personal_attendance_marking(self):
        failures = []
        for label, url_name, check in _feature_checks():
            allowed = bool(check(self.superuser))
            if url_name == 'attendance_check_in':
                allowed = False
            try:
                self._assert_feature(self.superuser, label, url_name, allowed)
            except AssertionError as exc:
                failures.append(str(exc))
        self.assertEqual(failures, [], msg='\n'.join(failures))

    def test_anonymous_users_are_sent_to_login(self):
        for _label, url_name, _check in _feature_checks():
            url = reverse(url_name)
            response = self.client.get(url)
            self.assertIn(response.status_code, {301, 302, 303}, msg=url)
            location = response.url or ''
            self.assertIn('login', location, msg=f'{url} → {location}')

    def test_home_sends_each_role_to_their_dashboard(self):
        for role, user in list(self.users.items()) + [(None, self.superuser)]:
            self.client.force_login(user)
            response = self.client.get(reverse('home'))
            expected = reverse(allowed_dashboard_url_name(user))
            self.assertEqual(response.status_code, 302, msg=user.username)
            self.assertEqual(response.url, expected, msg=user.username)

    def test_billing_and_import_are_accounts_and_admin_only(self):
        billing_urls = (
            reverse('invoice_list'),
            reverse('create_invoice'),
            reverse('invoice_import_upload'),
            reverse('invoice_import_history'),
            reverse('invoice_import_template'),
        )
        allowed_users = {self.users[ROLE_ACCOUNTS], self.superuser}
        for user in list(self.users.values()) + [self.superuser]:
            self.client.force_login(user)
            for url in billing_urls:
                response = self.client.get(url)
                if user in allowed_users:
                    self.assertFalse(_denied(response), msg=f'{user.username} {url}')
                    self.assertFalse(_page_failed(response), msg=f'{user.username} {url}')
                else:
                    self.assertTrue(_denied(response), msg=f'{user.username} {url}')

    def test_director_cannot_manage_billing(self):
        director = self.users[ROLE_DIRECTOR]
        self.assertFalse(can_view_invoices(director))
        self.assertFalse(can_create_invoice(director))
        self.assertFalse(can_import_invoices(director))
        self.client.force_login(director)
        for url_name in ('invoice_list', 'create_invoice', 'invoice_import_upload'):
            self.assertTrue(_denied(self.client.get(reverse(url_name))), msg=url_name)

    def test_field_staff_cannot_create_orders_or_approve_wcr_pages(self):
        for role in (ROLE_ENGINEER, ROLE_TECHNICIAN):
            user = self.users[role]
            self.assertTrue(can_view_orders(user))
            self.assertFalse(can_create_orders(user))
            self.assertTrue(can_view_wcr(user))
            self.assertFalse(can_access(user, MODULE_WCR_APPROVE))
            self.client.force_login(user)
            self.assertFalse(_denied(self.client.get(reverse('order_list'))))
            self.assertTrue(_denied(self.client.get(reverse('create_order'))))
            self.assertFalse(_denied(self.client.get(reverse('wcr_list'))))

    def test_sidebar_matches_role_permissions(self):
        expected_nav = {
            ROLE_DIRECTOR: {'Dashboard', 'Orders', 'Scheduling', 'Clients', 'Quotations', 'WCR', 'BOQ', 'GPS Tracking'},
            ROLE_ACCOUNTS: {'Dashboard', 'Billing', 'Manual Invoice Import', 'BOQ', 'Clients'},
            ROLE_ENGINEER: {'Dashboard', 'Orders', 'Scheduling', 'WCR'},
            ROLE_TECHNICIAN: {'Dashboard', 'Orders', 'Scheduling', 'WCR'},
            ROLE_BACK_OFFICE: {'Dashboard'},
            ROLE_ACCOUNTS_EXECUTIVE: {'Dashboard'},
        }
        forbidden_nav = {
            ROLE_DIRECTOR: {'Billing', 'Manual Invoice Import'},
            ROLE_ENGINEER: {'Billing', 'Manual Invoice Import', 'Clients', 'Quotations'},
            ROLE_TECHNICIAN: {'Billing', 'Manual Invoice Import', 'Create Order'},
            ROLE_ACCOUNTS_EXECUTIVE: {'Billing', 'Manual Invoice Import', 'Orders'},
            ROLE_BACK_OFFICE: {'Billing', 'Manual Invoice Import', 'Orders'},
        }
        for role, labels in expected_nav.items():
            menu = build_navigation_menu(self.users[role], allowed_dashboard_url_name(self.users[role]))
            visible = {item['label'] for section in menu for item in section['items']}
            missing = labels - visible
            self.assertFalse(missing, msg=f'{role} missing nav {missing}; visible={visible}')
            blocked = forbidden_nav.get(role, set()) & visible
            self.assertFalse(blocked, msg=f'{role} should not see {blocked}')

    def test_accounts_nav_includes_invoice_import_and_others_do_not(self):
        for role, user in self.users.items():
            menu = build_navigation_menu(user, allowed_dashboard_url_name(user))
            visible = {item['label'] for section in menu for item in section['items']}
            if role == ROLE_ACCOUNTS:
                self.assertIn('Manual Invoice Import', visible)
                self.assertIn('Invoice Import History', visible)
            else:
                self.assertNotIn('Manual Invoice Import', visible)
                self.assertNotIn('Invoice Import History', visible)
        admin_menu = build_navigation_menu(self.superuser, allowed_dashboard_url_name(self.superuser))
        admin_visible = {item['label'] for section in admin_menu for item in section['items']}
        self.assertIn('Manual Invoice Import', admin_visible)

    def test_gps_dashboard_does_not_use_blocked_osm_tiles(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('gps_dashboard'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('tile.openstreetmap.org', content)
        self.assertIn('basemaps.cartocdn.com', content)
        self.assertIn('arcgisonline.com', content)

    def test_technician_with_empty_employee_profile_still_opens_orders(self):
        from accounts.enterprise_models import Branch, Department, Designation, Employee
        from accounts.enterprise_permissions import invalidate_enterprise_permission_cache

        tech = self.users[ROLE_TECHNICIAN]
        dept, _ = Department.objects.get_or_create(code='OPS', defaults={'name': 'Operations'})
        designation, _ = Designation.objects.get_or_create(code='TECHNICIAN', defaults={'name': 'Technician'})
        branch, _ = Branch.objects.get_or_create(code='HO', defaults={'name': 'Head Office'})
        Employee.objects.create(
            user=tech,
            employee_code='TECH1',
            department=dept,
            designation=designation,
            branch=branch,
        )
        invalidate_enterprise_permission_cache(tech.pk)
        self.client.force_login(tech)
        orders = self.client.get(reverse('order_list'))
        dashboard = self.client.get(reverse('field_team_dashboard'))
        billing = self.client.get(reverse('invoice_list'))
        self.assertFalse(_denied(orders), msg=orders.url if _denied(orders) else '')
        self.assertFalse(_denied(dashboard), msg=dashboard.url if _denied(dashboard) else '')
        self.assertTrue(_denied(billing))
