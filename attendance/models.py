from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class Attendance(models.Model):

    STATUS_CHOICES = (
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('HALF_DAY', 'Half Day'),
        ('LEAVE', 'Leave'),
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    attendance_date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    working_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Calculated from check-in and check-out',
    )
    location = models.CharField(max_length=500, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Attendance records'
        ordering = ['-attendance_date', 'employee']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'attendance_date'],
                name='unique_employee_attendance_date',
            ),
        ]

    def __str__(self):
        return f"{self.employee} — {self.attendance_date} ({self.get_status_display()})"

    def calculate_working_hours(self):
        if self.check_in_time and self.check_out_time:
            today = self.attendance_date or timezone.localdate()
            start = datetime.combine(today, self.check_in_time)
            end = datetime.combine(today, self.check_out_time)
            if end < start:
                end += timedelta(days=1)
            delta = end - start
            hours = Decimal(delta.total_seconds()) / Decimal(3600)
            return hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if self.status == 'HALF_DAY':
            return Decimal('4.00')
        if self.status == 'PRESENT' and self.check_in_time and not self.check_out_time:
            return None
        return None

    def save(self, *args, **kwargs):
        hours = self.calculate_working_hours()
        if hours is not None:
            self.working_hours = hours
        super().save(*args, **kwargs)
