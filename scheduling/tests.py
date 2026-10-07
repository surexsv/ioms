from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.enterprise_models import Branch, Department, Designation, Employee
from accounts.models import User
from clients.models import Client
from orders.models import Order
from scheduling.forms import WorkScheduleForm
from scheduling.models import WorkSchedule


PASSWORD = 'testpass123'


class ScheduleCreateFormTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            password=PASSWORD,
            email='admin@example.com',
        )
        self.pm = User.objects.create_user(
            username='jayan',
            password=PASSWORD,
            role='DIRECTOR',
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
        )
        self.supervisor = User.objects.create_user(
            username='supervisor1',
            password=PASSWORD,
            role='OPERATIONS',
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
        )
        self.engineer = User.objects.create_user(
            username='engineer1',
            password=PASSWORD,
            role='ENGINEER',
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
        )
        self.tech = User.objects.create_user(
            username='Tech1',
            password=PASSWORD,
            role='Technician',
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
        )
        dept, _ = Department.objects.get_or_create(code='OPS', defaults={'name': 'Operations'})
        branch, _ = Branch.objects.get_or_create(code='HO', defaults={'name': 'Head Office'})
        pm_desig, _ = Designation.objects.get_or_create(code='PROJECT_MANAGER', defaults={'name': 'Project Manager'})
        tl_desig, _ = Designation.objects.get_or_create(code='TEAM_LEADER', defaults={'name': 'Team Leader'})
        Employee.objects.create(
            user=self.pm, employee_code='PM1', department=dept, designation=pm_desig, branch=branch,
        )
        Employee.objects.create(
            user=self.supervisor, employee_code='TL1', department=dept, designation=tl_desig, branch=branch,
        )
        self.client_obj = Client.objects.create(
            name='ASIANET SATELLITE COMMUNICATIONS LTD',
            company_type='TELECOM',
            address='Kochi',
            contact_person='A',
            phone='9999999999',
        )
        self.order = Order.objects.create(
            client=self.client_obj,
            site_address='Site',
            order_type='INSTALLATION',
            description='Install work',
            status='NEW',
            order_date=date.today() - timedelta(days=10),
            assigned_project_manager=self.pm,
            assigned_supervisor=self.supervisor,
            assigned_to=self.engineer,
        )

    def _post_data(self, **overrides):
        today = timezone.localdate()
        data = {
            'scheduled_start_date': today.isoformat(),
            'scheduled_end_date': today.isoformat(),
            'project_manager': str(self.pm.pk),
            'supervisor': str(self.supervisor.pk),
            'lead_engineer': str(self.engineer.pk),
            'technicians': [str(self.tech.pk)],
            'status': WorkSchedule.STATUS_PLANNED,
        }
        data.update(overrides)
        return data

    def test_form_accepts_designation_team_even_when_legacy_role_differs(self):
        form = WorkScheduleForm(self._post_data(), order=self.order)
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_create_schedule_http_succeeds(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('schedule_create', args=[self.order.order_id]),
            self._post_data(),
        )
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['form'].errors)
        self.assertTrue(WorkSchedule.objects.filter(order=self.order).exists())

    def test_create_page_does_not_default_end_date_before_start(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('schedule_create', args=[self.order.order_id]))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertGreaterEqual(
            form.initial['scheduled_end_date'],
            form.initial['scheduled_start_date'],
        )
