from decimal import Decimal

from django.conf import settings
from django.db import models


class EstimateBOQ(models.Model):
    """Pre-sales estimate BOQ for survey/feasibility costing — NOT execution BOQ."""

    STATUS_DRAFT = 'DRAFT'
    STATUS_FINALIZED = 'FINALIZED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_FINALIZED, 'Finalized'),
    )

    estimate_boq_number = models.CharField(max_length=30, unique=True, blank=True)
    enquiry = models.ForeignKey(
        'enquiries.Enquiry',
        on_delete=models.CASCADE,
        related_name='estimate_boqs',
    )
    title = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='estimate_boqs_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Estimate BOQ'
        verbose_name_plural = 'Estimate BOQs'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.estimate_boq_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_ESTIMATE_BOQ
            self.estimate_boq_number = generate_document_number(DOC_ESTIMATE_BOQ)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.estimate_boq_number

    @property
    def total_amount(self):
        return sum((line.amount for line in self.lines.all()), Decimal('0'))

    def recalculate(self):
        for line in self.lines.all():
            line.save()


class EstimateBOQLineItem(models.Model):
    estimate_boq = models.ForeignKey(
        EstimateBOQ,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    sl_no = models.PositiveIntegerField()
    item = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, default='Nos')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['sl_no']
        unique_together = [['estimate_boq', 'sl_no']]

    def save(self, *args, **kwargs):
        self.amount = (self.quantity * self.rate).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.sl_no}. {self.item}'
