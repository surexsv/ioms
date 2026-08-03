from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    ApprovalLimit,
    EmployeeAdvance,
    ExpenseApprovalHistory,
    ExpenseCategory,
    LedgerTransaction,
    PeamsSettings,
    ProjectExpense,
)

DEFAULT_CATEGORIES = [
    ('FUEL', 'Fuel', 10),
    ('FOOD', 'Food', 20),
    ('ACCOMMODATION', 'Accommodation', 30),
    ('TRAVEL', 'Travel', 40),
    ('PARKING', 'Parking', 50),
    ('TOLL', 'Toll', 60),
    ('LABOUR_PAYMENT', 'Labour Payment', 70),
    ('LOCAL_PURCHASE', 'Local Purchase', 80),
    ('COURIER', 'Courier', 90),
    ('PRINTING', 'Printing', 100),
    ('VEHICLE_REPAIR', 'Vehicle Repair', 110),
    ('MATERIAL_TRANSPORT', 'Material Transportation', 120),
    ('EQUIPMENT_HIRE', 'Equipment Hire', 130),
    ('SITE_EXPENSES', 'Site Expenses', 140),
    ('MISCELLANEOUS', 'Miscellaneous', 150),
]

# Map Special Project daily expense_type → PEAMS category code
SP_EXPENSE_TO_CATEGORY = {
    'FUEL': 'FUEL',
    'FOOD': 'FOOD',
    'ACCOMMODATION': 'ACCOMMODATION',
    'LOCAL_TRANSPORT': 'TRAVEL',
    'PARKING': 'PARKING',
    'TOLL': 'TOLL',
    'COURIER': 'COURIER',
    'EQUIPMENT_HIRE': 'EQUIPMENT_HIRE',
    'MISC': 'MISCELLANEOUS',
}


def seed_default_categories():
    for code, name, order in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.update_or_create(
            code=code,
            defaults={'name': name, 'sort_order': order, 'is_active': True},
        )


def seed_default_approval_limits():
    """Basic chain: Manager → Accounts; Director when amount >= threshold (settings)."""
    if ApprovalLimit.objects.exists():
        return
    ApprovalLimit.objects.bulk_create([
        ApprovalLimit(
            step_code=ApprovalLimit.STEP_MANAGER,
            step_order=10,
            min_amount=Decimal('0.00'),
            max_amount=None,
            can_approve_up_to=None,
        ),
        ApprovalLimit(
            step_code=ApprovalLimit.STEP_ACCOUNTS,
            step_order=20,
            min_amount=Decimal('0.00'),
            max_amount=None,
            can_approve_up_to=None,
        ),
        ApprovalLimit(
            step_code=ApprovalLimit.STEP_DIRECTOR,
            step_order=30,
            min_amount=PeamsSettings.get_solo().director_approval_threshold,
            max_amount=None,
            can_approve_up_to=None,
            remarks='Applies when amount >= director threshold',
        ),
    ])


def _next_number(prefix, model, field):
    year = timezone.localdate().strftime('%y')
    stem = f'{prefix}{year}'
    last = (
        model.objects.filter(**{f'{field}__startswith': stem})
        .order_by(f'-{field}')
        .values_list(field, flat=True)
        .first()
    )
    serial = 1
    if last:
        try:
            serial = int(str(last)[-4:]) + 1
        except ValueError:
            serial = model.objects.count() + 1
    return f'{stem}{serial:04d}'


def allocate_advance_number():
    return _next_number('ADV', EmployeeAdvance, 'advance_number')


def allocate_expense_number():
    return _next_number('EXP', ProjectExpense, 'expense_number')


def allocate_txn_number():
    return _next_number('LED', LedgerTransaction, 'txn_number')


def resolve_approval_steps(amount):
    """
    Return ordered list of step_codes required for this amount.
    Director is appended when amount >= PeamsSettings.director_approval_threshold.
    """
    amount = amount or Decimal('0')
    settings = PeamsSettings.get_solo()
    if not ApprovalLimit.objects.filter(is_active=True).exists():
        seed_default_approval_limits()

    steps = []
    for lim in ApprovalLimit.objects.filter(is_active=True).order_by('step_order'):
        if lim.step_code == ApprovalLimit.STEP_DIRECTOR:
            continue
        if amount < lim.min_amount:
            continue
        if lim.max_amount is not None and amount > lim.max_amount:
            continue
        if lim.step_code not in steps:
            steps.append(lim.step_code)

    if ApprovalLimit.STEP_MANAGER not in steps:
        steps.insert(0, ApprovalLimit.STEP_MANAGER)
    if ApprovalLimit.STEP_ACCOUNTS not in steps:
        idx = steps.index(ApprovalLimit.STEP_MANAGER) + 1 if ApprovalLimit.STEP_MANAGER in steps else len(steps)
        steps.insert(idx, ApprovalLimit.STEP_ACCOUNTS)

    if amount >= settings.director_approval_threshold:
        if ApprovalLimit.STEP_DIRECTOR not in steps:
            steps.append(ApprovalLimit.STEP_DIRECTOR)
    return steps


def _status_for_step(step):
    return {
        ApprovalLimit.STEP_MANAGER: ProjectExpense.STATUS_MANAGER,
        ApprovalLimit.STEP_ACCOUNTS: ProjectExpense.STATUS_ACCOUNTS,
        ApprovalLimit.STEP_DIRECTOR: ProjectExpense.STATUS_DIRECTOR,
    }.get(step, ProjectExpense.STATUS_SUBMITTED)


@transaction.atomic
def post_ledger(**kwargs):
    txn = LedgerTransaction(**kwargs)
    if not txn.txn_number:
        txn.txn_number = allocate_txn_number()
    txn.save()
    return txn


def employee_advance_balance(employee, as_of=None):
    qs = LedgerTransaction.objects.filter(employee=employee, is_void=False)
    if as_of:
        qs = qs.filter(txn_date__lte=as_of)
    agg = qs.aggregate(d=Sum('debit'), c=Sum('credit'))
    return (agg['d'] or Decimal('0')) - (agg['c'] or Decimal('0'))


def project_cost_total(special_project):
    agg = LedgerTransaction.objects.filter(
        special_project=special_project, is_void=False,
    ).aggregate(s=Sum('project_cost'))
    return agg['s'] or Decimal('0')


def employee_ledger_qs(employee):
    return LedgerTransaction.objects.filter(
        employee=employee, is_void=False,
    ).select_related('special_project', 'category', 'advance', 'expense')


def project_ledger_qs(special_project):
    return LedgerTransaction.objects.filter(
        special_project=special_project, is_void=False,
    ).select_related('employee', 'category', 'expense', 'fuel_transaction')


@transaction.atomic
def issue_advance(advance, user=None):
    advance.full_clean()
    if not advance.advance_number:
        advance.advance_number = allocate_advance_number()
    if user and not advance.issued_by_id:
        advance.issued_by = user
    advance.status = EmployeeAdvance.STATUS_OPEN
    advance.is_posted = True
    advance.save()
    post_ledger(
        txn_date=advance.advance_date,
        txn_type=LedgerTransaction.TYPE_ADVANCE_ISSUE,
        employee=advance.employee,
        special_project=advance.special_project,
        order=advance.order,
        debit=advance.amount,
        credit=Decimal('0.00'),
        project_cost=Decimal('0.00'),
        description=f'Advance {advance.advance_number}: {advance.purpose}',
        advance=advance,
        created_by=user,
        accounts_voucher_ref=advance.accounts_voucher_ref,
    )
    return advance


def advance_remaining(advance):
    """Unused advance balance for a specific advance document."""
    issued = LedgerTransaction.objects.filter(
        advance=advance, txn_type=LedgerTransaction.TYPE_ADVANCE_ISSUE, is_void=False,
    ).aggregate(s=Sum('debit'))['s'] or Decimal('0')
    adjusted = LedgerTransaction.objects.filter(
        advance=advance,
        txn_type__in=[
            LedgerTransaction.TYPE_ADVANCE_ADJUST,
            LedgerTransaction.TYPE_ADVANCE_SETTLE,
        ],
        is_void=False,
    ).aggregate(s=Sum('credit'))['s'] or Decimal('0')
    return issued - adjusted


@transaction.atomic
def settle_advance(advance, amount, *, user=None, remarks='', settle_date=None):
    """Employee returns unused advance cash."""
    if advance.status == EmployeeAdvance.STATUS_CLOSED:
        raise ValidationError('Advance is already closed.')
    remaining = advance_remaining(advance)
    if amount <= 0 or amount > remaining:
        raise ValidationError(f'Settlement must be between 0.01 and {remaining}.')
    post_ledger(
        txn_date=settle_date or timezone.localdate(),
        txn_type=LedgerTransaction.TYPE_ADVANCE_SETTLE,
        employee=advance.employee,
        special_project=advance.special_project,
        order=advance.order,
        debit=Decimal('0.00'),
        credit=amount,
        project_cost=Decimal('0.00'),
        description=remarks or f'Settlement of {advance.advance_number}',
        advance=advance,
        created_by=user,
    )
    if amount >= remaining:
        advance.status = EmployeeAdvance.STATUS_CLOSED
    else:
        advance.status = EmployeeAdvance.STATUS_ADJUSTED
    advance.save(update_fields=['status', 'updated_at'])
    return advance


def _post_expense_to_ledger(expense, user=None):
    if expense.is_posted:
        return
    debit = Decimal('0.00')
    credit = Decimal('0.00')
    project_cost = expense.amount
    txn_type = LedgerTransaction.TYPE_EXPENSE
    advance = None

    if expense.payment_method == ProjectExpense.PAY_ADVANCE:
        txn_type = LedgerTransaction.TYPE_ADVANCE_ADJUST
        credit = expense.amount
        advance = expense.advance
        if not advance:
            raise ValidationError({'advance': 'Select an open advance to adjust against.'})
        remaining = advance_remaining(advance)
        if expense.amount > remaining:
            raise ValidationError({
                'amount': f'Amount exceeds remaining advance balance ({remaining}).',
            })
        advance.status = EmployeeAdvance.STATUS_ADJUSTED
        advance.save(update_fields=['status', 'updated_at'])
    elif expense.payment_method == ProjectExpense.PAY_PETROL_CARD:
        txn_type = LedgerTransaction.TYPE_FLEET_FUEL_REF
        project_cost = expense.amount
        if expense.fuel_transaction_id:
            dup = ProjectExpense.objects.filter(
                fuel_transaction_id=expense.fuel_transaction_id,
                is_posted=True,
            ).exclude(pk=expense.pk).exists()
            if dup:
                raise ValidationError({
                    'fuel_transaction': 'This Fleet fuel entry is already posted in PEAMS.',
                })
    elif expense.payment_method == ProjectExpense.PAY_PERSONAL:
        project_cost = expense.amount
    else:
        project_cost = expense.amount

    post_ledger(
        txn_date=expense.expense_date,
        txn_type=txn_type,
        employee=expense.employee,
        special_project=expense.special_project,
        order=expense.order,
        category=expense.category,
        debit=debit,
        credit=credit,
        project_cost=project_cost,
        description=expense.description,
        advance=advance,
        expense=expense,
        fuel_transaction=expense.fuel_transaction,
        vendor_name=expense.vendor_name,
        gst_amount=expense.gst_amount,
        tds_amount=expense.tds_amount,
        accounts_voucher_ref=expense.accounts_voucher_ref,
        opms_activity_ref=expense.opms_activity_ref,
        created_by=user,
    )
    expense.is_posted = True
    expense.save(update_fields=['is_posted', 'updated_at'])


@transaction.atomic
def submit_expense(expense, user=None):
    expense.full_clean()
    if not expense.expense_number:
        expense.expense_number = allocate_expense_number()
    if expense.payment_method == ProjectExpense.PAY_PETROL_CARD and expense.fuel_transaction_id:
        expense.amount = expense.fuel_transaction.total_amount
    if expense.payment_method == ProjectExpense.PAY_PERSONAL:
        expense.reimbursement_status = ProjectExpense.REIMB_PENDING
    steps = resolve_approval_steps(expense.amount)
    first = steps[0] if steps else ApprovalLimit.STEP_MANAGER
    from_status = expense.status
    expense.status = _status_for_step(first)
    expense.current_step = first
    expense.submitted_at = timezone.now()
    if user and not expense.created_by_id:
        expense.created_by = user
    expense.save()
    ExpenseApprovalHistory.objects.create(
        expense=expense,
        action=ExpenseApprovalHistory.ACTION_SUBMIT,
        step_code=first,
        from_status=from_status,
        to_status=expense.status,
        acted_by=user,
        remarks='Submitted for approval',
    )
    return expense


@transaction.atomic
def approve_expense_step(expense, user, *, remarks=''):
    if expense.status in (
        ProjectExpense.STATUS_APPROVED,
        ProjectExpense.STATUS_REJECTED,
        ProjectExpense.STATUS_CLOSED,
        ProjectExpense.STATUS_PAID,
    ):
        raise ValidationError('Expense is not awaiting approval.')
    steps = resolve_approval_steps(expense.amount)
    current = expense.current_step or (
        ApprovalLimit.STEP_MANAGER
        if expense.status == ProjectExpense.STATUS_MANAGER
        else ApprovalLimit.STEP_ACCOUNTS
        if expense.status == ProjectExpense.STATUS_ACCOUNTS
        else ApprovalLimit.STEP_DIRECTOR
    )
    if current not in steps:
        steps = [current] + [s for s in steps if s != current]

    from_status = expense.status
    try:
        idx = steps.index(current)
    except ValueError:
        idx = 0
    if idx + 1 < len(steps):
        nxt = steps[idx + 1]
        expense.current_step = nxt
        expense.status = _status_for_step(nxt)
    else:
        expense.current_step = ''
        expense.status = ProjectExpense.STATUS_APPROVED
        expense.approved_at = timezone.now()
        if expense.reimbursement_status == ProjectExpense.REIMB_PENDING:
            expense.reimbursement_status = ProjectExpense.REIMB_APPROVED
        _post_expense_to_ledger(expense, user=user)

    expense.save()
    ExpenseApprovalHistory.objects.create(
        expense=expense,
        action=ExpenseApprovalHistory.ACTION_APPROVE,
        step_code=current,
        from_status=from_status,
        to_status=expense.status,
        acted_by=user,
        remarks=remarks,
    )
    return expense


@transaction.atomic
def reject_expense(expense, user, *, remarks=''):
    from_status = expense.status
    expense.status = ProjectExpense.STATUS_REJECTED
    expense.current_step = ''
    if expense.reimbursement_status == ProjectExpense.REIMB_PENDING:
        expense.reimbursement_status = ProjectExpense.REIMB_REJECTED
    expense.save()
    ExpenseApprovalHistory.objects.create(
        expense=expense,
        action=ExpenseApprovalHistory.ACTION_REJECT,
        from_status=from_status,
        to_status=expense.status,
        acted_by=user,
        remarks=remarks,
    )
    return expense


@transaction.atomic
def mark_reimbursement_paid(expense, user, *, remarks=''):
    if expense.payment_method != ProjectExpense.PAY_PERSONAL:
        raise ValidationError('Only personal-cash expenses have reimbursements.')
    if expense.status not in (ProjectExpense.STATUS_APPROVED, ProjectExpense.STATUS_PAID):
        raise ValidationError('Expense must be approved before payment.')
    from_status = expense.status
    expense.reimbursement_status = ProjectExpense.REIMB_PAID
    expense.status = ProjectExpense.STATUS_PAID
    expense.save()
    post_ledger(
        txn_date=timezone.localdate(),
        txn_type=LedgerTransaction.TYPE_REIMBURSEMENT_PAY,
        employee=expense.employee,
        special_project=expense.special_project,
        order=expense.order,
        category=expense.category,
        debit=Decimal('0.00'),
        credit=Decimal('0.00'),
        project_cost=Decimal('0.00'),
        description=f'Reimbursement paid {expense.expense_number}',
        expense=expense,
        created_by=user,
    )
    ExpenseApprovalHistory.objects.create(
        expense=expense,
        action=ExpenseApprovalHistory.ACTION_PAY,
        from_status=from_status,
        to_status=expense.status,
        acted_by=user,
        remarks=remarks,
    )
    return expense


@transaction.atomic
def sync_daily_expense_line(line, user=None):
    """
    Sync Special Project DailyExpenseLine financial total into PEAMS ledger.
    Does not replace site-diary capture — reference via daily_expense_line FK.
    """
    from django.core.exceptions import ObjectDoesNotExist
    from special_projects.models import DailyExpenseLine

    try:
        existing = line.peams_ledger
    except ObjectDoesNotExist:
        existing = None

    if line.approval_status == DailyExpenseLine.APPROVAL_REJECTED:
        if existing and not existing.is_void:
            existing.is_void = True
            existing.save(update_fields=['is_void'])
        return None

    if line.approval_status != DailyExpenseLine.APPROVAL_APPROVED:
        # Only approved diary lines hit financial ledger
        if existing and not existing.is_void:
            existing.is_void = True
            existing.save(update_fields=['is_void'])
        return existing

    project = line.daily_log.project
    cat_code = SP_EXPENSE_TO_CATEGORY.get(line.expense_type, 'MISCELLANEOUS')
    category = ExpenseCategory.objects.filter(code=cat_code, is_active=True).first()
    if not category:
        seed_default_categories()
        category = ExpenseCategory.objects.filter(code=cat_code).first()

    desc = f'SP daily expense: {line.get_expense_type_display()}'
    if line.remarks:
        desc = f'{desc} — {line.remarks}'[:255]

    if existing:
        existing.is_void = False
        existing.txn_date = line.daily_log.log_date
        existing.special_project = project
        existing.order = project.order
        existing.category = category
        existing.project_cost = line.amount
        existing.debit = Decimal('0.00')
        existing.credit = Decimal('0.00')
        existing.description = desc
        existing.save()
        return existing

    return post_ledger(
        txn_date=line.daily_log.log_date,
        txn_type=LedgerTransaction.TYPE_SP_DAILY_SYNC,
        employee=line.daily_log.mentor,
        special_project=project,
        order=project.order,
        category=category,
        debit=Decimal('0.00'),
        credit=Decimal('0.00'),
        project_cost=line.amount or Decimal('0.00'),
        description=desc,
        daily_expense_line=line,
        created_by=user,
    )


def sync_daily_log_expenses(daily_log, user=None):
    for line in daily_log.expenses.all():
        sync_daily_expense_line(line, user=user)


def dashboard_stats(user=None):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    led = LedgerTransaction.objects.filter(is_void=False)
    today_cost = led.filter(txn_date=today).aggregate(s=Sum('project_cost'))['s'] or Decimal('0')
    month_cost = led.filter(txn_date__gte=month_start).aggregate(s=Sum('project_cost'))['s'] or Decimal('0')
    pending = ProjectExpense.objects.filter(
        status__in=[
            ProjectExpense.STATUS_SUBMITTED,
            ProjectExpense.STATUS_MANAGER,
            ProjectExpense.STATUS_ACCOUNTS,
            ProjectExpense.STATUS_DIRECTOR,
        ],
    ).count()
    open_advances = EmployeeAdvance.objects.filter(
        status__in=[EmployeeAdvance.STATUS_OPEN, EmployeeAdvance.STATUS_ADJUSTED],
    ).count()
    pending_reimb = ProjectExpense.objects.filter(
        reimbursement_status=ProjectExpense.REIMB_PENDING,
    ).count()
    by_category = (
        led.exclude(category__isnull=True)
        .values('category__name')
        .annotate(total=Sum('project_cost'))
        .order_by('-total')[:10]
    )
    return {
        'today_cost': today_cost,
        'month_cost': month_cost,
        'pending_approvals': pending,
        'open_advances': open_advances,
        'pending_reimbursements': pending_reimb,
        'by_category': by_category,
        'director_threshold': PeamsSettings.get_solo().director_approval_threshold,
    }
