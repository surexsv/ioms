from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from orders.models import Order
from company_settings.mixins import AuthorizedSignatoryMixin


class BOQ(AuthorizedSignatoryMixin, models.Model):

    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('VERIFIED', 'Verified'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='boqs')
    boq_number = models.CharField(max_length=30, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='boqs_created',
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='boqs_verified',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'BOQ'
        verbose_name_plural = 'BOQs'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.boq_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_BOQ
            self.boq_number = generate_document_number(DOC_BOQ)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.boq_number

    @property
    def is_editable(self):
        return self.status == 'DRAFT'


class BOQLineItem(models.Model):

    boq = models.ForeignKey(BOQ, on_delete=models.CASCADE, related_name='lines')
    sl_no = models.PositiveIntegerField()
    description = models.TextField(verbose_name='Item / Service Description')
    hsn_sac = models.CharField(max_length=20, verbose_name='HSN / SAC code')
    unit = models.CharField(max_length=20, default='Nos')
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)

    class Meta:
        ordering = ['sl_no']
        unique_together = [['boq', 'sl_no']]

    def __str__(self):
        return f"{self.sl_no}. {self.description[:40]}"
