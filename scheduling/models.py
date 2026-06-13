from django.conf import settings
from django.db import models
from django.utils import timezone


class WorkSchedule(models.Model):
    STATUS_PLANNED = 'PLANNED'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = (
        (STATUS_PLANNED, 'Planned'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    schedule_number = models.CharField(max_length=30, unique=True, blank=True)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='work_schedule',
    )
    scheduled_start_date = models.DateField()
    scheduled_end_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True, verbose_name='Scheduled Time')
    expected_duration_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Expected Duration (Hours)',
    )
    expected_man_days = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Expected Man-Days (Team Total)',
    )
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schedules_as_pm',
        limit_choices_to={'role': 'PROJECT_MANAGER'},
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schedules_as_supervisor',
        limit_choices_to={'role__in': ['SUPERVISOR', 'Supervisor']},
    )
    lead_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='schedules_as_lead_engineer',
        limit_choices_to={'role': 'ENGINEER'},
    )
    supporting_engineers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='schedules_as_supporting_engineer',
        blank=True,
        limit_choices_to={'role': 'ENGINEER'},
    )
    technicians = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='schedules_as_technician',
        blank=True,
        limit_choices_to={'role': 'Technician'},
    )
    assigned_engineers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='work_schedules',
        blank=True,
    )
    team_leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_schedules',
    )
    vehicle_assigned = models.CharField(max_length=120, blank=True)
    resource_requirements = models.TextField(blank=True)
    work_instructions = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_start_date', '-id']

    def __str__(self):
        return self.schedule_number or f'Schedule for Order #{self.order_id}'

    def save(self, *args, **kwargs):
        if not self.schedule_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_SCHEDULE
            self.schedule_number = generate_document_number(DOC_SCHEDULE)
        super().save(*args, **kwargs)
        from .services import sync_order_from_schedule
        sync_order_from_schedule(self)

    @property
    def primary_engineer(self):
        return self.assigned_engineers.first()

    def engineer_names(self):
        names = [
            u.get_full_name() or u.username
            for u in self.assigned_engineers.all()
        ]
        return ', '.join(names) if names else '—'

    def team_member_names(self):
        parts = []
        if self.project_manager:
            parts.append(f'PM: {self.project_manager.get_full_name() or self.project_manager.username}')
        if self.supervisor:
            parts.append(f'Supervisor: {self.supervisor.get_full_name() or self.supervisor.username}')
        if self.lead_engineer:
            parts.append(f'Lead: {self.lead_engineer.get_full_name() or self.lead_engineer.username}')
        for u in self.supporting_engineers.all():
            parts.append(u.get_full_name() or u.username)
        for u in self.technicians.all():
            parts.append(u.get_full_name() or u.username)
        if not parts:
            return self.engineer_names()
        return ', '.join(parts)
