from django.contrib import admin

from .models import (
    FuelTransaction,
    PetrolCard,
    PetrolCardRecharge,
    PettyCashAccount,
    PettyCashLedger,
    Vehicle,
)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'vehicle_number', 'vehicle_type', 'fuel_type', 'assigned_employee',
        'last_odometer_km', 'status',
    )
    list_filter = ('status', 'vehicle_type', 'fuel_type')
    search_fields = ('vehicle_number', 'brand', 'model_name')


class RechargeInline(admin.TabularInline):
    model = PetrolCardRecharge
    extra = 0
    readonly_fields = ('balance_after', 'created_at', 'created_by')


@admin.register(PetrolCard)
class PetrolCardAdmin(admin.ModelAdmin):
    list_display = ('card_name', 'card_number', 'vehicle', 'current_balance', 'status')
    list_filter = ('status',)
    search_fields = ('card_name', 'card_number', 'mobile_number')
    inlines = [RechargeInline]


@admin.register(FuelTransaction)
class FuelTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_date', 'vehicle', 'driver', 'fuel_quantity_litres',
        'total_amount', 'mileage_kmpl', 'payment_method', 'reimbursement_status',
    )
    list_filter = ('payment_method', 'reimbursement_status', 'odometer_warning')
    search_fields = ('vehicle__vehicle_number', 'bill_number', 'fuel_station')
    raw_id_fields = ('driver', 'vehicle', 'order', 'special_project', 'petrol_card')


@admin.register(PettyCashAccount)
class PettyCashAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'current_balance', 'updated_at')


@admin.register(PettyCashLedger)
class PettyCashLedgerAdmin(admin.ModelAdmin):
    list_display = ('entry_date', 'entry_type', 'amount', 'balance_after', 'reference')
    list_filter = ('entry_type',)
