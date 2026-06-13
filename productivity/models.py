from decimal import Decimal

from django.conf import settings
from django.db import models

from productivity.constants import (
    ACTIVITY_CHOICES,
    COMPLETION_STATUS_CHOICES,
    DEPARTMENT_CHOICES,
    PARTICIPANT_ROLE_CHOICES,
)


class EmployeeActivityLog(models.Model):
    """Back-office and system activity log — auto-populated, KPI-ready."""

    STATUS_COMPLETED = 'COMPLETED'
    STATUS_PENDING = 'PENDING'
    STATUS_CHOICES = (
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_PENDING, 'Pending'),
    )

    activity_date = models.DateField(db_index=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productivity_activities',
    )
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, db_index=True)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_CHOICES, db_index=True)
    related_document = models.CharField(max_length=120, blank=True)
    related_model = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    # Future: incentive_weight, kpi_category, mobile_sync_id
    kpi_weight = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1.00'),
        help_text='Reserved for future KPI/incentive weighting',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['employee', 'activity_date']),
            models.Index(fields=['department', 'activity_type']),
        ]

    def __str__(self):
        return f'{self.get_activity_type_display()} — {self.employee}'


class WCRTeamParticipant(models.Model):
    """Per-person productivity credit on a WCR."""

    wcr = models.ForeignKey(
        'wcr.WorkCompletionReport',
        on_delete=models.CASCADE,
        related_name='team_participants',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wcr_participations',
    )
    participant_role = models.CharField(max_length=25, choices=PARTICIPANT_ROLE_CHOICES)
    attended = models.BooleanField(default=True)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    man_days = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    from_schedule = models.BooleanField(
        default=True,
        help_text='True if auto-loaded from schedule assignment',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['wcr', 'employee']]
        ordering = ['participant_role', 'employee_id']

    def __str__(self):
        return f'{self.employee} ({self.get_participant_role_display()})'


class EmployeeProductivitySnapshot(models.Model):
    """Aggregated productivity per employee per period — incentive/KPI ready."""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='productivity_snapshots',
    )
    period_year = models.PositiveSmallIntegerField(db_index=True)
    period_month = models.PositiveSmallIntegerField(db_index=True)
    jobs_assigned = models.PositiveIntegerField(default=0)
    jobs_attended = models.PositiveIntegerField(default=0)
    wcr_submitted = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    man_days = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    completed_jobs = models.PositiveIntegerField(default=0)
    pending_jobs = models.PositiveIntegerField(default=0)
    activities_count = models.PositiveIntegerField(default=0)
    attendance_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    completion_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    # Future incentive fields
    incentive_score = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    ranking_position = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['employee', 'period_year', 'period_month']]
        ordering = ['-period_year', '-period_month']

    def __str__(self):
        return f'{self.employee} {self.period_year}-{self.period_month:02d}'


class GPSLocationRecord(models.Model):
    """Permanent GPS capture for field verification — mobile-sync ready."""

    latitude = models.DecimalField(max_digits=10, decimal_places=6)
    longitude = models.DecimalField(max_digits=10, decimal_places=6)
    address = models.TextField(blank=True)
    captured_at = models.DateTimeField(db_index=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='gps_captures',
    )
    device_info = models.CharField(max_length=255, blank=True)
    action_type = models.CharField(max_length=30, db_index=True)
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_records',
    )
    schedule = models.ForeignKey(
        'scheduling.WorkSchedule', on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_records',
    )
    wcr = models.ForeignKey(
        'wcr.WorkCompletionReport', on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_records',
    )
    enquiry = models.ForeignKey(
        'enquiries.Enquiry', on_delete=models.SET_NULL, null=True, blank=True, related_name='gps_records',
    )
    mobile_sync_id = models.CharField(max_length=64, blank=True, help_text='Future Android app sync ID')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['employee', 'captured_at']),
            models.Index(fields=['action_type', 'captured_at']),
        ]

    def __str__(self):
        return f'{self.action_type} @ {self.latitude},{self.longitude}'

    @property
    def action_label(self):
        from productivity.field_constants import FIELD_ACTION_CHOICES
        return dict(FIELD_ACTION_CHOICES).get(self.action_type, self.action_type)


class FieldActivityLog(models.Model):
    """Field operations activity with GPS — distinct from back-office EmployeeActivityLog."""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='field_activities',
    )
    role = models.CharField(max_length=25, blank=True)
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='field_activities',
    )
    schedule = models.ForeignKey(
        'scheduling.WorkSchedule', on_delete=models.SET_NULL, null=True, blank=True, related_name='field_activities',
    )
    wcr = models.ForeignKey(
        'wcr.WorkCompletionReport', on_delete=models.SET_NULL, null=True, blank=True, related_name='field_activities',
    )
    enquiry = models.ForeignKey(
        'enquiries.Enquiry', on_delete=models.SET_NULL, null=True, blank=True, related_name='field_activities',
    )
    action_type = models.CharField(max_length=30, db_index=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    address = models.TextField(blank=True)
    activity_date = models.DateField(db_index=True)
    activity_time = models.TimeField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    gps_record = models.ForeignKey(
        GPSLocationRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities',
    )
    site_photo = models.ImageField(upload_to='field/site_photos/', blank=True)
    work_photo = models.ImageField(upload_to='field/work_photos/', blank=True)
    kpi_weight = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'))
    mobile_sync_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activity_date', '-activity_time', '-created_at']
        indexes = [
            models.Index(fields=['employee', 'activity_date']),
            models.Index(fields=['action_type', 'activity_date']),
        ]

    def __str__(self):
        return f'{self.action_type} — {self.employee}'

    @property
    def action_label(self):
        from productivity.field_constants import FIELD_ACTION_CHOICES
        return dict(FIELD_ACTION_CHOICES).get(self.action_type, self.action_type)


class ScheduleSiteAttendance(models.Model):
    """Per-schedule site check-in / check-out with GPS proof."""

    schedule = models.ForeignKey(
        'scheduling.WorkSchedule',
        on_delete=models.CASCADE,
        related_name='site_attendance',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='schedule_site_attendance',
    )
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_in_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    check_in_address = models.TextField(blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    check_out_latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    check_out_address = models.TextField(blank=True)
    site_photo = models.ImageField(upload_to='field/checkin_photos/', blank=True)
    work_photo = models.ImageField(upload_to='field/checkout_photos/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['schedule', 'employee']]
        ordering = ['-check_in_at']

    def __str__(self):
        return f'{self.employee} @ {self.schedule.schedule_number}'

    @property
    def is_checked_in(self):
        return self.check_in_at and not self.check_out_at


class EmployeeProductivityDaily(models.Model):
    """Daily productivity aggregates — KPI/incentive ready."""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_productivity',
    )
    period_date = models.DateField(db_index=True)
    jobs_assigned = models.PositiveIntegerField(default=0)
    jobs_attended = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    man_days = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    completed_jobs = models.PositiveIntegerField(default=0)
    site_check_ins = models.PositiveIntegerField(default=0)
    completion_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    incentive_score = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['employee', 'period_date']]
        ordering = ['-period_date']

    def __str__(self):
        return f'{self.employee} {self.period_date}'
