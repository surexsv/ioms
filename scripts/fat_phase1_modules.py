"""
IOMS FAT — Phase 1 Ops Modules (next-level)
Covers: Fleet & Fuel, PEAMS (Project Expenses), Special Projects
Focus: RBAC, audit fixes, ledger integrity, approval workflow

Does not delete production data. Uses FAT-tagged sample records.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from decimal import Decimal
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client as HttpClient
from django.urls import reverse
from django.utils import timezone

from fleet.forms import FuelTransactionForm
from fleet.models import FuelTransaction, PetrolCard, PettyCashAccount, Vehicle
from fleet.services import recharge_petrol_card, save_fuel_transaction, topup_petty_cash
from project_expenses.forms import ProjectExpenseForm
from project_expenses.models import EmployeeAdvance, ExpenseCategory, LedgerTransaction, ProjectExpense
from project_expenses.services import (
    advance_remaining,
    approve_expense_step,
    employee_advance_balance,
    issue_advance,
    project_cost_total,
    reject_expense,
    resolve_approval_steps,
    seed_default_approval_limits,
    seed_default_categories,
    submit_expense,
    sync_daily_expense_line,
)
from special_projects.forms import expense_formset_for_user
from special_projects.models import DailyExpenseLine, ProjectDailyLog, SpecialProject
from special_projects.views import _projects_for_user

User = get_user_model()
RESULTS = []
FAT_TAG = 'FAT-P1'


def record(step, case, status, detail='', evidence=''):
    RESULTS.append({
        'step': step, 'case': case, 'status': status,
        'detail': detail, 'evidence': evidence,
    })
    line = f'[{status}] {step} | {case}: {detail}'
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', 'replace').decode('ascii'))


def client():
    return HttpClient(HTTP_HOST='127.0.0.1')


def users():
    return {
        'director': User.objects.filter(username='surex').first()
        or User.objects.filter(role='DIRECTOR', is_active=True).first(),
        'accounts': User.objects.filter(username='Maya').first()
        or User.objects.filter(role='ACCOUNTS', is_active=True).first(),
        'pm': User.objects.filter(username='Jayan').first()
        or User.objects.filter(role='PROJECT_MANAGER', is_active=True).first(),
        'tech': User.objects.filter(username='Tech1').first()
        or User.objects.filter(role='Technician', is_active=True).first(),
        'engineer': User.objects.filter(username='Vishnu').first()
        or User.objects.filter(role='ENGINEER', is_active=True).first(),
    }


def http_get(user, url_name, expect=200, **kwargs):
    c = client()
    c.force_login(user)
    try:
        url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
        r = c.get(url)
        ok = r.status_code == expect
        record(
            'HTTP', f'{user.username} GET {url_name}',
            'PASS' if ok else 'FAIL',
            f'status={r.status_code} expected={expect}',
            url,
        )
        return r
    except Exception as e:
        record('HTTP', f'{user.username} GET {url_name}', 'FAIL', str(e))
        return None


def run():
    seed_default_categories()
    seed_default_approval_limits()
    u = users()
    for key in ('director', 'tech', 'accounts', 'pm'):
        if not u.get(key):
            record('SETUP', f'user:{key}', 'FAIL', 'User missing')
            return
        record('SETUP', f'user:{key}', 'PASS', f'{u[key].username} role={u[key].role}')

    director, tech, accounts, pm = u['director'], u['tech'], u['accounts'], u['pm']

    # --- HTTP surface (roles) ---
    for name in [
        'peams_dashboard', 'peams_expense_create', 'peams_expense_list',
        'peams_advance_list', 'peams_employee_ledger', 'peams_pending_approvals',
        'fleet_dashboard', 'fleet_fuel_create', 'fleet_fuel_list', 'fleet_vehicle_list',
        'special_project_list',
    ]:
        http_get(tech, name, 200)
        http_get(director, name, 200)

    # Tech blocked from manage pages (redirect 302)
    http_get(tech, 'fleet_petty_cash', 302)
    http_get(tech, 'fleet_reimbursement_list', 302)
    http_get(tech, 'peams_settings', 302)
    http_get(tech, 'peams_advance_create', 302)
    http_get(director, 'fleet_petty_cash', 200)
    http_get(director, 'peams_settings', 200)
    http_get(director, 'peams_advance_create', 200)

    # --- Form RBAC / audit fixes ---
    f_tech = ProjectExpenseForm(user=tech)
    if f_tech.fields['employee'].queryset.count() == 1 and f_tech.fields['employee'].queryset.first().pk == tech.pk:
        record('RBAC', 'PEAMS tech employee lock', 'PASS', 'employee queryset = self')
    else:
        record('RBAC', 'PEAMS tech employee lock', 'FAIL',
               f'count={f_tech.fields["employee"].queryset.count()}')

    f_dir = ProjectExpenseForm(user=director)
    if f_dir.fields['employee'].queryset.count() > 1:
        record('RBAC', 'PEAMS director employee list', 'PASS',
               f'count={f_dir.fields["employee"].queryset.count()}')
    else:
        record('RBAC', 'PEAMS director employee list', 'FAIL', 'expected multiple')

    ff_tech = FuelTransactionForm(user=tech)
    pay = dict(ff_tech.fields['payment_method'].choices)
    if FuelTransaction.PAY_PETTY not in pay and ff_tech.fields['driver'].queryset.count() == 1:
        record('RBAC', 'Fleet tech no petty + driver lock', 'PASS', str(list(pay.keys())))
    else:
        record('RBAC', 'Fleet tech no petty + driver lock', 'FAIL', str(list(pay.keys())))

    efs_tech = expense_formset_for_user(tech, prefix='expense')
    efs_dir = expense_formset_for_user(director, prefix='expense')
    tech_has_appr = 'approval_status' in efs_tech.forms[0].fields
    dir_has_appr = 'approval_status' in efs_dir.forms[0].fields
    if (not tech_has_appr) and dir_has_appr:
        record('RBAC', 'SP diary approval_status field', 'PASS', 'tech hidden, manager visible')
    else:
        record('RBAC', 'SP diary approval_status field', 'FAIL',
               f'tech={tech_has_appr} dir={dir_has_appr}')

    # Order PK safety
    order_qs = f_tech.fields['order'].queryset
    if list(order_qs.query.order_by) == ['-order_id']:
        record('AUDIT', 'Order order_by order_id', 'PASS')
    else:
        record('AUDIT', 'Order order_by order_id', 'FAIL', str(order_qs.query.order_by))

    # Approval chain config
    low = resolve_approval_steps(Decimal('500'))
    high = resolve_approval_steps(Decimal('15000'))
    if low == ['MANAGER', 'ACCOUNTS'] and 'DIRECTOR' in high:
        record('PEAMS', 'approval steps by amount', 'PASS', f'low={low} high={high}')
    else:
        record('PEAMS', 'approval steps by amount', 'FAIL', f'low={low} high={high}')

    # --- Fleet workflow ---
    try:
        with transaction.atomic():
            v, _ = Vehicle.objects.get_or_create(
                vehicle_number='FAT-P1-MH01',
                defaults={
                    'vehicle_type': Vehicle.TYPE_FOUR_WHEELER,
                    'fuel_type': Vehicle.FUEL_PETROL,
                    'last_odometer_km': Decimal('5000'),
                    'assigned_employee': tech,
                    'status': Vehicle.STATUS_ACTIVE,
                },
            )
            card, _ = PetrolCard.objects.get_or_create(
                card_number='FAT-P1-CARD',
                defaults={'card_name': 'FAT Card', 'vehicle': v, 'current_balance': Decimal('0')},
            )
            if card.current_balance < 3000:
                recharge_petrol_card(card, amount=Decimal('3000'), user=director, reference=FAT_TAG)
                card.refresh_from_db()
            acct = PettyCashAccount.get_default()
            if acct.current_balance < 1000:
                topup_petty_cash(amount=Decimal('2000'), user=director, reference=FAT_TAG)
                acct.refresh_from_db()

            # Tech cash fuel OK
            prev = v.last_odometer_km
            fuel_cash = FuelTransaction(
                driver=tech, vehicle=v,
                previous_odometer_km=prev,
                current_odometer_km=prev + Decimal('50'),
                fuel_quantity_litres=Decimal('5'),
                fuel_rate=Decimal('100'),
                payment_method=FuelTransaction.PAY_CASH,
                remarks=FAT_TAG,
            )
            save_fuel_transaction(fuel_cash, user=tech, is_new=True)
            if fuel_cash.reimbursement_status == FuelTransaction.REIMB_PENDING and fuel_cash.distance_km == 50:
                record('FLEET', 'tech cash fuel + reimb pending', 'PASS',
                       f'pk={fuel_cash.pk} amt={fuel_cash.total_amount}')
            else:
                record('FLEET', 'tech cash fuel + reimb pending', 'FAIL',
                       f'reimb={fuel_cash.reimbursement_status} dist={fuel_cash.distance_km}')

            # Card fuel
            v.refresh_from_db()
            bal_before = card.current_balance
            fuel_card = FuelTransaction(
                driver=tech, vehicle=v,
                previous_odometer_km=v.last_odometer_km,
                current_odometer_km=v.last_odometer_km + Decimal('40'),
                fuel_quantity_litres=Decimal('4'),
                fuel_rate=Decimal('100'),
                payment_method=FuelTransaction.PAY_CARD,
                petrol_card=card,
                remarks=FAT_TAG,
            )
            save_fuel_transaction(fuel_card, user=tech, is_new=True)
            card.refresh_from_db()
            if card.current_balance == bal_before - fuel_card.total_amount:
                record('FLEET', 'card fuel deducts balance', 'PASS',
                       f'{bal_before} -> {card.current_balance}')
            else:
                record('FLEET', 'card fuel deducts balance', 'FAIL',
                       f'{bal_before} -> {card.current_balance} amt={fuel_card.total_amount}')

            # Tech cannot use petty (form validation)
            bad = FuelTransactionForm(
                data={
                    'transaction_date': str(timezone.localdate()),
                    'driver': tech.pk,
                    'vehicle': v.pk,
                    'previous_odometer_km': str(v.last_odometer_km),
                    'current_odometer_km': str(v.last_odometer_km + 10),
                    'fuel_quantity_litres': '1',
                    'fuel_rate': '100',
                    'payment_method': FuelTransaction.PAY_PETTY,
                },
                user=tech,
            )
            if not bad.is_valid() and 'payment_method' in bad.errors:
                record('FLEET', 'tech petty cash blocked', 'PASS', str(bad.errors['payment_method']))
            else:
                record('FLEET', 'tech petty cash blocked', 'FAIL', f'valid={bad.is_valid()} errors={bad.errors}')

            # Fuel detail IDOR: tech cannot open director-owned foreign fuel if other driver
            c = client()
            c.force_login(tech)
            other = FuelTransaction.objects.exclude(driver=tech).exclude(created_by=tech).first()
            if other:
                r = c.get(reverse('fleet_fuel_detail', args=[other.pk]))
                # redirect to list
                if r.status_code in (302, 403):
                    record('FLEET', 'fuel detail IDOR blocked', 'PASS', f'status={r.status_code}')
                elif r.status_code == 200:
                    record('FLEET', 'fuel detail IDOR blocked', 'FAIL', 'tech saw other fuel')
                else:
                    record('FLEET', 'fuel detail IDOR blocked', 'WARNING', f'status={r.status_code}')
            else:
                record('FLEET', 'fuel detail IDOR blocked', 'WARNING', 'no other-driver fuel to test')

            # --- PEAMS advance + expense against advance ---
            adv = EmployeeAdvance(
                employee=tech, purpose=f'{FAT_TAG} site cash', amount=Decimal('2000'),
            )
            issue_advance(adv, user=director)
            bal1 = employee_advance_balance(tech)
            rem1 = advance_remaining(adv)
            if rem1 == Decimal('2000') and bal1 >= Decimal('2000'):
                record('PEAMS', 'advance issue ledger', 'PASS',
                       f'{adv.advance_number} rem={rem1} emp_bal={bal1}')
            else:
                record('PEAMS', 'advance issue ledger', 'FAIL', f'rem={rem1} bal={bal1}')

            cat = ExpenseCategory.objects.get(code='FOOD')
            sp = SpecialProject.objects.order_by('-pk').first()
            exp = ProjectExpense(
                employee=tech, category=cat, amount=Decimal('350'),
                payment_method=ProjectExpense.PAY_ADVANCE, advance=adv,
                description=f'{FAT_TAG} meals', special_project=sp,
                created_by=tech, status=ProjectExpense.STATUS_DRAFT,
            )
            from project_expenses.services import allocate_expense_number
            exp.expense_number = allocate_expense_number()
            exp.save()
            submit_expense(exp, user=tech)
            # Manager then Accounts
            while exp.status not in (
                ProjectExpense.STATUS_APPROVED, ProjectExpense.STATUS_REJECTED,
            ):
                actor = pm if exp.current_step == 'MANAGER' else (
                    accounts if exp.current_step == 'ACCOUNTS' else director
                )
                approve_expense_step(exp, actor, remarks=FAT_TAG)
                exp.refresh_from_db()
            rem2 = advance_remaining(adv)
            if exp.is_posted and rem2 == Decimal('1650'):
                record('PEAMS', 'expense vs advance posted', 'PASS',
                       f'{exp.expense_number} rem={rem2} status={exp.status}')
            else:
                record('PEAMS', 'expense vs advance posted', 'FAIL',
                       f'posted={exp.is_posted} rem={rem2} status={exp.status}')

            # Overdraw blocked at final approval
            exp2 = ProjectExpense(
                employee=tech, category=cat, amount=Decimal('5000'),
                payment_method=ProjectExpense.PAY_ADVANCE, advance=adv,
                description=f'{FAT_TAG} overdraw', created_by=tech,
                status=ProjectExpense.STATUS_DRAFT,
            )
            exp2.expense_number = allocate_expense_number()
            exp2.save()
            submit_expense(exp2, user=tech)
            overdraw_blocked = False
            try:
                while exp2.status not in (
                    ProjectExpense.STATUS_APPROVED, ProjectExpense.STATUS_REJECTED,
                ):
                    actor = pm if exp2.current_step == 'MANAGER' else (
                        accounts if exp2.current_step == 'ACCOUNTS' else director
                    )
                    approve_expense_step(exp2, actor, remarks=FAT_TAG)
                    exp2.refresh_from_db()
            except Exception as e:
                overdraw_blocked = True
                record('PEAMS', 'advance overdraw blocked', 'PASS', str(e)[:160])
            exp2.refresh_from_db()
            if not overdraw_blocked:
                if not exp2.is_posted:
                    record('PEAMS', 'advance overdraw blocked', 'PASS', 'not posted')
                else:
                    record('PEAMS', 'advance overdraw blocked', 'FAIL', 'overdraw was posted')

            # Reject path
            exp3 = ProjectExpense(
                employee=tech, category=cat, amount=Decimal('100'),
                payment_method=ProjectExpense.PAY_PERSONAL,
                description=f'{FAT_TAG} reject me', created_by=tech,
                status=ProjectExpense.STATUS_DRAFT,
            )
            exp3.expense_number = allocate_expense_number()
            exp3.save()
            submit_expense(exp3, user=tech)
            reject_expense(exp3, pm, remarks='FAT reject')
            exp3.refresh_from_db()
            if exp3.status == ProjectExpense.STATUS_REJECTED and not exp3.is_posted:
                record('PEAMS', 'reject does not post ledger', 'PASS', exp3.expense_number)
            else:
                record('PEAMS', 'reject does not post ledger', 'FAIL',
                       f'{exp3.status} posted={exp3.is_posted}')

            # Fuel double-link blocked
            form_dup = ProjectExpenseForm(
                data={
                    'expense_date': str(timezone.localdate()),
                    'employee': tech.pk,
                    'category': cat.pk,
                    'amount': str(fuel_card.total_amount),
                    'payment_method': ProjectExpense.PAY_PETROL_CARD,
                    'fuel_transaction': fuel_card.pk,
                    'description': f'{FAT_TAG} fuel link 1',
                },
                user=director,
            )
            # First link draft then submit/approve to post — use service path
            exp_fuel = ProjectExpense(
                employee=tech, category=ExpenseCategory.objects.filter(code='FUEL').first() or cat,
                amount=fuel_card.total_amount,
                payment_method=ProjectExpense.PAY_PETROL_CARD,
                fuel_transaction=fuel_card,
                description=f'{FAT_TAG} fleet ref',
                created_by=director,
                status=ProjectExpense.STATUS_DRAFT,
            )
            exp_fuel.expense_number = allocate_expense_number()
            exp_fuel.save()
            submit_expense(exp_fuel, user=director)
            while exp_fuel.status not in (
                ProjectExpense.STATUS_APPROVED, ProjectExpense.STATUS_REJECTED,
            ):
                actor = pm if exp_fuel.current_step == 'MANAGER' else (
                    accounts if exp_fuel.current_step == 'ACCOUNTS' else director
                )
                approve_expense_step(exp_fuel, actor, remarks=FAT_TAG)
                exp_fuel.refresh_from_db()

            form_dup2 = ProjectExpenseForm(
                data={
                    'expense_date': str(timezone.localdate()),
                    'employee': tech.pk,
                    'category': cat.pk,
                    'amount': str(fuel_card.total_amount),
                    'payment_method': ProjectExpense.PAY_PETROL_CARD,
                    'fuel_transaction': fuel_card.pk,
                    'description': f'{FAT_TAG} fuel link DUP',
                },
                user=director,
            )
            if not form_dup2.is_valid() and 'fuel_transaction' in form_dup2.errors:
                record('PEAMS', 'duplicate fleet fuel link blocked', 'PASS',
                       str(form_dup2.errors['fuel_transaction']))
            else:
                # may still be draft-only first; check after first posted
                if exp_fuel.is_posted:
                    record('PEAMS', 'duplicate fleet fuel link blocked', 'FAIL',
                           f'valid={form_dup2.is_valid()} err={form_dup2.errors}')
                else:
                    record('PEAMS', 'duplicate fleet fuel link blocked', 'WARNING',
                           'first fuel expense not posted')

            # --- SP sync ---
            if sp:
                log = ProjectDailyLog.objects.filter(project=sp).order_by('-pk').first()
                if not log:
                    log = ProjectDailyLog.objects.create(
                        project=sp, log_date=timezone.localdate(),
                        work_description=FAT_TAG, mentor=pm, created_by=director,
                    )
                line = DailyExpenseLine.objects.create(
                    daily_log=log, expense_type='FOOD', amount=Decimal('125'),
                    approval_status=DailyExpenseLine.APPROVAL_PENDING,
                    remarks=FAT_TAG,
                )
                sync_daily_expense_line(line)
                has_pending_ledger = LedgerTransaction.objects.filter(
                    daily_expense_line=line, is_void=False,
                ).exists()
                if not has_pending_ledger:
                    record('PEAMS', 'SP pending expense not in ledger', 'PASS')
                else:
                    record('PEAMS', 'SP pending expense not in ledger', 'FAIL')

                line.approval_status = DailyExpenseLine.APPROVAL_APPROVED
                line.save()
                sync_daily_expense_line(line)
                led = LedgerTransaction.objects.filter(
                    daily_expense_line=line, is_void=False,
                    txn_type=LedgerTransaction.TYPE_SP_DAILY_SYNC,
                ).first()
                if led and led.project_cost == Decimal('125'):
                    record('PEAMS', 'SP approved expense syncs ledger', 'PASS', led.txn_number)
                else:
                    record('PEAMS', 'SP approved expense syncs ledger', 'FAIL')

                # pre_delete void
                txn_id = led.pk if led else None
                line_pk = line.pk
                line.delete()
                if txn_id:
                    voided = LedgerTransaction.objects.filter(pk=txn_id, is_void=True).exists()
                    still_linked = LedgerTransaction.objects.filter(
                        daily_expense_line_id=line_pk, is_void=False,
                    ).exists()
                    if voided and not still_linked:
                        record('PEAMS', 'SP delete voids ledger (pre_delete)', 'PASS')
                    else:
                        record('PEAMS', 'SP delete voids ledger (pre_delete)', 'FAIL',
                               f'voided={voided} active_link={still_linked}')

                # Project access helper
                tech_projects = list(_projects_for_user(tech).values_list('pk', flat=True)[:50])
                dir_projects = list(_projects_for_user(director).values_list('pk', flat=True)[:50])
                if len(dir_projects) >= len(tech_projects):
                    record('SP', 'project queryset scoped by role', 'PASS',
                           f'tech={len(tech_projects)} dir={len(dir_projects)}')
                else:
                    record('SP', 'project queryset scoped by role', 'FAIL')
            else:
                record('PEAMS', 'SP sync suite', 'WARNING', 'No Special Project in DB')

            # Force rollback of FAT transactional writes? Keep them — tagged FAT-P1 for review.
            record('SETUP', 'FAT data retained', 'PASS',
                   'Vehicle FAT-P1-MH01, card FAT-P1-CARD, tagged advances/expenses')

    except Exception as e:
        record('SUITE', 'exception', 'FAIL', f'{e}\n{traceback.format_exc()[:800]}')

    # Summary
    counts = {}
    for r in RESULTS:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    record('SUMMARY', 'totals', 'PASS' if counts.get('FAIL', 0) == 0 else 'FAIL', str(counts))

    out = Path(__file__).resolve().parents[1] / 'docs' / 'FAT_PHASE1_MODULES_RESULTS.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        'generated_at': timezone.now().isoformat(),
        'counts': counts,
        'results': RESULTS,
    }, indent=2), encoding='utf-8')
    print(f'\nWrote {out}')
    print('COUNTS:', counts)
    return counts.get('FAIL', 0) == 0


if __name__ == '__main__':
    ok = run()
    sys.exit(0 if ok else 1)
