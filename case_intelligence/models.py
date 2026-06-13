from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from case_intelligence.constants import MODULE_CHOICES


class CaseActivityLog(models.Model):
    """Central activity log — enquiry-to-payment lifecycle intelligence."""

    activity_at = models.DateTimeField(auto_now_add=True, db_index=True)
    backfill_key = models.CharField(
        max_length=120, blank=True, null=True, unique=True, db_index=True,
        help_text='Idempotency key for historical backfill — not set for live events.',
    )
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, db_index=True)
    document_type = models.CharField(max_length=30, db_index=True)
    document_number = models.CharField(max_length=60, db_index=True)
    description = models.CharField(max_length=200)
    previous_status = models.CharField(max_length=50, blank=True)
    new_status = models.CharField(max_length=50, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='case_activities',
    )
    user_role = models.CharField(max_length=30, blank=True)
    remarks = models.TextField(blank=True)
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='case_activities',
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-activity_at']
        indexes = [
            models.Index(fields=['module', 'object_id']),
            models.Index(fields=['document_number']),
            models.Index(fields=['client', '-activity_at']),
            models.Index(fields=['-activity_at', 'module']),
        ]

    def __str__(self):
        return f'{self.document_number} — {self.description}'
