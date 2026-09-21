from datetime import date, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from clients.models import Client
from orders.models import Order
from scheduling.models import WorkSchedule
from wcr.models import WorkCompletionReport

from .models import PMObservation, PMObservationOrder, PMObservationSnapshot
from .services import create_order_from_observation, derive_monitoring_status, link_existing_order


class PMTestMixin:
    def make_user(self, username, role, password='test-pass'):
        return User.objects.create_user(
            username=username,
            password=password,
            role=role,
            approval_status=User.APPROVAL_APPROVED,
            is_active_employee=True,
        )

    def make_client(self, name='ABC Telecom'):
        return Client.objects.create(
            name=name,
            company_type='TELECOM',
            address='Site Road',
            contact_person='Ravi',
            phone='9999999999',
        )

    def make_observation(self, user, client=None, **kwargs):
        data = {
            'client': client or self.make_client(),
            'site_location': 'Fiber hut A',
            'observation': 'Fiber closure requires preventive maintenance.',
            'recommended_work': 'Reseal closure and clean trays.',
            'maintenance_type': PMObservation.TYPE_PREVENTIVE,
            'priority': PMObservation.PRIORITY_HIGH,
            'created_by': user,
        }
        data.update(kwargs)
        return PMObservation.objects.create(**data)

    def make_normal_order(self, client, **kwargs):
        data = {
            'client': client,
            'site_address': 'Existing site',
            'order_type': 'INSTALLATION',
            'description': 'Normal installation order',
            'priority': 'Normal',
            'status': 'NEW',
        }
        data.update(kwargs)
        return Order.objects.create(**data)


class PreventiveMaintenanceRBACTests(PMTestMixin, TestCase):
    def setUp(self):
        self.client_obj = self.make_client()
        self.tech = self.make_user('tech1', 'Technician')
        self.eng = self.make_user('eng1', 'ENGINEER')
        self.tl = self.make_user('tl1', 'SUPERVISOR')
        self.manager = self.make_user('pm1', 'PROJECT_MANAGER')
        self.accounts = self.make_user('acc1', 'ACCOUNTS')
        self.office = self.make_user('office1', 'BACK_OFFICE')

    def test_technician_can_create_observation(self):
        self.client.login(username='tech1', password='test-pass')
        resp = self.client.post(reverse('pm_observation_create'), {
            'client': self.client_obj.pk,
            'site_location': 'POP-1',
            'observation': 'UPS battery needs replacement',
            'recommended_work': 'Replace battery bank',
            'maintenance_type': PMObservation.TYPE_CORRECTIVE,
            'priority': PMObservation.PRIORITY_CRITICAL,
            'current_condition': PMObservation.CONDITION_AT_RISK,
            'source': PMObservation.SOURCE_TECH,
            'snapshots-TOTAL_FORMS': '2',
            'snapshots-INITIAL_FORMS': '0',
            'snapshots-MIN_NUM_FORMS': '0',
            'snapshots-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(resp.status_code, 302)
        obs = PMObservation.objects.get()
        self.assertEqual(obs.created_by, self.tech)
        self.assertEqual(obs.admin_status, PMObservation.ADMIN_REPORTED)
        self.assertTrue(obs.pm_number)

    def test_engineer_can_create_observation(self):
        self.client.login(username='eng1', password='test-pass')
        resp = self.client.post(reverse('pm_observation_create'), {
            'client': self.client_obj.pk,
            'observation': 'Switch capacity is nearly exhausted',
            'maintenance_type': PMObservation.TYPE_FUTURE,
            'priority': PMObservation.PRIORITY_LOW,
            'source': PMObservation.SOURCE_ENGINEER,
            'snapshots-TOTAL_FORMS': '2',
            'snapshots-INITIAL_FORMS': '0',
            'snapshots-MIN_NUM_FORMS': '0',
            'snapshots-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(PMObservation.objects.count(), 1)

    def test_tl_can_review_and_approve(self):
        obs = self.make_observation(self.tech, client=self.client_obj)
        self.client.login(username='tl1', password='test-pass')
        review = self.client.post(reverse('pm_observation_detail', args=[obs.pk]), {'action': 'review'})
        self.assertEqual(review.status_code, 302)
        obs.refresh_from_db()
        self.assertEqual(obs.admin_status, PMObservation.ADMIN_UNDER_REVIEW)
        approve = self.client.post(reverse('pm_observation_detail', args=[obs.pk]), {'action': 'approve'})
        self.assertEqual(approve.status_code, 302)
        obs.refresh_from_db()
        self.assertEqual(obs.admin_status, PMObservation.ADMIN_APPROVED)
        self.assertEqual(obs.approved_by, self.tl)

    def test_manager_can_approve(self):
        obs = self.make_observation(self.eng, client=self.client_obj)
        self.client.login(username='pm1', password='test-pass')
        resp = self.client.post(reverse('pm_observation_detail', args=[obs.pk]), {'action': 'approve'})
        self.assertEqual(resp.status_code, 302)
        obs.refresh_from_db()
        self.assertEqual(obs.admin_status, PMObservation.ADMIN_APPROVED)

    def test_technician_cannot_approve_or_create_order(self):
        obs = self.make_observation(self.tech, client=self.client_obj)
        obs.admin_status = PMObservation.ADMIN_APPROVED
        obs.save(update_fields=['admin_status'])
        self.client.login(username='tech1', password='test-pass')
        approve = self.client.post(reverse('pm_observation_detail', args=[obs.pk]), {'action': 'approve'})
        self.assertEqual(approve.status_code, 302)
        self.assertIn('/access-denied', approve['Location'])
        create = self.client.post(
            reverse('pm_observation_detail', args=[obs.pk]),
            {'action': 'create_order'},
        )
        self.assertEqual(create.status_code, 302)
        self.assertIn('/access-denied', create['Location'])
        self.assertEqual(Order.objects.count(), 0)

    def test_enterprise_technician_sees_pm_in_sidebar(self):
        from accounts.enterprise_migration import seed_masters
        from accounts.enterprise_models import (
            Branch,
            Department,
            Designation,
            Employee,
            EmployeePermissionGrant,
            ModulePermission,
        )
        from accounts.enterprise_permissions import build_navigation_menu
        from django.apps import apps

        seed_masters(apps, None)
        grants = {}
        for codename, name in (
            ('orders', 'Orders'),
            ('scheduling', 'Scheduling'),
            ('wcr', 'WCR'),
            ('dashboard', 'Dashboard'),
        ):
            grants[codename] = ModulePermission.objects.get_or_create(
                codename=codename,
                defaults={'name': name, 'category': 'operations', 'is_active': True},
            )[0]
        dept = Department.objects.get(code='OPERATIONS')
        desig = Designation.objects.get(code='TECHNICIAN')
        branch = Branch.objects.filter(is_head_office=True).first() or Branch.objects.first()
        employee = Employee.objects.create(
            user=self.tech,
            employee_code='TECH-NAV-1',
            department=dept,
            designation=desig,
            branch=branch,
        )
        for perm in grants.values():
            EmployeePermissionGrant.objects.create(employee=employee, permission=perm, is_active=True)

        nav_keys = {
            item['nav_key']
            for section in build_navigation_menu(self.tech, 'field_team_dashboard')
            for item in section.get('items', [])
        }
        self.assertIn('preventive_maintenance', nav_keys)

        self.client.login(username='tech1', password='test-pass')
        field = self.client.get(reverse('field_team_dashboard'))
        self.assertEqual(field.status_code, 200)
        self.assertContains(field, 'Preventive Maintenance')
        self.assertContains(field, reverse('pm_dashboard'))
        orders = self.client.get(reverse('order_list'))
        self.assertEqual(orders.status_code, 200)
        self.assertContains(orders, 'Preventive Maintenance')
        self.assertContains(orders, reverse('pm_dashboard'))

    def test_enterprise_technician_without_dashboard_grant_still_sees_pm(self):
        from accounts.enterprise_migration import seed_masters
        from accounts.enterprise_models import (
            Branch,
            Department,
            Designation,
            Employee,
            EmployeePermissionGrant,
            ModulePermission,
        )
        from accounts.enterprise_permissions import build_navigation_menu
        from django.apps import apps

        seed_masters(apps, None)
        orders = ModulePermission.objects.get_or_create(
            codename='orders',
            defaults={'name': 'Orders', 'category': 'operations', 'is_active': True},
        )[0]
        wcr = ModulePermission.objects.get_or_create(
            codename='wcr',
            defaults={'name': 'WCR', 'category': 'operations', 'is_active': True},
        )[0]
        dept = Department.objects.get(code='OPERATIONS')
        desig = Designation.objects.get(code='TECHNICIAN')
        branch = Branch.objects.filter(is_head_office=True).first() or Branch.objects.first()
        employee = Employee.objects.create(
            user=self.tech,
            employee_code='TECH-NAV-2',
            department=dept,
            designation=desig,
            branch=branch,
        )
        EmployeePermissionGrant.objects.create(employee=employee, permission=orders, is_active=True)
        EmployeePermissionGrant.objects.create(employee=employee, permission=wcr, is_active=True)
        nav_keys = {
            item['nav_key']
            for section in build_navigation_menu(self.tech, 'field_team_dashboard')
            for item in section.get('items', [])
        }
        self.assertIn('preventive_maintenance', nav_keys)
        self.client.login(username='tech1', password='test-pass')
        resp = self.client.get(reverse('field_team_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Preventive Maintenance')

    def test_technician_order_list_html_renders_pm_after_orders(self):
        self.client.login(username='tech1', password='test-pass')
        resp = self.client.get(reverse('order_list'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-nav="preventive-maintenance"', html)
        self.assertIn('Preventive Maintenance', html)
        self.assertLess(html.find('My Orders'), html.find('Preventive Maintenance'))
        self.assertEqual(html.count('data-nav="preventive-maintenance"'), 1)

    def test_pm_nav_injected_when_catalog_omits_it(self):
        from accounts import enterprise_permissions as ep
        from accounts.enterprise_permissions import build_navigation_menu

        original = ep.NAV_MENU_CATALOG
        ep.NAV_MENU_CATALOG = [
            item for item in original if item[5] != 'preventive_maintenance'
        ]
        try:
            nav_keys = {
                item['nav_key']
                for section in build_navigation_menu(self.tech, 'field_team_dashboard')
                for item in section.get('items', [])
            }
            self.assertIn('preventive_maintenance', nav_keys)
        finally:
            ep.NAV_MENU_CATALOG = original

        self.client.login(username='tech1', password='test-pass')
        resp = self.client.get(reverse('order_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-nav="preventive-maintenance"')

    def test_field_technician_without_any_enterprise_grants_still_sees_pm(self):
        from accounts.enterprise_migration import seed_masters
        from accounts.enterprise_models import Branch, Department, Designation, Employee
        from accounts.enterprise_permissions import build_navigation_menu
        from django.apps import apps
        from preventive_maintenance.permissions import can_view_pm

        seed_masters(apps, None)
        dept = Department.objects.get(code='OPERATIONS')
        desig = Designation.objects.get(code='TECHNICIAN')
        branch = Branch.objects.filter(is_head_office=True).first() or Branch.objects.first()
        Employee.objects.create(
            user=self.tech,
            employee_code='TECH-NAV-3',
            department=dept,
            designation=desig,
            branch=branch,
        )
        self.assertTrue(can_view_pm(self.tech))
        nav_keys = {
            item['nav_key']
            for section in build_navigation_menu(self.tech, 'field_team_dashboard')
            for item in section.get('items', [])
        }
        self.assertIn('preventive_maintenance', nav_keys)

    def test_accounts_and_office_cannot_access_pm(self):
        self.client.login(username='acc1', password='test-pass')
        resp = self.client.get(reverse('pm_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/access-denied', resp['Location'])
        self.client.login(username='office1', password='test-pass')
        resp = self.client.get(reverse('pm_observation_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/access-denied', resp['Location'])


class PreventiveMaintenanceOrderIntegrationTests(PMTestMixin, TestCase):
    def setUp(self):
        self.client_obj = self.make_client()
        self.tech = self.make_user('tech2', 'Technician')
        self.tl = self.make_user('tl2', 'SUPERVISOR')
        self.eng = self.make_user('eng2', 'ENGINEER')

    def _approve(self, obs):
        obs.admin_status = PMObservation.ADMIN_APPROVED
        obs.save(update_fields=['admin_status'])
        return obs

    def test_create_order_uses_existing_order_model(self):
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        self.client.login(username='tl2', password='test-pass')
        resp = self.client.post(
            reverse('pm_observation_detail', args=[obs.pk]),
            {'action': 'create_order', 'work_item': 'Fiber closure reseal'},
        )
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get()
        self.assertTrue(order.order_no)
        self.assertEqual(order.order_type, 'PREVENTIVE_MAINTENANCE')
        self.assertEqual(order.source, 'INTERNAL')
        self.assertEqual(order.status, 'NEW')
        self.assertEqual(order.client, self.client_obj)
        self.assertIn(obs.pm_number, order.remarks)
        self.assertIn('PREVENTIVE_MAINTENANCE', order.remarks)
        self.assertTrue(resp['Location'].endswith(reverse('order_detail', args=[order.pk])))
        self.assertTrue(PMObservationOrder.objects.filter(observation=obs, order=order).exists())

    def test_created_order_appears_in_order_list(self):
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        link = create_order_from_observation(obs, self.tl, work_item='CCTV')
        self.client.login(username='tl2', password='test-pass')
        resp = self.client.get(reverse('order_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, link.order.order_no)

    def test_created_order_can_be_scheduled(self):
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        link = create_order_from_observation(obs, self.tl)
        order = link.order
        schedule = WorkSchedule.objects.create(
            order=order,
            scheduled_start_date=date.today(),
            scheduled_end_date=date.today() + timedelta(days=1),
            status=WorkSchedule.STATUS_ASSIGNED,
            created_by=self.tl,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'SCHEDULED')
        self.assertEqual(order.work_schedule, schedule)
        self.assertEqual(derive_monitoring_status(obs), 'SCHEDULED')

    def test_order_status_reflected_in_pm_monitoring(self):
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        link = create_order_from_observation(obs, self.tl)
        order = link.order
        self.assertEqual(derive_monitoring_status(obs), 'ORDER_CREATED')
        order.status = 'IN_PROGRESS'
        order.save(update_fields=['status'])
        self.assertEqual(derive_monitoring_status(obs), 'IN_EXECUTION')
        order.status = 'COMPLETED'
        order.save(update_fields=['status'])
        self.assertEqual(derive_monitoring_status(obs), 'WCR_PENDING')
        WorkCompletionReport.objects.create(
            order=order,
            work_description='Closure resealed',
            submitted_by=self.eng,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'WCR_SUBMITTED')
        self.assertEqual(derive_monitoring_status(obs), 'VERIFICATION_PENDING')
        wcr = order.workcompletionreport
        wcr.approved = True
        wcr.save()
        order.refresh_from_db()
        self.assertEqual(order.status, 'APPROVED')
        self.assertEqual(derive_monitoring_status(obs), 'COMPLETED')
        order.status = 'CLOSED'
        order.save(update_fields=['status'])
        self.assertEqual(derive_monitoring_status(obs), 'CLOSED')

    def test_multiple_orders_can_be_linked(self):
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        first = create_order_from_observation(obs, self.tl, work_item='CCTV')
        second = create_order_from_observation(obs, self.tl, work_item='UPS')
        third = self.make_normal_order(self.client_obj, description='Rack work')
        link_existing_order(obs, third, self.tl, work_item='Network rack')
        self.assertEqual(obs.order_links.count(), 3)
        self.assertNotEqual(first.order_id, second.order_id)
        self.assertEqual(third.order_type, 'INSTALLATION')

    def test_future_observation_does_not_auto_create_order(self):
        obs = self.make_observation(
            self.tech,
            client=self.client_obj,
            maintenance_type=PMObservation.TYPE_FUTURE,
            observation='Upgrade recommended within 6 months.',
        )
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(derive_monitoring_status(obs), 'FUTURE_PLANNED')

    def test_existing_normal_orders_unaffected(self):
        existing = self.make_normal_order(self.client_obj)
        existing_no = existing.order_no
        existing_status = existing.status
        obs = self._approve(self.make_observation(self.tech, client=self.client_obj))
        create_order_from_observation(obs, self.tl)
        existing.refresh_from_db()
        self.assertEqual(existing.order_no, existing_no)
        self.assertEqual(existing.status, existing_status)
        self.assertEqual(existing.order_type, 'INSTALLATION')
        self.assertEqual(Order.objects.exclude(pk=existing.pk).count(), 1)

    def test_gps_and_snapshot_are_stored(self):
        self.client.login(username='tech2', password='test-pass')
        photo = SimpleUploadedFile('site.jpg', b'\xff\xd8\xffdummyjpeg', content_type='image/jpeg')
        resp = self.client.post(reverse('pm_observation_create'), {
            'client': self.client_obj.pk,
            'observation': 'Cable condition is poor',
            'maintenance_type': PMObservation.TYPE_PREVENTIVE,
            'priority': PMObservation.PRIORITY_MEDIUM,
            'source': PMObservation.SOURCE_FIELD_VISIT,
            'latitude': '10.015240',
            'longitude': '76.341800',
            'gps_accuracy': '12.50',
            'snapshots-TOTAL_FORMS': '2',
            'snapshots-INITIAL_FORMS': '0',
            'snapshots-MIN_NUM_FORMS': '0',
            'snapshots-MAX_NUM_FORMS': '1000',
            'snapshots-0-kind': 'SNAPSHOT',
            'snapshots-0-file': photo,
            'snapshots-0-caption': 'Closure photo',
        })
        self.assertEqual(resp.status_code, 302)
        obs = PMObservation.objects.get()
        self.assertEqual(obs.latitude, Decimal('10.015240'))
        self.assertEqual(obs.longitude, Decimal('76.341800'))
        self.assertTrue(obs.has_gps)
        snap = PMObservationSnapshot.objects.get()
        self.assertEqual(snap.caption, 'Closure photo')
        self.assertEqual(snap.latitude, obs.latitude)
        self.assertEqual(snap.longitude, obs.longitude)

    def test_dashboard_and_list_load_for_tl(self):
        self.make_observation(self.tech, client=self.client_obj)
        self.client.login(username='tl2', password='test-pass')
        dash = self.client.get(reverse('pm_dashboard'))
        listing = self.client.get(reverse('pm_observation_list'))
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, 'Preventive Maintenance')
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'Fiber closure requires preventive maintenance.')

    def test_pm_panel_visible_on_existing_role_dashboards(self):
        self.make_observation(self.tech, client=self.client_obj)
        self.client.login(username='tech2', password='test-pass')
        field = self.client.get(reverse('field_team_dashboard'))
        self.assertEqual(field.status_code, 200)
        self.assertContains(field, 'Preventive Maintenance')
        self.assertContains(field, 'New Observation')
        self.client.login(username='tl2', password='test-pass')
        supervisor = self.client.get(reverse('supervisor_dashboard'))
        self.assertEqual(supervisor.status_code, 200)
        self.assertContains(supervisor, 'Preventive Maintenance')
        self.assertContains(supervisor, 'Open PM Module')
