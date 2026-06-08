from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.db.models import Sum
from orders.models import Order
from config.company import COMPANY
from company_settings.mixins import AuthorizedSignatoryMixin


class Invoice(AuthorizedSignatoryMixin, models.Model):

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('RECEIVED', 'Received'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    boq = models.ForeignKey(
        'boq.BOQ',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        limit_choices_to={'status': 'VERIFIED'},
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
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    po_number = models.CharField(max_length=50, blank=True, verbose_name='PO/SO No')
    po_date = models.DateField(null=True, blank=True, verbose_name='PO Date')
    service_title = models.CharField(max_length=200, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='PENDING',
    )

    def recalculate_totals(self):
        subtotal = sum(
            (line.line_amount for line in self.line_items.all()),
            Decimal('0'),
        )
        self.amount = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        rate = Decimal(COMPANY['gst_rate_percent']) / 100
        self.gst = (self.amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = self.amount + self.gst

    def save(self, *args, **kwargs):
        if self.pk and self.line_items.exists():
            self.recalculate_totals()
        super().save(*args, **kwargs)
        if self.payment_status == 'RECEIVED':
            self.order.status = 'CLOSED'
        else:
            self.order.status = 'BILLED'
        self.order.save(update_fields=['status'])

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
