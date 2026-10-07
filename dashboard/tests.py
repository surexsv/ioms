from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from attendance.permissions import default_attendance_required_for_role
from dashboard.services import merge_pm_widget


class DirectorDashboardSmokeTests(TestCase):
    def setUp(self):
        self.director = User.objects.create_user(
            username='director',
            password='testpass123',
            role='DIRECTOR',
            is_active_employee=True,
            approval_status=User.APPROVAL_APPROVED,
            attendance_required=default_attendance_required_for_role('DIRECTOR'),
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='testpass123',
            email='admin@example.com',
        )

    def test_director_dashboard_renders(self):
        self.client.force_login(self.director)
        response = self.client.get(reverse('director_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Director Dashboard')
        self.assertNotContains(response, 'Something Went Wrong')

    def test_superuser_dashboard_renders_with_sidebar(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('director_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Director Dashboard')
        self.assertContains(response, 'Preventive Maintenance')
        self.assertNotContains(response, 'Something Went Wrong')

    def test_pm_widget_failure_does_not_crash_dashboard(self):
        with patch(
            'preventive_maintenance.services.observations_for_user',
            side_effect=RuntimeError('pm query failed'),
        ):
            context = merge_pm_widget({}, self.director)
            self.assertEqual(context['pm_summary']['my_observations'], 0)
            self.client.force_login(self.director)
            response = self.client.get(reverse('director_dashboard'))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'Something Went Wrong')
