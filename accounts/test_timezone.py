from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.test import TestCase
from django.utils import timezone


class IndiaStandardTimeTests(TestCase):
    def test_application_clock_is_indian_standard_time(self):
        self.assertEqual(settings.TIME_ZONE, 'Asia/Kolkata')
        self.assertTrue(settings.USE_TZ)

        utc = datetime(2026, 11, 1, 15, 30, tzinfo=datetime_timezone.utc)
        local = timezone.localtime(utc)

        self.assertEqual(local.hour, 21)
        self.assertEqual(local.minute, 0)
        self.assertEqual(local.utcoffset(), timedelta(hours=5, minutes=30))
