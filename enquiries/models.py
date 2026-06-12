from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from clients.models import Client


class Enquiry(models.Model):
    """Pre-sales enquiry — CRM-ready foundation for leads, follow-ups, and opportunities."""

    STATUS_NEW = 'NEW'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_SURVEY_SCHEDULED = 'SURVEY_SCHEDULED'
    STATUS_SURVEY_COMPLETED = 'SURVEY_COMPLETED'
    STATUS_FEASIBILITY_IN_PROGRESS = 'FEASIBILITY_IN_PROGRESS'
    STATUS_QUOTATION_PREPARATION = 'QUOTATION_PREPARATION'
    STATUS_QUOTATION_SUBMITTED = 'QUOTATION_SUBMITTED'
    STATUS_FOLLOW_UP = 'FOLLOW_UP'
    STATUS_WON = 'WON'
    STATUS_LOST = 'LOST'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CONVERTED = 'CONVERTED_TO_ORDER'

    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_SURVEY_SCHEDULED, 'Survey Scheduled'),
        (STATUS_SURVEY_COMPLETED, 'Survey Completed'),
        (STATUS_FEASIBILITY_IN_PROGRESS, 'Feasibility In Progress'),
        (STATUS_QUOTATION_PREPARATION, 'Quotation Preparation'),
        (STATUS_QUOTATION_SUBMITTED, 'Quotation Submitted'),
        (STATUS_FOLLOW_UP, 'Follow Up'),
        (STATUS_WON, 'Won'),
        (STATUS_LOST, 'Lost'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CONVERTED, 'Converted To Order'),
    )

    PIPELINE_STAGES = (
        STATUS_NEW, STATUS_ASSIGNED, STATUS_SURVEY_SCHEDULED,
        STATUS_QUOTATION_PREPARATION, STATUS_QUOTATION_SUBMITTED,
        STATUS_WON, STATUS_LOST,
    )

    FEASIBILITY_PENDING = 'PENDING'
    FEASIBILITY_IN_PROGRESS = 'IN_PROGRESS'
    FEASIBILITY_FEASIBLE = 'FEASIBLE'
    FEASIBILITY_NOT_FEASIBLE = 'NOT_FEASIBLE'
    FEASIBILITY_ON_HOLD = 'ON_HOLD'
    FEASIBILITY_CHOICES = (
        (FEASIBILITY_PENDING, 'Pending'),
        (FEASIBILITY_IN_PROGRESS, 'In Progress'),
        (FEASIBILITY_FEASIBLE, 'Feasible'),
        (FEASIBILITY_NOT_FEASIBLE, 'Not Feasible'),
        (FEASIBILITY_ON_HOLD, 'On Hold'),
    )

    ENQUIRY_TYPE_CHOICES = (
        ('SURVEY', 'Survey'),
        ('INSTALLATION', 'Installation'),
        ('COMPLAINT', 'Complaint'),
        ('MAINTENANCE', 'Maintenance'),
        ('AMC', 'AMC'),
        ('UPGRADE', 'Upgrade'),
    )

    SOURCE_CHOICES = (
        ('PHONE', 'Phone Call'),
        ('EMAIL', 'Email'),
        ('WEBSITE', 'Website'),
        ('REFERRAL', 'Referral'),
        ('WALK_IN', 'Walk-in'),
        ('EXISTING_CLIENT', 'Existing Client'),
        ('OTHER', 'Other'),
    )

    enquiry_number = models.CharField(max_length=30, unique=True, blank=True)
    enquiry_date = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='enquiries')
    contact_person = models.CharField(max_length=100)
    mobile = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    location = models.TextField()
    enquiry_type = models.CharField(max_length=20, choices=ENQUIRY_TYPE_CHOICES)
    description = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='PHONE')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries_assigned',
    )
    assigned_project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries_as_pm',
    )
    assigned_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries_as_supervisor',
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_NEW)
    remarks = models.TextField(blank=True)

    survey_required = models.BooleanField(default=True)
    feasibility_required = models.BooleanField(default=True)
    survey_date = models.DateField(null=True, blank=True)
    survey_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries_surveyed',
    )
    survey_remarks = models.TextField(blank=True)
    feasibility_status = models.CharField(
        max_length=20,
        choices=FEASIBILITY_CHOICES,
        default=FEASIBILITY_PENDING,
    )
    feasibility_remarks = models.TextField(blank=True)

    # CRM-ready extension fields (future modules)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_notes = models.TextField(blank=True)
    opportunity_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    lead_source_detail = models.CharField(max_length=200, blank=True)
    meeting_scheduled_at = models.DateTimeField(null=True, blank=True)
    amc_reference = models.CharField(max_length=50, blank=True)

    converted_order = models.OneToOneField(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_enquiry',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='enquiries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'enquiries'
        ordering = ['-enquiry_date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.enquiry_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_ENQUIRY
            self.enquiry_number = generate_document_number(DOC_ENQUIRY)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.enquiry_number or f'Enquiry #{self.pk}'

    @property
    def is_open(self):
        return self.status not in (
            self.STATUS_LOST, self.STATUS_CLOSED,
            self.STATUS_CONVERTED, self.STATUS_WON,
        )

    @property
    def can_convert_to_order(self):
        if self.converted_order_id:
            return False
        if self.status == self.STATUS_WON:
            return True
        return self.quotations.filter(
            status__in=('APPROVED', 'ACCEPTED', 'SENT'),
        ).exists()


class SiteProgressUpdate(models.Model):
    """Supervisor daily site progress — supports photo uploads and verification."""

    enquiry = models.ForeignKey(
        Enquiry,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='site_updates',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='site_updates',
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='site_progress_updates',
    )
    update_date = models.DateField(default=timezone.now)
    site_location = models.CharField(max_length=200, blank=True)
    work_description = models.TextField()
    progress_percent = models.PositiveSmallIntegerField(default=0)
    photo = models.ImageField(upload_to='site_progress/', blank=True, null=True)
    attendance_noted = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='site_updates_verified',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-update_date', '-created_at']

    def __str__(self):
        return f'Site update {self.update_date} — {self.supervisor}'
