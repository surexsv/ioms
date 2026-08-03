import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import module_required

from .forms import (
    CardRechargeForm,
    FuelTransactionForm,
    PetrolCardForm,
    PettyCashTopupForm,
    VehicleForm,
)
from .models import FuelTransaction, PetrolCard, PettyCashAccount, PettyCashLedger, Vehicle
from .permissions import (
    MODULE_FLEET,
    can_create_fuel_entry,
    can_edit_fuel_entry,
    can_manage_fleet,
    can_view_fleet,
)
from .services import (
    dashboard_stats,
    previous_odometer_for_vehicle,
    recharge_petrol_card,
    save_fuel_transaction,
    topup_petty_cash,
)


def _require_view(user):
    return can_view_fleet(user)


@module_required(MODULE_FLEET)
def fleet_dashboard(request):
    if not _require_view(request.user):
        messages.error(request, 'Access denied.')
        return redirect('login')
    return render(request, 'fleet/dashboard.html', {
        'stats': dashboard_stats(),
        'can_manage': can_manage_fleet(request.user),
        'can_create': can_create_fuel_entry(request.user),
    })


@module_required(MODULE_FLEET)
def vehicle_list(request):
    vehicles = Vehicle.objects.select_related('assigned_employee').all()
    status = request.GET.get('status', '').strip()
    if status:
        vehicles = vehicles.filter(status=status)
    return render(request, 'fleet/vehicle_list.html', {
        'vehicles': vehicles,
        'can_manage': can_manage_fleet(request.user),
        'status_filter': status,
    })


@module_required(MODULE_FLEET)
def vehicle_create(request):
    if not can_manage_fleet(request.user):
        messages.error(request, 'Only managers/accounts can add vehicles.')
        return redirect('fleet_vehicle_list')
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle saved.')
            return redirect('fleet_vehicle_list')
    else:
        form = VehicleForm()
    return render(request, 'fleet/vehicle_form.html', {'form': form, 'title': 'Add Vehicle'})


@module_required(MODULE_FLEET)
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if not can_manage_fleet(request.user):
        messages.error(request, 'Only managers/accounts can edit vehicles.')
        return redirect('fleet_vehicle_list')
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated.')
            return redirect('fleet_vehicle_list')
    else:
        form = VehicleForm(instance=vehicle)
    return render(request, 'fleet/vehicle_form.html', {
        'form': form, 'title': f'Edit {vehicle.vehicle_number}', 'vehicle': vehicle,
    })


@module_required(MODULE_FLEET)
def card_list(request):
    cards = PetrolCard.objects.select_related('vehicle').all()
    return render(request, 'fleet/card_list.html', {
        'cards': cards,
        'can_manage': can_manage_fleet(request.user),
    })


@module_required(MODULE_FLEET)
def card_create(request):
    if not can_manage_fleet(request.user):
        messages.error(request, 'Only accounts/managers can manage petrol cards.')
        return redirect('fleet_card_list')
    if request.method == 'POST':
        form = PetrolCardForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Petrol card saved.')
            return redirect('fleet_card_list')
    else:
        form = PetrolCardForm()
    return render(request, 'fleet/card_form.html', {'form': form, 'title': 'Add Petrol Card'})


@module_required(MODULE_FLEET)
def card_detail(request, pk):
    card = get_object_or_404(PetrolCard.objects.select_related('vehicle'), pk=pk)
    recharges = card.recharges.select_related('created_by')[:30]
    fuels = card.fuel_transactions.select_related('vehicle', 'driver')[:30]
    recharge_form = CardRechargeForm(initial={'recharge_date': timezone.localdate()})
    return render(request, 'fleet/card_detail.html', {
        'card': card,
        'recharges': recharges,
        'fuels': fuels,
        'recharge_form': recharge_form,
        'can_manage': can_manage_fleet(request.user),
    })


@module_required(MODULE_FLEET)
def card_recharge(request, pk):
    card = get_object_or_404(PetrolCard, pk=pk)
    if not can_manage_fleet(request.user):
        messages.error(request, 'Only accounts/managers can recharge cards.')
        return redirect('fleet_card_detail', pk=pk)
    if request.method == 'POST':
        form = CardRechargeForm(request.POST)
        if form.is_valid():
            try:
                recharge_petrol_card(
                    card,
                    amount=form.cleaned_data['amount'],
                    recharge_date=form.cleaned_data['recharge_date'],
                    reference=form.cleaned_data.get('reference_number', ''),
                    bank=form.cleaned_data.get('bank', ''),
                    remarks=form.cleaned_data.get('remarks', ''),
                    user=request.user,
                )
                messages.success(request, 'Card recharged.')
            except ValidationError as e:
                messages.error(request, '; '.join(sum(e.message_dict.values(), [])) if hasattr(e, 'message_dict') else str(e))
        else:
            messages.error(request, 'Please correct recharge form errors.')
    return redirect('fleet_card_detail', pk=pk)


@module_required(MODULE_FLEET)
def fuel_list(request):
    qs = FuelTransaction.objects.select_related(
        'vehicle', 'driver', 'petrol_card', 'order', 'special_project',
    )
    if not can_manage_fleet(request.user):
        qs = qs.filter(Q(driver=request.user) | Q(created_by=request.user))
    vehicle_id = request.GET.get('vehicle')
    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)
    return render(request, 'fleet/fuel_list.html', {
        'transactions': qs[:200],
        'can_create': can_create_fuel_entry(request.user),
        'can_manage': can_manage_fleet(request.user),
        'vehicles': Vehicle.objects.filter(status=Vehicle.STATUS_ACTIVE),
        'vehicle_filter': vehicle_id or '',
    })


@module_required(MODULE_FLEET)
def fuel_create(request):
    if not can_create_fuel_entry(request.user):
        messages.error(request, 'You cannot create fuel entries.')
        return redirect('fleet_fuel_list')

    if request.method == 'POST':
        form = FuelTransactionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            fuel = form.save(commit=False)
            try:
                save_fuel_transaction(fuel, user=request.user, is_new=True)
                if fuel.odometer_warning:
                    messages.warning(
                        request,
                        'Saved with odometer warning: current KM is less than previous KM.',
                    )
                else:
                    messages.success(
                        request,
                        f'Fuel entry saved. Distance {fuel.distance_km} KM, '
                        f'mileage {fuel.mileage_kmpl or "—"} KM/L, amount {fuel.total_amount}.',
                    )
                return redirect('fleet_fuel_detail', pk=fuel.pk)
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errs in e.message_dict.items():
                        for err in errs:
                            form.add_error(field if field in form.fields else None, err)
                else:
                    form.add_error(None, e)
        messages.error(request, 'Could not save fuel entry. Please correct the errors.')
    else:
        initial = {}
        vid = request.GET.get('vehicle')
        if vid:
            initial['vehicle'] = vid
            v = Vehicle.objects.filter(pk=vid).first()
            if v:
                initial['previous_odometer_km'] = previous_odometer_for_vehicle(v)
        form = FuelTransactionForm(user=request.user, initial=initial)

    cards = list(
        PetrolCard.objects.filter(status=PetrolCard.STATUS_ACTIVE).values(
            'id', 'card_number', 'mobile_number', 'current_balance', 'card_name',
        )
    )
    for c in cards:
        c['current_balance'] = str(c['current_balance'])
    return render(request, 'fleet/fuel_form.html', {
        'form': form,
        'title': 'Add Fuel Entry',
        'cards_json': json.dumps(cards),
    })


@module_required(MODULE_FLEET)
def fuel_detail(request, pk):
    fuel = get_object_or_404(
        FuelTransaction.objects.select_related(
            'vehicle', 'driver', 'petrol_card', 'order', 'special_project', 'created_by',
        ),
        pk=pk,
    )
    if (
        not can_manage_fleet(request.user)
        and fuel.driver_id != request.user.pk
        and fuel.created_by_id != request.user.pk
    ):
        messages.error(request, 'Access denied.')
        return redirect('fleet_fuel_list')
    return render(request, 'fleet/fuel_detail.html', {
        'fuel': fuel,
        'can_edit': can_edit_fuel_entry(request.user, fuel),
        'can_manage': can_manage_fleet(request.user),
    })


@module_required(MODULE_FLEET)
def fuel_edit(request, pk):
    fuel = get_object_or_404(FuelTransaction, pk=pk)
    if not can_edit_fuel_entry(request.user, fuel):
        messages.error(request, 'You cannot edit this fuel entry.')
        return redirect('fleet_fuel_detail', pk=pk)
    if request.method == 'POST':
        form = FuelTransactionForm(request.POST, request.FILES, instance=fuel, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            # Phase 1: do not re-apply card/petty deductions on edit
            obj.recalculate()
            obj.save()
            messages.success(request, 'Fuel entry updated (payment balances unchanged).')
            return redirect('fleet_fuel_detail', pk=pk)
    else:
        form = FuelTransactionForm(instance=fuel, user=request.user)
    cards = list(
        PetrolCard.objects.filter(status=PetrolCard.STATUS_ACTIVE).values(
            'id', 'card_number', 'mobile_number', 'current_balance', 'card_name',
        )
    )
    for c in cards:
        c['current_balance'] = str(c['current_balance'])
    return render(request, 'fleet/fuel_form.html', {
        'form': form,
        'title': 'Edit Fuel Entry',
        'fuel': fuel,
        'cards_json': json.dumps(cards),
    })


@module_required(MODULE_FLEET)
def reimbursement_list(request):
    if not can_manage_fleet(request.user):
        messages.error(request, 'Accounts/managers only.')
        return redirect('fleet_dashboard')
    qs = FuelTransaction.objects.filter(
        payment_method=FuelTransaction.PAY_CASH,
    ).exclude(reimbursement_status='').select_related('vehicle', 'driver')
    status = request.GET.get('status', 'PENDING')
    if status:
        qs = qs.filter(reimbursement_status=status)
    return render(request, 'fleet/reimbursement_list.html', {
        'transactions': qs[:200],
        'status_filter': status,
    })


@module_required(MODULE_FLEET)
def reimbursement_update(request, pk):
    if not can_manage_fleet(request.user):
        messages.error(request, 'Accounts/managers only.')
        return redirect('fleet_dashboard')
    fuel = get_object_or_404(FuelTransaction, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('reimbursement_status')
        allowed = {c[0] for c in FuelTransaction.REIMB_CHOICES if c[0]}
        if new_status in allowed:
            fuel.reimbursement_status = new_status
            if new_status in (FuelTransaction.REIMB_APPROVED, FuelTransaction.REIMB_PAID):
                fuel.is_locked = True
            fuel.save(update_fields=['reimbursement_status', 'is_locked', 'updated_at'])
            messages.success(request, f'Reimbursement marked {new_status}.')
    return redirect('fleet_reimbursement_list')


@module_required(MODULE_FLEET)
def petty_cash(request):
    if not can_manage_fleet(request.user):
        messages.error(request, 'Accounts/managers only.')
        return redirect('fleet_dashboard')
    account = PettyCashAccount.get_default()
    form = PettyCashTopupForm(initial={'entry_date': timezone.localdate()})
    if request.method == 'POST':
        form = PettyCashTopupForm(request.POST)
        if form.is_valid():
            try:
                topup_petty_cash(
                    amount=form.cleaned_data['amount'],
                    entry_date=form.cleaned_data['entry_date'],
                    reference=form.cleaned_data.get('reference', ''),
                    remarks=form.cleaned_data.get('remarks', ''),
                    user=request.user,
                )
                messages.success(request, 'Petty cash topped up.')
                return redirect('fleet_petty_cash')
            except ValidationError as e:
                messages.error(request, str(e))
    ledger = PettyCashLedger.objects.select_related('created_by', 'fuel_transaction')[:50]
    return render(request, 'fleet/petty_cash.html', {
        'account': account,
        'form': form,
        'ledger': ledger,
    })


@module_required(MODULE_FLEET)
def mileage_report(request):
    qs = (
        FuelTransaction.objects.exclude(mileage_kmpl__isnull=True)
        .select_related('vehicle', 'driver')
        .order_by('-transaction_date')[:200]
    )
    return render(request, 'fleet/mileage_report.html', {
        'transactions': qs,
    })
