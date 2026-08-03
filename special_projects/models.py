"""
Special Project (PEMS Phase 1) — long-duration execution workspace for selected Orders.

Phase 0 lock:
- One SpecialProject ↔ one Order (OneToOne)
- Daily logs capture labour, material, service, expense, media
- Completion closes via normal WCR → BOQ → Billing
- Cost summary is separate in this module
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class SpecialProject(models.Model):
    STATUS_PLANNING = 'PLANNING'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_ON_HOLD = 'ON_HOLD'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_PLANNING, 'Planning'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_ON_HOLD, 'On Hold'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CLOSED, 'Closed'),
    )

    CATEGORY_CHOICES = (
        ('OFC', 'OFC / Fibre'),
        ('NETWORK', 'Networking'),
        ('CCTV', 'CCTV / ELV'),
        ('ISP', 'ISP Installation'),
        ('INFRA', 'IT Infrastructure'),
        ('MAINTENANCE', 'Long Maintenance'),
        ('OTHER', 'Other'),
    )

    project_number = models.CharField(max_length=30, unique=True, blank=True)
    name = models.CharField(max_length=200)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='special_project',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='special_projects_managed',
    )
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNING)
    overall_progress_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='0–100',
    )
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='special_projects_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Special Project'
        verbose_name_plural = 'Special Projects'

    def __str__(self):
        return f'{self.project_number or "SP"} — {self.name}'

    @property
    def client(self):
        return self.order.client

    def total_expenses(self):
        total = DailyExpenseLine.objects.filter(
            daily_log__project=self,
        ).aggregate(s=Sum('amount'))['s']
        return total or Decimal('0.00')

    def budget_variance(self):
        return self.budget - self.total_expenses()

    def save(self, *args, **kwargs):
        if not self.project_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_SPECIAL_PROJECT
            self.project_number = generate_document_number(DOC_SPECIAL_PROJECT)
        if not self.name:
            self.name = self.order.display_site_name or self.order.client.name
        super().save(*args, **kwargs)


class ProjectDailyLog(models.Model):
    project = models.ForeignKey(
        SpecialProject,
        on_delete=models.CASCADE,
        related_name='daily_logs',
    )
    log_date = models.DateField(default=timezone.localdate, db_index=True)
    site_location = models.CharField(max_length=255, blank=True)
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='special_project_logs_as_mentor',
    )
    assigned_employees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='special_project_daily_assignments',
    )
    work_description = models.TextField()
    daily_progress_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
    )
    planned_work = models.TextField(blank=True)
    actual_work = models.TextField(blank=True)
    issues_risks = models.TextField(blank=True)
    next_day_plan = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='special_project_logs_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-log_date', '-id']
        unique_together = [['project', 'log_date']]
        verbose_name = 'Project Daily Log'

    def __str__(self):
        return f'{self.project.project_number} — {self.log_date}'

    def clean(self):
        if self.daily_progress_pct is not None and (
            self.daily_progress_pct < 0 or self.daily_progress_pct > 100
        ):
            raise ValidationError({'daily_progress_pct': 'Progress must be between 0 and 100.'})

    def day_expense_total(self):
        total = self.expenses.aggregate(s=Sum('amount'))['s']
        return total or Decimal('0.00')


class DailyLabourLine(models.Model):
    ATTENDANCE_CHOICES = (
        ('PRESENT', 'Present'),
        ('HALF_DAY', 'Half Day'),
        ('ABSENT', 'Absent'),
        ('LEAVE', 'Leave'),
    )

    daily_log = models.ForeignKey(
        ProjectDailyLog, on_delete=models.CASCADE, related_name='labour_lines',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='special_project_labour_lines',
    )
    attendance = models.CharField(max_length=15, choices=ATTENDANCE_CHOICES, default='PRESENT')
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    special_work = models.CharField(max_length=255, blank=True)
    emergency_callout = models.BooleanField(default=False)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.employee} — {self.hours_worked}h'


class DailyMaterialLine(models.Model):
    daily_log = models.ForeignKey(
        ProjectDailyLog, on_delete=models.CASCADE, related_name='material_lines',
    )
    material = models.CharField(max_length=200)
    unit = models.CharField(max_length=30, default='Nos')
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    issued_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    consumed_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    returned_qty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    linked_boq_item = models.CharField(max_length=120, blank=True, help_text='BOQ line reference (text for Phase 1)')
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        self.closing_balance = (
            self.opening_balance + self.issued_qty - self.consumed_qty - self.returned_qty
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.material


class DailyServiceLine(models.Model):
    SERVICE_CHOICES = (
        ('CABLE_LAYING', 'Cable Laying'),
        ('SPLICING', 'Splicing'),
        ('TERMINATION', 'Termination'),
        ('TESTING', 'Testing'),
        ('INSTALLATION', 'Installation'),
        ('SURVEY', 'Survey'),
        ('CONFIGURATION', 'Configuration'),
        ('OTHER', 'Other'),
    )

    daily_log = models.ForeignKey(
        ProjectDailyLog, on_delete=models.CASCADE, related_name='service_lines',
    )
    service_type = models.CharField(max_length=30, choices=SERVICE_CHOICES, default='OTHER')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    unit = models.CharField(max_length=30, default='Nos')
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.get_service_type_display()} x {self.quantity}'


class DailyExpenseLine(models.Model):
    EXPENSE_CHOICES = (
        ('FUEL', 'Fuel'),
        ('FOOD', 'Food'),
        ('ACCOMMODATION', 'Accommodation'),
        ('LOCAL_TRANSPORT', 'Local Transport'),
        ('PARKING', 'Parking'),
        ('TOLL', 'Toll'),
        ('COURIER', 'Courier'),
        ('EQUIPMENT_HIRE', 'Equipment Hire'),
        ('MISC', 'Miscellaneous'),
    )
    APPROVAL_PENDING = 'PENDING'
    APPROVAL_APPROVED = 'APPROVED'
    APPROVAL_REJECTED = 'REJECTED'
    APPROVAL_CHOICES = (
        (APPROVAL_PENDING, 'Pending'),
        (APPROVAL_APPROVED, 'Approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    )

    daily_log = models.ForeignKey(
        ProjectDailyLog, on_delete=models.CASCADE, related_name='expenses',
    )
    expense_type = models.CharField(max_length=30, choices=EXPENSE_CHOICES, default='MISC')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    approval_status = models.CharField(
        max_length=15, choices=APPROVAL_CHOICES, default=APPROVAL_PENDING,
    )
    bill_photo = models.FileField(upload_to='special_projects/expense_bills/', blank=True)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.get_expense_type_display()} — {self.amount}'


class DailyMedia(models.Model):
    MEDIA_BEFORE = 'BEFORE'
    MEDIA_DURING = 'DURING'
    MEDIA_AFTER = 'AFTER'
    MEDIA_DRAWING = 'DRAWING'
    MEDIA_DOCUMENT = 'DOCUMENT'
    MEDIA_CHOICES = (
        (MEDIA_BEFORE, 'Before photo'),
        (MEDIA_DURING, 'During work photo'),
        (MEDIA_AFTER, 'After photo'),
        (MEDIA_DRAWING, 'Drawing'),
        (MEDIA_DOCUMENT, 'Document'),
    )

    daily_log = models.ForeignKey(
        ProjectDailyLog, on_delete=models.CASCADE, related_name='media_files',
    )
    media_type = models.CharField(max_length=20, choices=MEDIA_CHOICES, default=MEDIA_DURING)
    file = models.FileField(upload_to='special_projects/media/')
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['media_type', 'id']
        verbose_name_plural = 'Daily media'

    def __str__(self):
        return f'{self.get_media_type_display()} — {self.caption or self.file.name}'
