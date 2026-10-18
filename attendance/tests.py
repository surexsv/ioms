import io
from datetime import date, time
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from .models import Attendance
from .services import photo_verification_report


def _jpeg():
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), 'red').save(buf, format='JPEG')
    return SimpleUploadedFile('face.jpg', buf.getvalue(), content_type='image/jpeg')


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


class WorkModeAttendanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='eng-office', password='test', role='ENGINEER',
        )

    def test_check_in_page_offers_field_and_office(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('attendance_check_in'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mobile — field')
        self.assertContains(response, 'PC — office')
        self.assertContains(response, 'name="work_mode"')
        self.assertNotContains(response, 'capture="user" required')

    def test_office_check_in_and_out_without_photo_or_gps(self):
        self.client.force_login(self.user)
        check_in = self.client.post(reverse('attendance_check_in'), {
            'work_mode': Attendance.WORK_OFFICE,
            'remarks': 'At the desk',
        })
        self.assertRedirects(check_in, reverse('my_attendance'))
        record = Attendance.objects.get(employee=self.user)
        self.assertEqual(record.check_in_work_mode, Attendance.WORK_OFFICE)
        self.assertIsNotNone(record.check_in_time)
        self.assertIsNone(record.latitude)
        self.assertFalse(record.photos.exists())

        check_out = self.client.post(reverse('attendance_check_out'), {
            'work_mode': Attendance.WORK_OFFICE,
        })
        self.assertRedirects(check_out, reverse('my_attendance'))
        record.refresh_from_db()
        self.assertEqual(record.check_out_work_mode, Attendance.WORK_OFFICE)
        self.assertIsNotNone(record.check_out_time)
        self.assertFalse(record.photos.exists())

        report = photo_verification_report(record.attendance_date)
        self.assertTrue(report['rows'][0]['verified'])

    def test_field_check_in_requires_photo_and_gps(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('attendance_check_in'), {
            'work_mode': Attendance.WORK_FIELD,
        })
        self.assertEqual(response.status_code, 200)
        record = Attendance.objects.get(employee=self.user)
        self.assertIsNone(record.check_in_time)
        self.assertContains(response, 'Photo is required for field check-in.')
        self.assertContains(response, 'GPS location is required for field check-in.')

    def test_field_check_in_saves_photo_and_gps(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('attendance_check_in'), {
            'work_mode': Attendance.WORK_FIELD,
            'latitude': '10.0150000',
            'longitude': '76.3410000',
            'photo': _jpeg(),
        })
        self.assertRedirects(response, reverse('my_attendance'))
        record = Attendance.objects.get(employee=self.user)
        self.assertEqual(record.check_in_work_mode, Attendance.WORK_FIELD)
        self.assertTrue(record.has_check_in_photo)
        self.assertEqual(record.latitude, Decimal('10.0150000'))
