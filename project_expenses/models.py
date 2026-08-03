"""
Project Expense & Advance Management (PEAMS) — Phase 1.

Central financial control layer for project expenses.
- Single LedgerTransaction source for employee / project / financial views
- Advances + expense claims with configurable approval limits
- Fleet fuel: reference only (no duplicate fuel entry)
- Special Projects daily expenses: sync financial totals into ledger
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ExpenseCategory(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    # Future: gst_applicable, gl_account_code, cost_center_default
    gl_account_code = models.CharField(max_length=40, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Expense categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper().replace(' ', '_')
        super().save(*args, **kwargs)


class PeamsSettings(models.Model):
    """Singleton PEAMS configuration (approval thresholds, etc.)."""

    director_approval_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text='Expenses at or above this amount require Director approval.',
    )
    default_currency = models.CharField(max_length=10, default='INR')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'PEAMS settings'
        verbose_name_plural = 'PEAMS settings'

    def __str__(self):
        return 'PEAMS Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ApprovalLimit(models.Model):
    """
    Configurable approval steps and per-step amount limits.
    Step is required when expense amount is within [min_amount, max_amount]
    (max_amount null = no upper bound for that step's applicability).
    """

    STEP_MANAGER = 'MANAGER'
    STEP_ACCOUNTS = 'ACCOUNTS'
    STEP_DIRECTOR = 'DIRECTOR'
    STEP_CHOICES = (
        (STEP_MANAGER, 'Manager'),
        (STEP_ACCOUNTS, 'Accounts'),
        (STEP_DIRECTOR, 'Director'),
    )

    step_code = models.CharField(max_length=20, choices=STEP_CHOICES)
    step_order = models.PositiveSmallIntegerField(default=10)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    max_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Leave blank for unlimited. Step applies when amount >= min and (<= max if set).',
    )
    can_approve_up_to = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Approver at this step may approve up to this amount; blank = unlimited.',
    )
    is_active = models.BooleanField(default=True)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['step_order', 'min_amount']

    def __str__(self):
        return f'{self.get_step_code_display()} (order {self.step_order})'


class EmployeeAdvance(models.Model):
    STATUS_OPEN = 'OPEN'
    STATUS_ADJUSTED = 'ADJUSTED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_ADJUSTED, 'Adjusted'),
        (STATUS_CLOSED, 'Closed'),
    )

    advance_number = models.CharField(max_length=40, unique=True, blank=True)
    advance_date = models.DateField(default=timezone.localdate, db_index=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='project_advances',
    )
    special_project = models.ForeignKey(
        'special_projects.SpecialProject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advances',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_advances',
    )
    purpose = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='advances_issued',
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)
    remarks = models.TextField(blank=True)
    is_posted = models.BooleanField(default=False)
    # Future: accounts_voucher_no, payroll_deduction_ref
    accounts_voucher_ref = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-advance_date', '-id']

    def __str__(self):
        return self.advance_number or f'Advance #{self.pk}'

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Advance amount must be greater than zero.'})


class ProjectExpense(models.Model):
    """Employee / ops expense claim (workflow document). Posts to LedgerTransaction on approval."""

    PAY_PERSONAL = 'PERSONAL_CASH'
    PAY_ADVANCE = 'AGAINST_ADVANCE'
    PAY_BANK = 'BANK_TRANSFER'
    PAY_PETROL_CARD = 'PETROL_CARD'  # must reference Fleet FuelTransaction
    PAY_CREDIT_CARD = 'CREDIT_CARD'  # future
    PAYMENT_CHOICES = (
        (PAY_PERSONAL, 'Employee Personal Cash (Reimbursement)'),
        (PAY_ADVANCE, 'Against Employee Advance'),
        (PAY_BANK, 'Company Bank Transfer'),
        (PAY_PETROL_CARD, 'Prepaid Petrol Card (Fleet)'),
        (PAY_CREDIT_CARD, 'Company Credit Card (Future)'),
    )

    STATUS_DRAFT = 'DRAFT'
    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_MANAGER = 'MANAGER_REVIEW'
    STATUS_ACCOUNTS = 'ACCOUNTS_REVIEW'
    STATUS_DIRECTOR = 'DIRECTOR_REVIEW'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_PAID = 'PAID'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_MANAGER, 'Manager Review'),
        (STATUS_ACCOUNTS, 'Accounts Review'),
        (STATUS_DIRECTOR, 'Director Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_PAID, 'Payment Released'),
        (STATUS_CLOSED, 'Closed'),
    )

    REIMB_NONE = ''
    REIMB_PENDING = 'PENDING'
    REIMB_APPROVED = 'APPROVED'
    REIMB_PAID = 'PAID'
    REIMB_REJECTED = 'REJECTED'
    REIMB_CHOICES = (
        (REIMB_NONE, '—'),
        (REIMB_PENDING, 'Pending'),
        (REIMB_APPROVED, 'Approved'),
        (REIMB_PAID, 'Paid'),
        (REIMB_REJECTED, 'Rejected'),
    )

    expense_number = models.CharField(max_length=40, unique=True, blank=True)
    expense_date = models.DateField(default=timezone.localdate, db_index=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='project_expenses',
    )
    special_project = models.ForeignKey(
        'special_projects.SpecialProject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_expenses',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_expenses',
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name='expenses',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAY_PERSONAL)
    advance = models.ForeignKey(
        EmployeeAdvance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expense_adjustments',
    )
    # Fleet reference only — do not recreate fuel fields here
    fuel_transaction = models.ForeignKey(
        'fleet.FuelTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_expenses',
    )
    vendor_name = models.CharField(max_length=200, blank=True)
    description = models.CharField(max_length=255)
    location = models.CharField(max_length=200, blank=True)
    bill_upload = models.FileField(upload_to='project_expenses/bills/', blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    current_step = models.CharField(max_length=20, blank=True)
    reimbursement_status = models.CharField(
        max_length=15, choices=REIMB_CHOICES, blank=True, default=REIMB_NONE,
    )
    is_posted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_expenses_created',
    )
    # Future integration placeholders
    accounts_voucher_ref = models.CharField(max_length=60, blank=True)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    purchase_order_ref = models.CharField(max_length=60, blank=True)
    opms_activity_ref = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return self.expense_number or f'Expense #{self.pk}'

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors['amount'] = 'Amount must be greater than zero.'
        if self.payment_method == self.PAY_PETROL_CARD and not self.fuel_transaction_id:
            errors['fuel_transaction'] = 'Link a Fleet fuel transaction for petrol card payments.'
        if self.payment_method == self.PAY_ADVANCE and not self.advance_id:
            errors['advance'] = 'Select an open advance to adjust against.'
        if self.payment_method == self.PAY_CREDIT_CARD:
            errors['payment_method'] = 'Company credit card is reserved for a future phase.'
        if errors:
            raise ValidationError(errors)


class ExpenseApprovalHistory(models.Model):
    ACTION_SUBMIT = 'SUBMIT'
    ACTION_APPROVE = 'APPROVE'
    ACTION_REJECT = 'REJECT'
    ACTION_RETURN = 'RETURN'
    ACTION_PAY = 'PAY'
    ACTION_CHOICES = (
        (ACTION_SUBMIT, 'Submitted'),
        (ACTION_APPROVE, 'Approved step'),
        (ACTION_REJECT, 'Rejected'),
        (ACTION_RETURN, 'Returned'),
        (ACTION_PAY, 'Payment released'),
    )

    expense = models.ForeignKey(ProjectExpense, on_delete=models.CASCADE, related_name='approvals')
    action = models.CharField(max_length=15, choices=ACTION_CHOICES)
    step_code = models.CharField(max_length=20, blank=True)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    remarks = models.CharField(max_length=255, blank=True)
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-acted_at']


class LedgerTransaction(models.Model):
    """
    Single transaction ledger — source of truth for employee, project, and financial reports.
    Domain documents (Advance / Expense / SP daily line / Fleet fuel ref) post here.
    """

    TYPE_ADVANCE_ISSUE = 'ADVANCE_ISSUE'
    TYPE_ADVANCE_ADJUST = 'ADVANCE_ADJUST'
    TYPE_ADVANCE_SETTLE = 'ADVANCE_SETTLE'
    TYPE_EXPENSE = 'EXPENSE'
    TYPE_SP_DAILY_SYNC = 'SP_DAILY_SYNC'
    TYPE_FLEET_FUEL_REF = 'FLEET_FUEL_REF'
    TYPE_REIMBURSEMENT_PAY = 'REIMBURSEMENT_PAY'
    TYPE_CHOICES = (
        (TYPE_ADVANCE_ISSUE, 'Advance issued'),
        (TYPE_ADVANCE_ADJUST, 'Advance adjusted (expense)'),
        (TYPE_ADVANCE_SETTLE, 'Advance settled / returned'),
        (TYPE_EXPENSE, 'Project expense'),
        (TYPE_SP_DAILY_SYNC, 'Special Project daily expense sync'),
        (TYPE_FLEET_FUEL_REF, 'Fleet fuel cost reference'),
        (TYPE_REIMBURSEMENT_PAY, 'Reimbursement payment'),
    )

    txn_number = models.CharField(max_length=40, unique=True, blank=True)
    txn_date = models.DateField(default=timezone.localdate, db_index=True)
    txn_type = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger',
    )
    special_project = models.ForeignKey(
        'special_projects.SpecialProject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger',
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    # Employee advance running balance semantics: debit = advance out, credit = adjust/return
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # Project / P&L cost amount (usually same as debit or credit depending on type)
    project_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    description = models.CharField(max_length=255, blank=True)
    advance = models.ForeignKey(
        EmployeeAdvance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    expense = models.ForeignKey(
        ProjectExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    fuel_transaction = models.ForeignKey(
        'fleet.FuelTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger',
    )
    daily_expense_line = models.OneToOneField(
        'special_projects.DailyExpenseLine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger',
    )
    is_void = models.BooleanField(default=False)
    # Future: Accounts / GST / TDS / Vendor / Payroll / OPMS
    accounts_voucher_ref = models.CharField(max_length=60, blank=True)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vendor_name = models.CharField(max_length=200, blank=True)
    cost_center = models.CharField(max_length=60, blank=True)
    payroll_period = models.CharField(max_length=20, blank=True)
    opms_activity_ref = models.CharField(max_length=60, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='peams_ledger_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['txn_date', 'id']

    def __str__(self):
        return self.txn_number or f'LED-{self.pk}'
