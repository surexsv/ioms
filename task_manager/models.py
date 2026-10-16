from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class TeamTask(models.Model):
    """A team to-do that can be scheduled, forwarded, held, reminded, and closed."""

    STATUS_OPEN = 'OPEN'
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_ON_HOLD = 'ON_HOLD'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_ON_HOLD, 'On hold'),
        (STATUS_CLOSED, 'Closed'),
    )
    WORKABLE_STATUSES = (
        STATUS_OPEN,
        STATUS_SCHEDULED,
        STATUS_IN_PROGRESS,
    )

    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'
    PRIORITY_CHOICES = (
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    )

    task_number = models.CharField(max_length=30, unique=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        db_index=True,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_team_tasks',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_team_tasks',
    )
    scheduled_on = models.DateField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    remind_after_days = models.PositiveSmallIntegerField(
        default=3,
        help_text='Remind the team if the task is still open after this many days.',
    )
    next_reminder_on = models.DateField(null=True, blank=True, db_index=True)
    latest_remarks = models.TextField(blank=True)
    hold_remarks = models.TextField(blank=True)
    close_remarks = models.TextField(blank=True)
    held_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    related_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_tasks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f'{self.task_number} — {self.title}'

    def save(self, *args, **kwargs):
        if not self.task_number:
            self.task_number = allocate_task_number()
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.status == self.STATUS_CLOSED or not self.due_on:
            return False
        return self.due_on < timezone.localdate()

    @property
    def is_long_pending(self):
        if self.status not in self.WORKABLE_STATUSES:
            return False
        opened = timezone.localtime(self.created_at).date()
        return (timezone.localdate() - opened).days >= (self.remind_after_days or 1)

    @property
    def days_open(self):
        opened = timezone.localtime(self.created_at).date()
        return (timezone.localdate() - opened).days


class TaskHistory(models.Model):
    ACTION_CREATED = 'CREATED'
    ACTION_SCHEDULED = 'SCHEDULED'
    ACTION_STARTED = 'STARTED'
    ACTION_REMAPPED = 'REMAPPED'
    ACTION_HELD = 'HELD'
    ACTION_RESUMED = 'RESUMED'
    ACTION_REMINDED = 'REMINDED'
    ACTION_CLOSED = 'CLOSED'
    ACTION_NOTE = 'NOTE'
    ACTION_CHOICES = (
        (ACTION_CREATED, 'Created'),
        (ACTION_SCHEDULED, 'Scheduled'),
        (ACTION_STARTED, 'Started'),
        (ACTION_REMAPPED, 'Remapped'),
        (ACTION_HELD, 'Put on hold'),
        (ACTION_RESUMED, 'Resumed'),
        (ACTION_REMINDED, 'Reminder'),
        (ACTION_CLOSED, 'Closed'),
        (ACTION_NOTE, 'Update'),
    )

    task = models.ForeignKey(TeamTask, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_task_history',
    )
    remarks = models.TextField(blank=True)
    from_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_task_history_from',
    )
    to_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_task_history_to',
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'task history'

    def __str__(self):
        return f'{self.task.task_number} {self.get_action_display()}'


def allocate_task_number():
    year = timezone.localdate().year
    prefix = f'TM-{year}-'
    last = (
        TeamTask.objects.filter(task_number__startswith=prefix)
        .order_by('-task_number')
        .values_list('task_number', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.rsplit('-', 1)[-1]) + 1
        except (TypeError, ValueError):
            seq = TeamTask.objects.filter(task_number__startswith=prefix).count() + 1
    return f'{prefix}{seq:04d}'


def reminder_date(base_date, remind_after_days):
    days = remind_after_days or 1
    return base_date + timedelta(days=days)
