"""
Fleet & Fuel Management (FVEMS) — Phase 1.

Phase 0 lock:
- Vehicle Master, Petrol Cards + recharge ledger, Fuel transactions
- Payment methods: Direct Cash | Petty Cash | Prepaid Card
- Auto distance + mileage from odometer history
- Optional links: Order, Special Project
- Cash reimbursement status kept in-module (ERMS link later)
- Petty cash: simple company balance ledger (Phase 1)
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from decimal import Decimal, ROUND_HALF_UP


class Vehicle(models.Model):
    TYPE_TWO_WHEELER = 'TWO_WHEELER'
    TYPE_FOUR_WHEELER = 'FOUR_WHEELER'
    TYPE_VAN = 'VAN'
    TYPE_TRUCK = 'TRUCK'
    TYPE_OTHER = 'OTHER'
    TYPE_CHOICES = (
        (TYPE_TWO_WHEELER, 'Two Wheeler'),
        (TYPE_FOUR_WHEELER, 'Four Wheeler'),
        (TYPE_VAN, 'Van'),
        (TYPE_TRUCK, 'Truck'),
        (TYPE_OTHER, 'Other'),
    )

    FUEL_PETROL = 'PETROL'
    FUEL_DIESEL = 'DIESEL'
    FUEL_CNG = 'CNG'
    FUEL_EV = 'EV'
    FUEL_CHOICES = (
        (FUEL_PETROL, 'Petrol'),
        (FUEL_DIESEL, 'Diesel'),
        (FUEL_CNG, 'CNG'),
        (FUEL_EV, 'EV'),
    )

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_MAINTENANCE = 'MAINTENANCE'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_MAINTENANCE, 'Under Maintenance'),
    )

    vehicle_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FOUR_WHEELER)
    brand = models.CharField(max_length=80, blank=True)
    model_name = models.CharField(max_length=80, blank=True, verbose_name='Model')
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    assigned_employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicles',
    )
    fuel_type = models.CharField(max_length=15, choices=FUEL_CHOICES, default=FUEL_PETROL)
    tank_capacity_litres = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
    )
    mileage_target_kmpl = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Average mileage target (KM/L)',
    )
    last_odometer_km = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Updated automatically from fuel entries.',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    remarks = models.TextField(blank=True)
    # Future-ready placeholders (unused in Phase 1 UI)
    insurance_expiry = models.DateField(null=True, blank=True)
    puc_expiry = models.DateField(null=True, blank=True)
    next_service_due = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['vehicle_number']

    def __str__(self):
        return self.vehicle_number

    def save(self, *args, **kwargs):
        if self.vehicle_number:
            self.vehicle_number = self.vehicle_number.strip().upper()
        super().save(*args, **kwargs)


class PetrolCard(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_BLOCKED = 'BLOCKED'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_BLOCKED, 'Blocked'),
    )

    card_name = models.CharField(max_length=120)
    card_number = models.CharField(max_length=40, unique=True)
    mobile_number = models.CharField(max_length=20, blank=True)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='petrol_cards',
    )
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_recharge_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['card_name']

    def __str__(self):
        return f'{self.card_name} ({self.card_number})'


class PetrolCardRecharge(models.Model):
    card = models.ForeignKey(PetrolCard, on_delete=models.CASCADE, related_name='recharges')
    recharge_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_number = models.CharField(max_length=80, blank=True)
    bank = models.CharField(max_length=120, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='petrol_card_recharges',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recharge_date', '-id']

    def __str__(self):
        return f'{self.card.card_number} +{self.amount}'


class PettyCashAccount(models.Model):
    """Singleton-ish company petty cash wallet for fuel (Phase 1)."""

    name = models.CharField(max_length=80, default='Company Petty Cash')
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Petty cash account'

    def __str__(self):
        return f'{self.name} ({self.current_balance})'

    @classmethod
    def get_default(cls):
        obj = cls.objects.order_by('id').first()
        if obj:
            return obj
        return cls.objects.create(name='Company Petty Cash', current_balance=Decimal('0.00'))


class PettyCashLedger(models.Model):
    TYPE_CREDIT = 'CREDIT'
    TYPE_DEBIT = 'DEBIT'
    TYPE_CHOICES = (
        (TYPE_CREDIT, 'Credit / Top-up'),
        (TYPE_DEBIT, 'Debit / Fuel'),
    )

    account = models.ForeignKey(PettyCashAccount, on_delete=models.CASCADE, related_name='entries')
    entry_date = models.DateField(default=timezone.localdate)
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reference = models.CharField(max_length=120, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    fuel_transaction = models.ForeignKey(
        'FuelTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='petty_cash_entries',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-id']


class FuelTransaction(models.Model):
    PAY_CASH = 'DIRECT_CASH'
    PAY_PETTY = 'PETTY_CASH'
    PAY_CARD = 'PETROL_CARD'
    PAYMENT_CHOICES = (
        (PAY_CASH, 'Direct Cash (Reimbursement)'),
        (PAY_PETTY, 'Petty Cash'),
        (PAY_CARD, 'Prepaid Petrol Card'),
    )

    REIMB_NONE = ''
    REIMB_PENDING = 'PENDING'
    REIMB_APPROVED = 'APPROVED'
    REIMB_REJECTED = 'REJECTED'
    REIMB_PAID = 'PAID'
    REIMB_CHOICES = (
        (REIMB_NONE, '—'),
        (REIMB_PENDING, 'Pending'),
        (REIMB_APPROVED, 'Approved'),
        (REIMB_REJECTED, 'Rejected'),
        (REIMB_PAID, 'Paid'),
    )

    transaction_date = models.DateField(default=timezone.localdate, db_index=True)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='fuel_transactions',
        verbose_name='Technician / Driver',
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='fuel_transactions')
    previous_odometer_km = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    current_odometer_km = models.DecimalField(max_digits=12, decimal_places=2)
    closing_odometer_km = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Optional; defaults to current reading.',
    )
    distance_km = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    fuel_quantity_litres = models.DecimalField(max_digits=10, decimal_places=3)
    fuel_rate = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    mileage_kmpl = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Mileage (KM/L)',
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAY_CASH)
    petrol_card = models.ForeignKey(
        PetrolCard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_transactions',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_transactions',
    )
    special_project = models.ForeignKey(
        'special_projects.SpecialProject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_transactions',
    )
    location = models.CharField(max_length=200, blank=True)
    fuel_station = models.CharField(max_length=200, blank=True)
    bill_number = models.CharField(max_length=80, blank=True)
    bill_upload = models.FileField(upload_to='fleet/fuel_bills/', blank=True)
    remarks = models.TextField(blank=True)
    odometer_warning = models.BooleanField(
        default=False,
        help_text='True when current KM is not greater than previous KM.',
    )
    reimbursement_status = models.CharField(
        max_length=15, choices=REIMB_CHOICES, blank=True, default=REIMB_NONE,
    )
    is_locked = models.BooleanField(
        default=False,
        help_text='Locked after accounts approval/payment processing.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fuel_entries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date', '-id']

    def __str__(self):
        return f'{self.vehicle.vehicle_number} — {self.transaction_date} — {self.total_amount}'

    def clean(self):
        errors = {}
        if self.fuel_quantity_litres is not None and self.fuel_quantity_litres <= 0:
            errors['fuel_quantity_litres'] = 'Fuel quantity must be greater than zero.'
        if self.fuel_rate is not None and self.fuel_rate < 0:
            errors['fuel_rate'] = 'Fuel rate cannot be negative.'
        if self.current_odometer_km is not None and self.previous_odometer_km is not None:
            if self.current_odometer_km < self.previous_odometer_km:
                # Soft warning — allow save with flag; hard-block only if wildly wrong optional
                pass
        if self.payment_method == self.PAY_CARD and not self.petrol_card_id:
            errors['petrol_card'] = 'Select a petrol card for card payments.'
        if self.payment_method != self.PAY_CARD:
            self.petrol_card = None
        if errors:
            raise ValidationError(errors)

    def recalculate(self):
        prev = self.previous_odometer_km or Decimal('0.00')
        curr = self.current_odometer_km or Decimal('0.00')
        self.odometer_warning = curr < prev
        self.distance_km = max(curr - prev, Decimal('0.00'))
        qty = self.fuel_quantity_litres or Decimal('0')
        rate = self.fuel_rate or Decimal('0')
        self.total_amount = (qty * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if qty > 0 and self.distance_km > 0:
            self.mileage_kmpl = (self.distance_km / qty).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )
        else:
            self.mileage_kmpl = None
        if not self.closing_odometer_km:
            self.closing_odometer_km = curr
