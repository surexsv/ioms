from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone

from clients.models import Client
from company_settings.mixins import AuthorizedSignatoryMixin

from .defaults import (
    DEFAULT_BANK_DETAILS,
    DEFAULT_CLOSING_PARAGRAPH,
    DEFAULT_COMPANY_INTRODUCTION,
    DEFAULT_COVERING_LETTER_BODY,
    DEFAULT_COVERING_LETTER_SUBJECT,
    DEFAULT_FOOTER_NOTES,
    DEFAULT_PAYMENT_TERMS,
    DEFAULT_TERMS_AND_CONDITIONS,
    DEFAULT_VALIDITY_DAYS,
    DEFAULT_VALIDITY_PERIOD,
    SEED_PROPOSAL_TEMPLATES,
)


def _money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class ServiceRateCard(models.Model):
    service_code = models.CharField(max_length=30, unique=True)
    service_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=20, default='Nos')
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    is_active = models.BooleanField(default=True)
    rate_revision_date = models.DateField(null=True, blank=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_rates_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['service_code']

    def __str__(self):
        return f"{self.service_code} — {self.service_name}"


class MaterialRateCard(models.Model):
    item_code = models.CharField(max_length=30, unique=True)
    item_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=20, default='Nos')
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    is_active = models.BooleanField(default=True)
    rate_revision_date = models.DateField(null=True, blank=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='material_rates_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_code']

    def __str__(self):
        return f"{self.item_code} — {self.item_name}"


class QuotationSettings(models.Model):
    """Singleton master settings for quotation documents."""

    terms_and_conditions = models.TextField(
        default=DEFAULT_TERMS_AND_CONDITIONS,
        help_text='Standard terms printed on every quotation.',
    )
    payment_terms = models.TextField(
        default=DEFAULT_PAYMENT_TERMS,
        help_text='Payment terms section.',
    )
    validity_period = models.TextField(
        default=DEFAULT_VALIDITY_PERIOD,
        help_text='Validity wording shown on quotations.',
    )
    validity_days = models.PositiveSmallIntegerField(
        default=DEFAULT_VALIDITY_DAYS,
        help_text='Default number of days for Valid Until on new quotations.',
    )
    bank_details = models.TextField(
        default=DEFAULT_BANK_DETAILS,
        help_text='Company bank details printed on quotations.',
    )
    footer_notes = models.TextField(
        blank=True,
        default=DEFAULT_FOOTER_NOTES,
        help_text='Optional footer notes below the signature block.',
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_settings_updates',
    )

    class Meta:
        verbose_name = 'Quotation settings'
        verbose_name_plural = 'Quotation settings'

    def __str__(self):
        return 'Quotation Master Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'terms_and_conditions': DEFAULT_TERMS_AND_CONDITIONS,
                'payment_terms': DEFAULT_PAYMENT_TERMS,
                'validity_period': DEFAULT_VALIDITY_PERIOD,
                'validity_days': DEFAULT_VALIDITY_DAYS,
                'bank_details': DEFAULT_BANK_DETAILS,
                'footer_notes': DEFAULT_FOOTER_NOTES,
            },
        )
        return obj


class CoveringLetterSettings(models.Model):
    """Singleton settings for covering letter defaults."""

    company_introduction = models.TextField(default=DEFAULT_COMPANY_INTRODUCTION)
    default_subject = models.CharField(max_length=255, default=DEFAULT_COVERING_LETTER_SUBJECT)
    default_body = models.TextField(default=DEFAULT_COVERING_LETTER_BODY)
    closing_paragraph = models.TextField(default=DEFAULT_CLOSING_PARAGRAPH)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='covering_letter_settings_updates',
    )

    class Meta:
        verbose_name = 'Covering letter settings'
        verbose_name_plural = 'Covering letter settings'

    def __str__(self):
        return 'Covering Letter Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'company_introduction': DEFAULT_COMPANY_INTRODUCTION,
                'default_subject': DEFAULT_COVERING_LETTER_SUBJECT,
                'default_body': DEFAULT_COVERING_LETTER_BODY,
                'closing_paragraph': DEFAULT_CLOSING_PARAGRAPH,
            },
        )
        return obj


class ProposalTemplate(models.Model):
    """Reusable covering letter / proposal templates."""

    name = models.CharField(max_length=120, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposal_templates_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            ProposalTemplate.objects.exclude(pk=self.pk).update(is_default=False)

    @classmethod
    def get_default(cls):
        obj = cls.objects.filter(is_default=True).first()
        if obj:
            return obj
        return cls.objects.order_by('pk').first()

    @classmethod
    def ensure_seed_templates(cls):
        if cls.objects.exists():
            return
        for item in SEED_PROPOSAL_TEMPLATES:
            cls.objects.create(
                name=item['name'],
                subject=item['subject'],
                body=item['body'],
                is_default=item.get('is_default', False),
            )


class RateCardAuditLog(models.Model):
    RATE_TYPE_CHOICES = (
        ('SERVICE', 'Service Rate Card'),
        ('MATERIAL', 'Material Rate Card'),
    )
    ACTION_CHOICES = (
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
    )

    rate_type = models.CharField(max_length=10, choices=RATE_TYPE_CHOICES)
    record_code = models.CharField(max_length=30)
    record_name = models.CharField(max_length=200)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=50, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    revised_at = models.DateTimeField(auto_now_add=True)
    revised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rate_card_audits',
    )

    class Meta:
        ordering = ['-revised_at']

    def __str__(self):
        return f"{self.rate_type} {self.record_code} — {self.action}"


class Quotation(AuthorizedSignatoryMixin, models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('SENT', 'Sent'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('CONVERTED', 'Converted To Order'),
    )

    quotation_number = models.CharField(max_length=30, unique=True, blank=True)
    quotation_date = models.DateField(default=timezone.now)
    valid_until = models.DateField()
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='quotations')
    contact_person = models.CharField(max_length=100)
    site_location = models.TextField()
    subject = models.CharField(max_length=255)
    scope_of_work = models.TextField()
    reference_number = models.CharField(max_length=80, blank=True)
    proposal_template = models.ForeignKey(
        ProposalTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
    )
    covering_letter_subject = models.CharField(max_length=255, blank=True)
    covering_letter_body = models.TextField(blank=True)
    include_covering_letter = models.BooleanField(default=True)
    include_terms = models.BooleanField(default=True)
    include_company_seal = models.BooleanField(default=True)
    include_signature = models.BooleanField(default=True)
    terms_and_conditions = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='quotations_created',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations_approved',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gst_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    enquiry = models.ForeignKey(
        'enquiries.Enquiry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
    )
    estimate_boq = models.ForeignKey(
        'estimate_boq.EstimateBOQ',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
    )
    converted_order = models.OneToOneField(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_source',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-quotation_date', '-id']

    def __str__(self):
        return self.quotation_number or f"Quotation #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            from document_generator.services import generate_document_number
            from document_generator.constants import DOC_QUOTATION
            self.quotation_number = generate_document_number(DOC_QUOTATION)
        super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status in ('DRAFT', 'UNDER_REVIEW', 'REJECTED')

    def recalculate_totals(self):
        mat = self.material_lines.all()
        svc = self.service_lines.all()
        subtotal = Decimal('0')
        gst_total = Decimal('0')
        for line in list(mat) + list(svc):
            subtotal += line.line_amount
            gst_total += line.line_gst_amount
        self.subtotal = _money(subtotal)
        self.gst_total = _money(gst_total)
        self.grand_total = _money(subtotal + gst_total)

    def can_transition_to(self, new_status):
        allowed = {
            'DRAFT': {'UNDER_REVIEW'},
            'UNDER_REVIEW': {'APPROVED', 'DRAFT'},
            'APPROVED': {'SENT', 'UNDER_REVIEW'},
            'SENT': {'ACCEPTED', 'REJECTED'},
            'ACCEPTED': {'CONVERTED'},
            'REJECTED': {'DRAFT'},
            'CONVERTED': set(),
        }
        return new_status in allowed.get(self.status, set())


class QuotationMaterialLine(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name='material_lines',
    )
    material_item = models.ForeignKey(
        MaterialRateCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_lines',
    )
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, default='Nos')
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    line_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def compute_line(self):
        self.line_amount = _money(self.quantity * self.unit_rate)
        self.line_gst_amount = _money(self.line_amount * self.gst_percent / 100)
        self.line_total = _money(self.line_amount + self.line_gst_amount)

    def save(self, *args, **kwargs):
        self.compute_line()
        super().save(*args, **kwargs)


class QuotationServiceLine(models.Model):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name='service_lines',
    )
    service_item = models.ForeignKey(
        ServiceRateCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_lines',
    )
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=20, default='Nos')
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    line_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_gst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def compute_line(self):
        self.line_amount = _money(self.quantity * self.unit_rate)
        self.line_gst_amount = _money(self.line_amount * self.gst_percent / 100)
        self.line_total = _money(self.line_amount + self.line_gst_amount)

    def save(self, *args, **kwargs):
        self.compute_line()
        super().save(*args, **kwargs)
