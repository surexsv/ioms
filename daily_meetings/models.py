from django.conf import settings
from django.db import models
from django.utils import timezone


class DailyMeetingsSettings(models.Model):
    """Singleton — meeting start time and defaults."""

    meeting_start_time = models.TimeField(default='09:00')
    default_meeting_type = models.CharField(max_length=20, default='DAILY')
    late_grace_minutes = models.PositiveSmallIntegerField(
        default=0,
        help_text='Minutes after start time before marking late.',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dom_settings_updates',
    )

    class Meta:
        verbose_name = 'Daily meetings settings'
        verbose_name_plural = 'Daily meetings settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AgendaTemplateItem(models.Model):
    """Reusable standard agenda template (admin-editable)."""

    sort_order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False,
        help_text='System items are re-seeded if missing.',
    )

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'Agenda template item'

    def __str__(self):
        return f'{self.sort_order}. {self.title}'


class OpenItemRegister(models.Model):
    """Recurring open items that appear in meetings until closed."""

    STATUS_OPEN = 'OPEN'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    item_code = models.CharField(max_length=30, unique=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_open_items',
    )
    target_date = models.DateField(null=True, blank=True)
    is_recurring = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_open_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['status', 'title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.item_code:
            last = OpenItemRegister.objects.order_by('-pk').first()
            seq = (last.pk if last else 0) + 1
            self.item_code = f'OIR-{seq:04d}'
        super().save(*args, **kwargs)


class DailyMeeting(models.Model):
    TYPE_DAILY = 'DAILY'
    TYPE_WEEKLY = 'WEEKLY'
    TYPE_SPECIAL = 'SPECIAL'
    TYPE_CHOICES = (
        (TYPE_DAILY, 'Daily Morning Meeting'),
        (TYPE_WEEKLY, 'Weekly Review'),
        (TYPE_SPECIAL, 'Special Meeting'),
    )

    STATUS_DRAFT = 'DRAFT'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    meeting_number = models.CharField(max_length=30, unique=True, blank=True)
    meeting_date = models.DateField(db_index=True)
    meeting_time = models.TimeField()
    meeting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_DAILY)
    topic_of_day = models.CharField(max_length=300, blank=True)
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings_conducted',
    )
    department = models.CharField(max_length=100, blank=True, default='Operations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    remarks = models.TextField(blank=True)
    closing_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meetings_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-meeting_date', '-meeting_time']
        constraints = [
            models.UniqueConstraint(
                fields=['meeting_date', 'meeting_type', 'department'],
                name='unique_daily_meeting_per_day_type_dept',
            ),
        ]

    def __str__(self):
        return f'{self.meeting_number} — {self.meeting_date}'

    def save(self, *args, **kwargs):
        if not self.meeting_number:
            year = self.meeting_date.year if self.meeting_date else timezone.localdate().year
            count = DailyMeeting.objects.filter(meeting_date__year=year).count() + 1
            self.meeting_number = f'DOM-{year}-{count:04d}'
        super().save(*args, **kwargs)


class MeetingAgendaItem(models.Model):
    """Agenda line items for a specific meeting (from template or custom)."""

    meeting = models.ForeignKey(DailyMeeting, on_delete=models.CASCADE, related_name='agenda_items')
    sort_order = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.title


class MeetingAttendance(models.Model):
    STATUS_PRESENT = 'PRESENT'
    STATUS_LATE = 'LATE'
    STATUS_ABSENT = 'ABSENT'
    STATUS_CHOICES = (
        (STATUS_PRESENT, 'Present'),
        (STATUS_LATE, 'Late'),
        (STATUS_ABSENT, 'Absent'),
    )

    meeting = models.ForeignKey(DailyMeeting, on_delete=models.CASCADE, related_name='attendees')
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meeting_attendance',
    )
    role_snapshot = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ABSENT, db_index=True)
    join_time = models.TimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    is_manual_override = models.BooleanField(default=False)
    attendance_record_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Linked attendance.models.Attendance pk if auto-matched.',
    )

    class Meta:
        ordering = ['employee__username']
        constraints = [
            models.UniqueConstraint(
                fields=['meeting', 'employee'],
                name='unique_meeting_attendee',
            ),
        ]

    def __str__(self):
        return f'{self.employee} — {self.get_status_display()}'


class MeetingDiscussion(models.Model):
    meeting = models.ForeignKey(DailyMeeting, on_delete=models.CASCADE, related_name='discussions')
    agenda_item = models.ForeignKey(
        MeetingAgendaItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussions',
    )
    agenda_title = models.CharField(max_length=200)
    discussion_notes = models.TextField(blank=True)
    key_learnings = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    decisions_taken = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return self.agenda_title


class MeetingActionItem(models.Model):
    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_CRITICAL = 'CRITICAL'
    PRIORITY_CHOICES = (
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    )

    STATUS_OPEN = 'OPEN'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_OVERDUE = 'OVERDUE'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_OVERDUE, 'Overdue'),
    )

    action_number = models.CharField(max_length=30, unique=True, blank=True)
    meeting = models.ForeignKey(
        DailyMeeting,
        on_delete=models.CASCADE,
        related_name='action_items',
        null=True,
        blank=True,
    )
    open_item = models.ForeignKey(
        OpenItemRegister,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='action_items',
    )
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_meeting_actions',
    )
    target_date = models.DateField(null=True, blank=True, db_index=True)
    priority = models.CharField(max_length=12, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    remarks = models.TextField(blank=True)
    completion_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_meeting_actions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action_number}: {self.description[:50]}'

    def save(self, *args, **kwargs):
        if not self.action_number:
            year = timezone.localdate().year
            count = MeetingActionItem.objects.filter(created_at__year=year).count() + 1
            self.action_number = f'ACT-{year}-{count:04d}'
        if self.target_date and self.target_date < timezone.localdate():
            if self.status in (self.STATUS_OPEN, self.STATUS_IN_PROGRESS):
                self.status = self.STATUS_OVERDUE
        super().save(*args, **kwargs)


class ManagementMessage(models.Model):
    CAT_MOTIVATION = 'MOTIVATION'
    CAT_SAFETY = 'SAFETY'
    CAT_QUALITY = 'QUALITY'
    CAT_OPERATIONS = 'OPERATIONS'
    CAT_HR = 'HR'
    CAT_GENERAL = 'GENERAL'
    CATEGORY_CHOICES = (
        (CAT_MOTIVATION, 'Motivation'),
        (CAT_SAFETY, 'Safety'),
        (CAT_QUALITY, 'Quality'),
        (CAT_OPERATIONS, 'Operations'),
        (CAT_HR, 'HR'),
        (CAT_GENERAL, 'General'),
    )

    meeting = models.ForeignKey(
        DailyMeeting,
        on_delete=models.CASCADE,
        related_name='management_messages',
        null=True,
        blank=True,
    )
    message_date = models.DateField(default=timezone.localdate, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CAT_GENERAL)
    message = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='management_messages_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-message_date', '-created_at']

    def __str__(self):
        return f'{self.get_category_display()} — {self.message_date}'


class MeetingOpenItemSnapshot(models.Model):
    """Links recurring open items reviewed in a meeting."""

    meeting = models.ForeignKey(DailyMeeting, on_delete=models.CASCADE, related_name='open_item_reviews')
    open_item = models.ForeignKey(OpenItemRegister, on_delete=models.CASCADE, related_name='meeting_reviews')
    status_at_meeting = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['meeting', 'open_item'],
                name='unique_meeting_open_item',
            ),
        ]
