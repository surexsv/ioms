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
        ('LATE', 'Late Arrival'),
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    attendance_date = models.DateField(db_index=True)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    working_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Calculated from check-in and check-out',
    )
    location = models.CharField(max_length=500, blank=True, help_text='Check-in address')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_maps_link = models.URLField(max_length=500, blank=True)
    check_out_location = models.CharField(max_length=500, blank=True)
    check_out_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_maps_link = models.URLField(max_length=500, blank=True)
    device_info_in = models.CharField(max_length=500, blank=True)
    device_info_out = models.CharField(max_length=500, blank=True)
    ip_address_in = models.GenericIPAddressField(null=True, blank=True)
    ip_address_out = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT', db_index=True)
    notes = models.TextField(blank=True)
    check_in_remarks = models.TextField(blank=True)
    check_out_remarks = models.TextField(blank=True)
    is_corrected = models.BooleanField(default=False)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_corrections',
    )
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
        indexes = [
            models.Index(fields=['employee', '-attendance_date']),
            models.Index(fields=['attendance_date', 'status']),
        ]

    def __str__(self):
        return f"{self.employee} — {self.attendance_date} ({self.get_status_display()})"

    @property
    def has_check_in_photo(self):
        return self.photos.filter(photo_type=AttendancePhoto.TYPE_CHECK_IN).exists()

    @property
    def has_check_out_photo(self):
        return self.photos.filter(photo_type=AttendancePhoto.TYPE_CHECK_OUT).exists()

    def calculate_working_hours(self):
        if self.check_in_at and self.check_out_at:
            delta = self.check_out_at - self.check_in_at
            if delta.total_seconds() < 0:
                delta += timedelta(days=1)
            hours = Decimal(delta.total_seconds()) / Decimal(3600)
            return hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
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
        return None

    def save(self, *args, **kwargs):
        hours = self.calculate_working_hours()
        if hours is not None:
            self.working_hours = hours
        super().save(*args, **kwargs)


class AttendancePhoto(models.Model):
    TYPE_CHECK_IN = 'CHECK_IN'
    TYPE_CHECK_OUT = 'CHECK_OUT'
    TYPE_CHOICES = (
        (TYPE_CHECK_IN, 'Check-In Photo'),
        (TYPE_CHECK_OUT, 'Check-Out Photo'),
    )

    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_photos',
    )
    photo_type = models.CharField(max_length=12, choices=TYPE_CHOICES, db_index=True)
    image = models.ImageField(upload_to='attendance_photos/%Y/%m/')
    captured_at = models.DateTimeField(default=timezone.now)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        ordering = ['-captured_at']

    def __str__(self):
        return f'{self.attendance_id} — {self.get_photo_type_display()}'


class AttendanceAuditLog(models.Model):
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=40, db_index=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_audit_actions',
    )
    user_role = models.CharField(max_length=30, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=500, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} @ {self.created_at}'
