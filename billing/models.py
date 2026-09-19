from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone

from billing.approval import (
    APPROVAL_STATUS_CHOICES,
    REJECTION_REASON_CHOICES,
    ACTION_CHOICES,
    STATUS_APPROVED,
    STATUS_DRAFT,
)
from billing.gst import GST_TYPE_CHOICES, GST_TYPE_INTRA, calculate_gst_breakdown
from company_settings.mixins import AuthorizedSignatoryMixin
from orders.models import Order


def default_invoice_date():
    return timezone.localdate()


def default_invoice_due_date():
    return timezone.localdate() + timedelta(days=30)


class Invoice(AuthorizedSignatoryMixin, models.Model):

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RECEIVED', 'Received'),
    )

    SOURCE_ORDER = 'ORDER'
    SOURCE_IMPORT = 'IMPORT'
    SOURCE_CHOICES = (
        (SOURCE_ORDER, 'Order workflow'),
        (SOURCE_IMPORT, 'Manual import'),
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='invoice',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
    )
    boq = models.ForeignKey(
        'boq.BOQ',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        limit_choices_to={'status': 'VERIFIED'},
    )
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default=SOURCE_ORDER,
        db_index=True,
    )
    NUMBER_MODE_AUTO = 'AUTO'
    NUMBER_MODE_MANUAL = 'MANUAL'
    NUMBER_MODE_CHOICES = (
        (NUMBER_MODE_AUTO, 'Auto Generate'),
        (NUMBER_MODE_MANUAL, 'Manual Entry'),
    )

    invoice_number = models.CharField(max_length=50, unique=True)
    number_mode = models.CharField(
        max_length=10,
        choices=NUMBER_MODE_CHOICES,
        default=NUMBER_MODE_AUTO,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_type = models.CharField(
        max_length=15,
        choices=GST_TYPE_CHOICES,
        default=GST_TYPE_INTRA,
        verbose_name='GST Type',
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_date = models.DateField(default=default_invoice_date)
    due_date = models.DateField(default=default_invoice_due_date)
    po_number = models.CharField(max_length=50, blank=True, verbose_name='PO/SO No')
    po_date = models.DateField(null=True, blank=True, verbose_name='PO Date')
    billing_period_from = models.DateField(null=True, blank=True)
    billing_period_to = models.DateField(null=True, blank=True)
    import_batch = models.ForeignKey(
        'billing.InvoiceImportBatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices',
    )
    service_title = models.CharField(max_length=200, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='PENDING',
    )
    approval_status = models.CharField(
        max_length=15,
        choices=APPROVAL_STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_created',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_submitted',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_approved',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_rejected',
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(
        max_length=20,
        blank=True,
        choices=REJECTION_REASON_CHOICES,
    )
    approval_remarks = models.TextField(blank=True)

    def recalculate_totals(self, gst_type=None):
        subtotal = sum(
            (line.line_amount for line in self.line_items.all()),
            Decimal('0'),
        )
        self.amount = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if gst_type:
            self.gst_type = gst_type
        breakdown = calculate_gst_breakdown(self.amount, self.gst_type)
        self.gst = breakdown['gst']
        self.cgst_amount = breakdown['cgst_amount']
        self.sgst_amount = breakdown['sgst_amount']
        self.igst_amount = breakdown['igst_amount']
        self.total = self.amount + self.gst

    def _sync_order_billing_status(self):
        if not self.order_id:
            return
        if self.approval_status != STATUS_APPROVED:
            return
        if self.payment_status == 'RECEIVED':
            self.order.status = 'CLOSED'
        else:
            self.order.status = 'BILLED'
        self.order.save(update_fields=['status'])

    def save(self, *args, **kwargs):
        if self.order_id and not self.client_id:
            self.client_id = self.order.client_id
        if self.pk and self.line_items.exists():
            self.recalculate_totals()
        super().save(*args, **kwargs)
        self._sync_order_billing_status()

    @property
    def billing_client(self):
        if self.client_id:
            return self.client
        if self.order_id:
            return self.order.client
        return None

    @property
    def is_pdf_available(self):
        return self.approval_status == STATUS_APPROVED

    def __str__(self):
        return self.invoice_number


class InvoiceLineItem(models.Model):

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    sl_no = models.PositiveIntegerField()
    description = models.TextField(verbose_name='Item / Service Description')
    hsn_sac = models.CharField(max_length=20, verbose_name='HSN / SAC code')
    unit = models.CharField(max_length=20, default='Nos')
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.CharField(max_length=255, blank=True)
    from_boq = models.BooleanField(default=False, help_text='Line copied from verified BOQ')

    class Meta:
        ordering = ['sl_no']

    @property
    def line_amount(self):
        return (self.qty * self.rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f"{self.sl_no}. {self.description[:40]}"


class InvoiceGstAuditLog(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='gst_audit_logs',
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invoice_gst_audits',
    )
    client_gst_type = models.CharField(max_length=15, blank=True)
    previous_gst_type = models.CharField(max_length=15, blank=True)
    new_gst_type = models.CharField(max_length=15)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.invoice.invoice_number}: {self.previous_gst_type} → {self.new_gst_type}'


class InvoiceApprovalAuditLog(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='approval_audit_logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invoice_approval_actions',
    )
    previous_status = models.CharField(max_length=15, blank=True)
    new_status = models.CharField(max_length=15, blank=True)
    remarks = models.TextField(blank=True)
    rejection_reason = models.CharField(max_length=20, blank=True)
    notification_channel = models.CharField(
        max_length=30,
        blank=True,
        help_text='Reserved for future email/WhatsApp/mobile notifications',
    )
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.invoice.invoice_number}: {self.action}'


class InvoiceImportBatch(models.Model):
    STATUS_VALIDATED = 'VALIDATED'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = (
        (STATUS_VALIDATED, 'Validated'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    )

    title = models.CharField(max_length=200, blank=True)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to='billing_imports/%Y/%m/', blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invoice_import_batches',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_VALIDATED,
        db_index=True,
    )
    total_rows = models.PositiveIntegerField(default=0)
    invoice_count = models.PositiveIntegerField(default=0)
    valid_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    confirm_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title or self.original_filename


class InvoiceImportItem(models.Model):
    STATUS_VALID = 'VALID'
    STATUS_WARNING = 'WARNING'
    STATUS_ERROR = 'ERROR'
    STATUS_ALREADY_EXISTS = 'ALREADY_EXISTS'
    STATUS_CREATED = 'CREATED'
    STATUS_FAILED = 'FAILED'
    STATUS_SKIPPED = 'SKIPPED'
    STATUS_CHOICES = (
        (STATUS_VALID, 'Valid'),
        (STATUS_WARNING, 'Warning'),
        (STATUS_ERROR, 'Error'),
        (STATUS_ALREADY_EXISTS, 'Already exists'),
        (STATUS_CREATED, 'Created'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    )

    batch = models.ForeignKey(
        InvoiceImportBatch,
        on_delete=models.CASCADE,
        related_name='items',
    )
    sort_order = models.PositiveIntegerField(default=0)
    grouping_key = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=50, blank=True)
    number_mode = models.CharField(max_length=10, default=Invoice.NUMBER_MODE_MANUAL)
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_VALID)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    created_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='import_items',
    )

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.invoice_number or self.grouping_key
