from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from .constants import (
    ALLOWED_EXTENSIONS,
    PRIORITY_CHOICES,
    PRIORITY_NORMAL,
    STATUS_CHOICES,
    STATUS_DRAFT,
)


class RequestType(models.Model):
    """Configurable request types — admin can add more."""

    codename = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    requires_amount = models.BooleanField(default=False)
    approver_role_hints = models.CharField(
        max_length=200,
        blank=True,
        help_text='Comma-separated role codenames suggested for Submitted To dropdown.',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    # Future: multi-level approval chain JSON, SLA hours, escalation rules.
    approval_chain_config = models.JSONField(default=dict, blank=True)
    notification_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class EmployeeRequest(models.Model):
    request_number = models.CharField(max_length=30, unique=True, blank=True, db_index=True)
    request_date = models.DateField(default=timezone.localdate, db_index=True)
    request_type = models.ForeignKey(
        RequestType,
        on_delete=models.PROTECT,
        related_name='requests',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='employee_requests_created',
    )
    department = models.CharField(max_length=100, blank=True)
    submitted_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='employee_requests_inbox',
        null=True,
        blank=True,
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    remarks = models.TextField(blank=True)
    # Future hooks: SLA due date, escalation level, current approval step.
    sla_due_at = models.DateTimeField(null=True, blank=True)
    approval_step = models.PositiveSmallIntegerField(default=1)
    escalation_level = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-request_date', '-created_at']

    def __str__(self):
        return self.request_number or f'Draft #{self.pk}'

    def save(self, *args, **kwargs):
        if not self.request_number and self.status != STATUS_DRAFT:
            from document_generator.constants import DOC_REQUEST
            from document_generator.services import generate_document_number
            self.request_number = generate_document_number(DOC_REQUEST)
        super().save(*args, **kwargs)


class RequestAttachment(models.Model):
    request = models.ForeignKey(
        EmployeeRequest,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(
        upload_to='employee_requests/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=list(ALLOWED_EXTENSIONS))],
    )
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']


class RequestApprovalHistory(models.Model):
    request = models.ForeignKey(
        EmployeeRequest,
        on_delete=models.CASCADE,
        related_name='approval_history',
    )
    action = models.CharField(max_length=40, db_index=True)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_approval_actions',
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Future: approval step index, channel (portal/email/whatsapp).
    channel = models.CharField(max_length=20, default='portal', blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'Request approval history'


class PortalNotification(models.Model):
    """In-portal notifications for request workflow."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portal_notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    related_request = models.ForeignKey(
        EmployeeRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Future: email_sent_at, whatsapp_sent_at.
    email_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
