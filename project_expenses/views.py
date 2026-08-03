from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import module_required
from special_projects.models import SpecialProject

from .forms import (
    AdvanceSettleForm,
    ApprovalLimitForm,
    EmployeeAdvanceForm,
    ExpenseActionForm,
    ExpenseCategoryForm,
    PeamsSettingsForm,
    ProjectExpenseForm,
)
from .models import (
    ApprovalLimit,
    EmployeeAdvance,
    ExpenseCategory,
    LedgerTransaction,
    PeamsSettings,
    ProjectExpense,
)
from .permissions import (
    MODULE_PEAMS,
    can_approve_expense,
    can_create_expense,
    can_manage_peams,
    can_view_peams,
)
from .services import (
    allocate_expense_number,
    approve_expense_step,
    dashboard_stats,
    employee_advance_balance,
    employee_ledger_qs,
    issue_advance,
    mark_reimbursement_paid,
    project_cost_total,
    project_ledger_qs,
    reject_expense,
    resolve_approval_steps,
    seed_default_approval_limits,
    seed_default_categories,
    settle_advance,
    submit_expense,
)


@module_required(MODULE_PEAMS)
def peams_dashboard(request):
    if not can_view_peams(request.user):
        messages.error(request, 'Access denied.')
        return redirect('login')
    seed_default_categories()
    seed_default_approval_limits()
    stats = dashboard_stats(request.user)
    # Budget vs actual for top projects with budget
    projects = []
    for p in SpecialProject.objects.filter(budget__gt=0).order_by('-pk')[:8]:
        actual = project_cost_total(p)
        projects.append({
            'project': p,
            'budget': p.budget,
            'actual': actual,
            'remaining': p.budget - actual,
        })
    return render(request, 'project_expenses/dashboard.html', {
        'stats': stats,
        'budget_rows': projects,
        'can_manage': can_manage_peams(request.user),
        'can_create': can_create_expense(request.user),
    })


@module_required(MODULE_PEAMS)
def category_list(request):
    seed_default_categories()
    return render(request, 'project_expenses/category_list.html', {
        'categories': ExpenseCategory.objects.all(),
        'can_manage': can_manage_peams(request.user),
    })


@module_required(MODULE_PEAMS)
def category_create(request):
    if not can_manage_peams(request.user):
        messages.error(request, 'Managers/accounts only.')
        return redirect('peams_category_list')
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category saved.')
            return redirect('peams_category_list')
    else:
        form = ExpenseCategoryForm()
    return render(request, 'project_expenses/category_form.html', {
        'form': form, 'title': 'Add Expense Category',
    })


@module_required(MODULE_PEAMS)
def settings_view(request):
    if not can_manage_peams(request.user):
        messages.error(request, 'Managers/accounts only.')
        return redirect('peams_dashboard')
    seed_default_approval_limits()
    settings_obj = PeamsSettings.get_solo()
    if request.method == 'POST' and 'save_settings' in request.POST:
        sform = PeamsSettingsForm(request.POST, instance=settings_obj)
        if sform.is_valid():
            sform.save()
            messages.success(request, 'Settings updated.')
            return redirect('peams_settings')
    else:
        sform = PeamsSettingsForm(instance=settings_obj)

    if request.method == 'POST' and 'add_limit' in request.POST:
        lform = ApprovalLimitForm(request.POST)
        if lform.is_valid():
            lform.save()
            messages.success(request, 'Approval limit added.')
            return redirect('peams_settings')
    else:
        lform = ApprovalLimitForm()

    return render(request, 'project_expenses/settings.html', {
        'settings_form': sform,
        'limit_form': lform,
        'limits': ApprovalLimit.objects.all(),
    })


@module_required(MODULE_PEAMS)
def advance_list(request):
    qs = EmployeeAdvance.objects.select_related(
        'employee', 'special_project', 'order', 'issued_by',
    )
    if not can_manage_peams(request.user):
        qs = qs.filter(employee=request.user)
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)
    return render(request, 'project_expenses/advance_list.html', {
        'advances': qs[:200],
        'can_manage': can_manage_peams(request.user),
        'status_filter': status,
    })


@module_required(MODULE_PEAMS)
def advance_create(request):
    if not can_manage_peams(request.user):
        messages.error(request, 'Only managers/accounts can issue advances.')
        return redirect('peams_advance_list')
    if request.method == 'POST':
        form = EmployeeAdvanceForm(request.POST)
        if form.is_valid():
            adv = form.save(commit=False)
            try:
                issue_advance(adv, user=request.user)
                messages.success(request, f'Advance {adv.advance_number} issued and posted to ledger.')
                return redirect('peams_advance_detail', pk=adv.pk)
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = EmployeeAdvanceForm(initial={'advance_date': timezone.localdate()})
    return render(request, 'project_expenses/advance_form.html', {
        'form': form, 'title': 'Issue Advance',
    })


@module_required(MODULE_PEAMS)
def advance_detail(request, pk):
    adv = get_object_or_404(
        EmployeeAdvance.objects.select_related('employee', 'special_project', 'order'),
        pk=pk,
    )
    if not can_manage_peams(request.user) and adv.employee_id != request.user.pk:
        messages.error(request, 'Access denied.')
        return redirect('peams_advance_list')
    settle_form = AdvanceSettleForm()
    if request.method == 'POST' and can_manage_peams(request.user):
        settle_form = AdvanceSettleForm(request.POST)
        if settle_form.is_valid():
            try:
                settle_advance(
                    adv,
                    settle_form.cleaned_data['amount'],
                    user=request.user,
                    remarks=settle_form.cleaned_data.get('remarks', ''),
                )
                messages.success(request, 'Settlement posted.')
                return redirect('peams_advance_detail', pk=pk)
            except ValidationError as e:
                messages.error(request, e.messages[0] if hasattr(e, 'messages') else str(e))
    entries = LedgerTransaction.objects.filter(advance=adv, is_void=False)
    return render(request, 'project_expenses/advance_detail.html', {
        'advance': adv,
        'entries': entries,
        'employee_balance': employee_advance_balance(adv.employee),
        'settle_form': settle_form,
        'can_manage': can_manage_peams(request.user),
    })


@module_required(MODULE_PEAMS)
def expense_list(request):
    qs = ProjectExpense.objects.select_related(
        'employee', 'category', 'special_project', 'order',
    )
    if not can_manage_peams(request.user):
        qs = qs.filter(Q(employee=request.user) | Q(created_by=request.user))
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)
    return render(request, 'project_expenses/expense_list.html', {
        'expenses': qs[:200],
        'can_create': can_create_expense(request.user),
        'can_manage': can_manage_peams(request.user),
        'status_filter': status,
    })


@module_required(MODULE_PEAMS)
def expense_create(request):
    if not can_create_expense(request.user):
        messages.error(request, 'You cannot create expenses.')
        return redirect('peams_expense_list')
    seed_default_categories()
    if request.method == 'POST':
        form = ProjectExpenseForm(request.POST, request.FILES, user=request.user)
        action = request.POST.get('action', 'draft')
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            if not can_manage_peams(request.user):
                expense.employee = request.user
            if not expense.expense_number:
                expense.expense_number = allocate_expense_number()
            if expense.payment_method == ProjectExpense.PAY_PERSONAL:
                expense.reimbursement_status = ''
            expense.status = ProjectExpense.STATUS_DRAFT
            expense.save()
            if action == 'submit':
                try:
                    submit_expense(expense, user=request.user)
                    messages.success(
                        request,
                        f'{expense.expense_number} submitted. Steps: '
                        f'{", ".join(resolve_approval_steps(expense.amount))}.',
                    )
                except ValidationError as e:
                    messages.error(request, str(e))
                    return redirect('peams_expense_detail', pk=expense.pk)
            else:
                messages.success(request, f'Draft {expense.expense_number} saved.')
            return redirect('peams_expense_detail', pk=expense.pk)
    else:
        form = ProjectExpenseForm(user=request.user, initial={'expense_date': timezone.localdate()})
    return render(request, 'project_expenses/expense_form.html', {
        'form': form, 'title': 'New Project Expense',
    })


@module_required(MODULE_PEAMS)
def expense_detail(request, pk):
    expense = get_object_or_404(
        ProjectExpense.objects.select_related(
            'employee', 'category', 'special_project', 'order',
            'advance', 'fuel_transaction', 'fuel_transaction__vehicle', 'created_by',
        ),
        pk=pk,
    )
    if (
        not can_manage_peams(request.user)
        and expense.employee_id != request.user.pk
        and expense.created_by_id != request.user.pk
        and not can_approve_expense(request.user, expense)
    ):
        messages.error(request, 'Access denied.')
        return redirect('peams_expense_list')

    action_form = ExpenseActionForm()
    if request.method == 'POST':
        action = request.POST.get('action')
        action_form = ExpenseActionForm(request.POST)
        remarks = action_form.cleaned_data.get('remarks', '') if action_form.is_valid() else ''
        try:
            if action == 'submit' and expense.status == ProjectExpense.STATUS_DRAFT:
                if expense.employee_id == request.user.pk or can_manage_peams(request.user):
                    submit_expense(expense, user=request.user)
                    messages.success(request, 'Submitted for approval.')
            elif action == 'approve' and can_approve_expense(request.user, expense):
                approve_expense_step(expense, request.user, remarks=remarks)
                messages.success(request, f'Status: {expense.get_status_display()}.')
            elif action == 'reject' and can_approve_expense(request.user, expense):
                reject_expense(expense, request.user, remarks=remarks)
                messages.success(request, 'Expense rejected.')
            elif action == 'pay' and can_manage_peams(request.user):
                mark_reimbursement_paid(expense, request.user, remarks=remarks)
                messages.success(request, 'Reimbursement marked paid.')
            else:
                messages.error(request, 'Action not allowed.')
        except ValidationError as e:
            messages.error(request, e.messages[0] if hasattr(e, 'messages') else str(e))
        return redirect('peams_expense_detail', pk=pk)

    return render(request, 'project_expenses/expense_detail.html', {
        'expense': expense,
        'approvals': expense.approvals.select_related('acted_by'),
        'ledger': expense.ledger_entries.filter(is_void=False),
        'can_approve': can_approve_expense(request.user, expense),
        'can_manage': can_manage_peams(request.user),
        'can_submit': expense.status == ProjectExpense.STATUS_DRAFT and (
            expense.employee_id == request.user.pk or can_manage_peams(request.user)
        ),
        'approval_steps': resolve_approval_steps(expense.amount),
        'action_form': action_form,
    })


@module_required(MODULE_PEAMS)
def pending_approvals(request):
    qs = ProjectExpense.objects.filter(
        status__in=[
            ProjectExpense.STATUS_MANAGER,
            ProjectExpense.STATUS_ACCOUNTS,
            ProjectExpense.STATUS_DIRECTOR,
        ],
    ).select_related('employee', 'category', 'special_project')
    # Filter to steps user can approve
    visible = [e for e in qs[:300] if can_approve_expense(request.user, e)]
    return render(request, 'project_expenses/pending_approvals.html', {
        'expenses': visible,
    })


@module_required(MODULE_PEAMS)
def employee_ledger(request):
    User = get_user_model()
    emp_id = request.GET.get('employee')
    if can_manage_peams(request.user) and emp_id:
        employee = get_object_or_404(User, pk=emp_id)
    else:
        employee = request.user
    entries = list(employee_ledger_qs(employee)[:300])
    running = Decimal('0')
    rows = []
    for e in entries:
        running = running + e.debit - e.credit
        rows.append({'entry': e, 'balance': running})
    return render(request, 'project_expenses/employee_ledger.html', {
        'employee': employee,
        'rows': rows,
        'balance': employee_advance_balance(employee),
        'employees': User.objects.filter(is_active=True).order_by('first_name', 'username')
        if can_manage_peams(request.user) else None,
    })


@module_required(MODULE_PEAMS)
def project_ledger(request):
    project_id = request.GET.get('project')
    project = None
    rows = []
    total = None
    remaining = None
    if project_id:
        project = get_object_or_404(SpecialProject.objects.select_related('order'), pk=project_id)
        entries = project_ledger_qs(project)[:300]
        total = project_cost_total(project)
        remaining = (project.budget or Decimal('0')) - total
        rows = entries
    return render(request, 'project_expenses/project_ledger.html', {
        'project': project,
        'rows': rows,
        'total': total,
        'budget': project.budget if project else None,
        'remaining': remaining,
        'projects': SpecialProject.objects.select_related('order').order_by('-pk')[:200],
    })
