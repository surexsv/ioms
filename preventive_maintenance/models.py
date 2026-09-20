from django.conf import settings
from django.db import models
from django.utils import timezone


class PMObservation(models.Model):
    """Field observation / recommendation. Operational work stays on Order."""

    TYPE_CORRECTIVE = 'CORRECTIVE'
    TYPE_PREVENTIVE = 'PREVENTIVE'
    TYPE_FUTURE = 'FUTURE'
    TYPE_IMPROVEMENT = 'IMPROVEMENT'
    TYPE_SAFETY = 'SAFETY'
    MAINTENANCE_TYPE_CHOICES = (
        (TYPE_CORRECTIVE, 'Corrective'),
        (TYPE_PREVENTIVE, 'Preventive'),
        (TYPE_FUTURE, 'Future / Planned'),
        (TYPE_IMPROVEMENT, 'Improvement / Upgrade'),
        (TYPE_SAFETY, 'Safety / Compliance'),
    )

    PRIORITY_CRITICAL = 'CRITICAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_LOW = 'LOW'
    PRIORITY_INFO = 'INFORMATIONAL'
    PRIORITY_CHOICES = (
        (PRIORITY_CRITICAL, 'Critical'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_INFO, 'Informational'),
    )

    CONDITION_NORMAL = 'WORKING_NORMAL'
    CONDITION_ISSUE = 'WORKING_ISSUE'
    CONDITION_DEGRADED = 'DEGRADED'
    CONDITION_AT_RISK = 'AT_RISK'
    CONDITION_FAILED = 'FAILED'
    CONDITION_NOT_IN_USE = 'NOT_IN_USE'
    CONDITION_OBSOLETE = 'OBSOLETE'
    CONDITION_UNKNOWN = 'UNKNOWN'
    CONDITION_CHOICES = (
        (CONDITION_NORMAL, 'Working normally'),
        (CONDITION_ISSUE, 'Working with issue'),
        (CONDITION_DEGRADED, 'Degraded'),
        (CONDITION_AT_RISK, 'At risk of failure'),
        (CONDITION_FAILED, 'Failed'),
        (CONDITION_NOT_IN_USE, 'Not in use'),
        (CONDITION_OBSOLETE, 'Obsolete'),
        (CONDITION_UNKNOWN, 'Unknown'),
    )

    IMPACT_NONE = 'NO_IMMEDIATE'
    IMPACT_MINOR = 'MINOR'
    IMPACT_PERFORMANCE = 'PERFORMANCE'
    IMPACT_INTERRUPTION = 'INTERRUPTION_RISK'
    IMPACT_MAJOR = 'MAJOR_INTERRUPTION'
    IMPACT_SAFETY = 'SAFETY_RISK'
    IMPACT_ESCALATION = 'CUSTOMER_ESCALATION'
    IMPACT_CHOICES = (
        (IMPACT_NONE, 'No immediate impact'),
        (IMPACT_MINOR, 'Minor service impact'),
        (IMPACT_PERFORMANCE, 'Performance degradation'),
        (IMPACT_INTERRUPTION, 'Service interruption risk'),
        (IMPACT_MAJOR, 'Major service interruption'),
        (IMPACT_SAFETY, 'Safety risk'),
        (IMPACT_ESCALATION, 'Customer escalation risk'),
    )

    SOURCE_FIELD_VISIT = 'FIELD_VISIT'
    SOURCE_PM_VISIT = 'PM_VISIT'
    SOURCE_BREAKDOWN = 'BREAKDOWN_VISIT'
    SOURCE_COMPLAINT = 'CUSTOMER_COMPLAINT'
    SOURCE_TECH = 'TECHNICIAN_OBSERVATION'
    SOURCE_ENGINEER = 'ENGINEER_OBSERVATION'
    SOURCE_TL = 'TL_INSPECTION'
    SOURCE_SURVEY = 'PROJECT_SURVEY'
    SOURCE_AMC = 'AMC_VISIT'
    SOURCE_MGMT = 'MANAGEMENT_INSPECTION'
    SOURCE_OTHER = 'OTHER'
    SOURCE_CHOICES = (
        (SOURCE_FIELD_VISIT, 'Field Visit'),
        (SOURCE_PM_VISIT, 'Preventive Maintenance Visit'),
        (SOURCE_BREAKDOWN, 'Breakdown Visit'),
        (SOURCE_COMPLAINT, 'Customer Complaint'),
        (SOURCE_TECH, 'Technician Observation'),
        (SOURCE_ENGINEER, 'Engineer Observation'),
        (SOURCE_TL, 'TL Inspection'),
        (SOURCE_SURVEY, 'Project Survey'),
        (SOURCE_AMC, 'AMC Visit'),
        (SOURCE_MGMT, 'Management Inspection'),
        (SOURCE_OTHER, 'Other'),
    )

    ADMIN_REPORTED = 'REPORTED'
    ADMIN_UNDER_REVIEW = 'UNDER_REVIEW'
    ADMIN_APPROVED = 'APPROVED'
    ADMIN_CLOSED = 'CLOSED'
    ADMIN_STATUS_CHOICES = (
        (ADMIN_REPORTED, 'Reported'),
        (ADMIN_UNDER_REVIEW, 'Under Review'),
        (ADMIN_APPROVED, 'Approved'),
        (ADMIN_CLOSED, 'Closed'),
    )

    pm_number = models.CharField(max_length=30, unique=True, blank=True)
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='pm_observations',
    )
    site_location = models.CharField(max_length=255, blank=True, verbose_name='Site / Location')
    system_service = models.CharField(max_length=120, blank=True, verbose_name='System / Service')
    equipment_asset = models.CharField(max_length=200, blank=True, verbose_name='Equipment / Asset')
    related_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_pm_observations',
        help_text='Existing order/project visit this observation was captured on, if any.',
    )
    related_project = models.ForeignKey(
        'special_projects.SpecialProject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_observations',
    )
    observation = models.TextField()
    recommended_work = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    maintenance_type = models.CharField(
        max_length=20,
        choices=MAINTENANCE_TYPE_CHOICES,
        default=TYPE_PREVENTIVE,
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )
    current_condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default=CONDITION_UNKNOWN,
        blank=True,
    )
    potential_impact = models.CharField(
        max_length=30,
        choices=IMPACT_CHOICES,
        blank=True,
    )
    suggested_due_date = models.DateField(null=True, blank=True)
    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default=SOURCE_FIELD_VISIT,
    )
    admin_status = models.CharField(
        max_length=20,
        choices=ADMIN_STATUS_CHOICES,
        default=ADMIN_REPORTED,
        db_index=True,
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    gps_accuracy = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    gps_address = models.CharField(max_length=500, blank=True)
    gps_captured_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_observations_created',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_observations_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_observations_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_observations_closed',
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_status', 'priority']),
            models.Index(fields=['suggested_due_date']),
        ]

    def __str__(self):
        return self.pm_number or f'PM #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.pm_number:
            from document_generator.constants import DOC_PM
            from document_generator.services import generate_document_number
            self.pm_number = generate_document_number(DOC_PM)
        super().save(*args, **kwargs)

    @property
    def has_gps(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def is_overdue(self):
        if self.admin_status == self.ADMIN_CLOSED:
            return False
        if not self.suggested_due_date:
            return False
        monitoring = self.monitoring_status
        if monitoring in ('COMPLETED', 'CLOSED'):
            return False
        return self.suggested_due_date < timezone.localdate()

    @property
    def linked_orders(self):
        return [link.order for link in self.order_links.select_related(
            'order', 'order__client', 'order__assigned_to',
            'order__work_schedule', 'order__workcompletionreport',
        )]

    @property
    def primary_link(self):
        return self.order_links.select_related(
            'order', 'order__assigned_to',
            'order__work_schedule', 'order__workcompletionreport',
        ).first()

    @property
    def primary_order_row(self):
        link = self.primary_link
        if not link:
            return None
        from preventive_maintenance.services import linked_order_display
        return linked_order_display(link)

    @property
    def monitoring_status(self):
        from preventive_maintenance.services import derive_monitoring_status
        return derive_monitoring_status(self)

    def monitoring_status_label(self):
        from preventive_maintenance.services import MONITORING_LABELS
        return MONITORING_LABELS.get(self.monitoring_status, self.monitoring_status)


class PMObservationOrder(models.Model):
    """One observation may generate one or more existing IOMS Orders."""

    observation = models.ForeignKey(
        PMObservation,
        on_delete=models.CASCADE,
        related_name='order_links',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='pm_order_links',
    )
    work_item = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_orders_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['observation', 'order']]
        ordering = ['created_at']

    def __str__(self):
        return f'{self.observation.pm_number} → {self.order.order_no}'


class PMObservationSnapshot(models.Model):
    """Site photo / document captured with the observation (reuses MEDIA_ROOT)."""

    KIND_SNAPSHOT = 'SNAPSHOT'
    KIND_DOCUMENT = 'DOCUMENT'
    KIND_CHOICES = (
        (KIND_SNAPSHOT, 'Snapshot'),
        (KIND_DOCUMENT, 'Document'),
    )

    observation = models.ForeignKey(
        PMObservation,
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_SNAPSHOT)
    file = models.FileField(upload_to='preventive_maintenance/%Y/%m/')
    caption = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_snapshots_uploaded',
    )

    class Meta:
        ordering = ['captured_at']

    def __str__(self):
        return self.caption or self.file.name


class PMObservationHistory(models.Model):
    ACTION_CREATED = 'CREATED'
    ACTION_REVIEWED = 'REVIEWED'
    ACTION_APPROVED = 'APPROVED'
    ACTION_ORDER_CREATED = 'ORDER_CREATED'
    ACTION_ORDER_LINKED = 'ORDER_LINKED'
    ACTION_PRIORITY_CHANGED = 'PRIORITY_CHANGED'
    ACTION_TYPE_CHANGED = 'TYPE_CHANGED'
    ACTION_CLOSED = 'CLOSED'
    ACTION_GPS_CAPTURED = 'GPS_CAPTURED'
    ACTION_SNAPSHOT = 'SNAPSHOT'
    ACTION_CHOICES = (
        (ACTION_CREATED, 'Created'),
        (ACTION_REVIEWED, 'Reviewed'),
        (ACTION_APPROVED, 'Approved'),
        (ACTION_ORDER_CREATED, 'Order Created'),
        (ACTION_ORDER_LINKED, 'Order Linked'),
        (ACTION_PRIORITY_CHANGED, 'Priority Changed'),
        (ACTION_TYPE_CHANGED, 'Classification Changed'),
        (ACTION_CLOSED, 'Closed'),
        (ACTION_GPS_CAPTURED, 'GPS Captured'),
        (ACTION_SNAPSHOT, 'Snapshot Added'),
    )

    observation = models.ForeignKey(
        PMObservation,
        on_delete=models.CASCADE,
        related_name='history',
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pm_history_actions',
    )
    previous_value = models.CharField(max_length=80, blank=True)
    new_value = models.CharField(max_length=80, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.observation} {self.action}'
