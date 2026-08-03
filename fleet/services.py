from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .models import (
    FuelTransaction,
    PetrolCard,
    PetrolCardRecharge,
    PettyCashAccount,
    PettyCashLedger,
    Vehicle,
)


def previous_odometer_for_vehicle(vehicle):
    last = (
        FuelTransaction.objects.filter(vehicle=vehicle)
        .order_by('-transaction_date', '-id')
        .values_list('current_odometer_km', flat=True)
        .first()
    )
    if last is not None:
        return last
    return vehicle.last_odometer_km or Decimal('0.00')


@transaction.atomic
def save_fuel_transaction(fuel: FuelTransaction, *, user=None, is_new=False):
    fuel.full_clean()
    fuel.recalculate()
    if is_new and user and not fuel.created_by_id:
        fuel.created_by = user
    if is_new and not fuel.driver_id and user:
        fuel.driver = user

    # Pre-validate balances before save
    if is_new and fuel.payment_method == FuelTransaction.PAY_CARD:
        if not fuel.petrol_card_id:
            raise ValidationError({'petrol_card': 'Select a petrol card for card payments.'})
        card = PetrolCard.objects.select_for_update().get(pk=fuel.petrol_card_id)
        if fuel.total_amount > card.current_balance:
            raise ValidationError({
                'petrol_card': (
                    f'Insufficient card balance ({card.current_balance}). '
                    f'Required {fuel.total_amount}.'
                ),
            })
    if is_new and fuel.payment_method == FuelTransaction.PAY_PETTY:
        account = PettyCashAccount.get_default()
        account = PettyCashAccount.objects.select_for_update().get(pk=account.pk)
        if fuel.total_amount > account.current_balance:
            raise ValidationError({
                'payment_method': (
                    f'Insufficient petty cash ({account.current_balance}). '
                    f'Required {fuel.total_amount}.'
                ),
            })

    if fuel.payment_method == FuelTransaction.PAY_CASH:
        if not fuel.reimbursement_status:
            fuel.reimbursement_status = FuelTransaction.REIMB_PENDING
    elif fuel.reimbursement_status == FuelTransaction.REIMB_PENDING:
        fuel.reimbursement_status = FuelTransaction.REIMB_NONE

    fuel.save()

    vehicle = Vehicle.objects.select_for_update().get(pk=fuel.vehicle_id)
    if fuel.current_odometer_km >= (vehicle.last_odometer_km or 0):
        vehicle.last_odometer_km = fuel.current_odometer_km
        vehicle.save(update_fields=['last_odometer_km', 'updated_at'])

    if is_new and fuel.payment_method == FuelTransaction.PAY_CARD and fuel.petrol_card_id:
        card = PetrolCard.objects.select_for_update().get(pk=fuel.petrol_card_id)
        card.current_balance = (card.current_balance - fuel.total_amount).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
        card.save(update_fields=['current_balance', 'updated_at'])

    if is_new and fuel.payment_method == FuelTransaction.PAY_PETTY:
        account = PettyCashAccount.get_default()
        account = PettyCashAccount.objects.select_for_update().get(pk=account.pk)
        account.current_balance = (account.current_balance - fuel.total_amount).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
        account.save(update_fields=['current_balance', 'updated_at'])
        PettyCashLedger.objects.create(
            account=account,
            entry_date=fuel.transaction_date,
            entry_type=PettyCashLedger.TYPE_DEBIT,
            amount=fuel.total_amount,
            balance_after=account.current_balance,
            reference=f'FUEL-{fuel.pk}',
            remarks=f'Fuel {fuel.vehicle.vehicle_number}',
            fuel_transaction=fuel,
            created_by=user or fuel.created_by,
        )

    return fuel


@transaction.atomic
def recharge_petrol_card(card, *, amount, recharge_date=None, reference='', bank='', remarks='', user=None):
    if amount is None or amount <= 0:
        raise ValidationError({'amount': 'Recharge amount must be greater than zero.'})
    card = PetrolCard.objects.select_for_update().get(pk=card.pk)
    card.current_balance = (card.current_balance + amount).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )
    card.last_recharge_date = recharge_date or timezone.localdate()
    card.save(update_fields=['current_balance', 'last_recharge_date', 'updated_at'])
    return PetrolCardRecharge.objects.create(
        card=card,
        recharge_date=card.last_recharge_date,
        amount=amount,
        reference_number=reference,
        bank=bank,
        remarks=remarks,
        balance_after=card.current_balance,
        created_by=user,
    )


@transaction.atomic
def topup_petty_cash(*, amount, entry_date=None, reference='', remarks='', user=None):
    if amount is None or amount <= 0:
        raise ValidationError({'amount': 'Amount must be greater than zero.'})
    account = PettyCashAccount.get_default()
    account = PettyCashAccount.objects.select_for_update().get(pk=account.pk)
    account.current_balance = (account.current_balance + amount).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )
    account.save(update_fields=['current_balance', 'updated_at'])
    return PettyCashLedger.objects.create(
        account=account,
        entry_date=entry_date or timezone.localdate(),
        entry_type=PettyCashLedger.TYPE_CREDIT,
        amount=amount,
        balance_after=account.current_balance,
        reference=reference,
        remarks=remarks,
        created_by=user,
    )


def dashboard_stats():
    today = timezone.localdate()
    month_start = today.replace(day=1)
    qs = FuelTransaction.objects.all()
    today_total = qs.filter(transaction_date=today).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    month_total = qs.filter(transaction_date__gte=month_start).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
    avg_mileage = qs.exclude(mileage_kmpl__isnull=True).aggregate(a=Avg('mileage_kmpl'))['a']
    by_vehicle = (
        qs.values('vehicle__vehicle_number')
        .annotate(total=Sum('total_amount'), trips=Count('id'), avg_m=Avg('mileage_kmpl'))
        .order_by('-total')[:8]
    )
    pending_reimb = qs.filter(reimbursement_status=FuelTransaction.REIMB_PENDING).count()
    cards = PetrolCard.objects.filter(status=PetrolCard.STATUS_ACTIVE).order_by('current_balance')[:8]
    petty = PettyCashAccount.get_default()
    low_mileage = (
        qs.exclude(mileage_kmpl__isnull=True)
        .order_by('mileage_kmpl')
        .values('vehicle__vehicle_number', 'mileage_kmpl', 'transaction_date')[:5]
    )
    high_mileage = (
        qs.exclude(mileage_kmpl__isnull=True)
        .order_by('-mileage_kmpl')
        .values('vehicle__vehicle_number', 'mileage_kmpl', 'transaction_date')[:5]
    )
    return {
        'today_total': today_total,
        'month_total': month_total,
        'avg_mileage': avg_mileage,
        'by_vehicle': by_vehicle,
        'pending_reimbursements': pending_reimb,
        'cards': cards,
        'petty_balance': petty.current_balance,
        'low_mileage': low_mileage,
        'high_mileage': high_mileage,
        'vehicle_count': Vehicle.objects.filter(status=Vehicle.STATUS_ACTIVE).count(),
        'txn_count_month': qs.filter(transaction_date__gte=month_start).count(),
    }
