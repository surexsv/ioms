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
