from django.conf import settings
from django.db import models

from .constants import DOCUMENT_TYPES


class DocumentNumberSettings(models.Model):
    """Singleton master settings for document numbering."""

    company_prefix = models.CharField(max_length=10, default='ITSPL')
    order_prefix = models.CharField(max_length=10, default='ORD')
    quotation_prefix = models.CharField(max_length=10, default='QT')
    wcr_prefix = models.CharField(max_length=10, default='WCR')
    boq_prefix = models.CharField(max_length=10, default='BOQ')
    invoice_prefix = models.CharField(max_length=10, default='INV')
    purchase_order_prefix = models.CharField(max_length=10, default='PO')
    schedule_prefix = models.CharField(max_length=10, default='SCH')
    serial_length = models.PositiveSmallIntegerField(default=4)
    year_format = models.CharField(max_length=10, default='YYYY')
    allow_editing = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_number_settings_updates',
    )

    class Meta:
        verbose_name = 'Document number settings'
        verbose_name_plural = 'Document number settings'

    def __str__(self):
        return 'Document Number Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def prefix_for(self, document_type):
        from .constants import PREFIX_FIELD_MAP
        return getattr(self, PREFIX_FIELD_MAP[document_type])


class DocumentCounter(models.Model):
    """Per document-type, per year-series serial counter."""

    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    year_series = models.CharField(max_length=4)
    last_serial = models.PositiveIntegerField(default=0)
    last_number = models.CharField(max_length=50, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['document_type', 'year_series']]
        ordering = ['document_type', '-year_series']

    def __str__(self):
        return f'{self.document_type} {self.year_series}: {self.last_serial}'


class GeneratedDocumentNumber(models.Model):
    """Audit log of generated document numbers."""

    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_number = models.CharField(max_length=50, unique=True)
    year_series = models.CharField(max_length=4)
    serial = models.PositiveIntegerField()
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_document_numbers',
    )

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return self.document_number
