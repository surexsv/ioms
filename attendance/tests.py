from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from accounts.models import User
from .models import Attendance
from .services import today_stats, employee_month_stats


class AttendanceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='eng1', password='test', role='ENGINEER',
        )
        self.user.is_active_employee = True
        self.user.save()

    def test_working_hours_calculated(self):
        rec = Attendance.objects.create(
            employee=self.user,
            attendance_date=date.today(),
            status='PRESENT',
            check_in_time=time(9, 0),
            check_out_time=time(17, 30),
        )
        rec.refresh_from_db()
        self.assertEqual(rec.working_hours, Decimal('8.50'))
