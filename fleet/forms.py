from django import forms
from django.contrib.auth import get_user_model

from orders.models import Order
from special_projects.models import SpecialProject

from .models import FuelTransaction, PetrolCard, Vehicle
from .permissions import can_manage_fleet
from .services import previous_odometer_for_vehicle

User = get_user_model()


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_number', 'vehicle_type', 'brand', 'model_name', 'year',
            'assigned_employee', 'fuel_type', 'tank_capacity_litres',
            'mileage_target_kmpl', 'last_odometer_km', 'status', 'remarks',
        ]
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_employee'].queryset = User.objects.filter(
            is_active=True,
        ).order_by('first_name', 'username')
        self.fields['assigned_employee'].required = False


class PetrolCardForm(forms.ModelForm):
    class Meta:
        model = PetrolCard
        fields = [
            'card_name', 'card_number', 'mobile_number', 'vehicle',
            'current_balance', 'status',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.filter(
            status=Vehicle.STATUS_ACTIVE,
        ).order_by('vehicle_number')
        self.fields['vehicle'].required = False
        if self.instance and self.instance.pk:
            self.fields['current_balance'].disabled = True
            self.fields['current_balance'].help_text = 'Balance changes via recharge / fuel entries.'


class CardRechargeForm(forms.Form):
    recharge_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)
    reference_number = forms.CharField(required=False, max_length=80)
    bank = forms.CharField(required=False, max_length=120)
    remarks = forms.CharField(required=False, max_length=255, widget=forms.Textarea(attrs={'rows': 2}))


class PettyCashTopupForm(forms.Form):
    entry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)
    reference = forms.CharField(required=False, max_length=120)
    remarks = forms.CharField(required=False, max_length=255)


class FuelTransactionForm(forms.ModelForm):
    class Meta:
        model = FuelTransaction
        fields = [
            'transaction_date', 'driver', 'vehicle',
            'previous_odometer_km', 'current_odometer_km', 'closing_odometer_km',
            'fuel_quantity_litres', 'fuel_rate',
            'payment_method', 'petrol_card',
            'order', 'special_project',
            'location', 'fuel_station', 'bill_number', 'bill_upload', 'remarks',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        manage = can_manage_fleet(user) if user else False
        if manage:
            self.fields['driver'].queryset = User.objects.filter(is_active=True).order_by(
                'first_name', 'username',
            )
        elif user:
            self.fields['driver'].queryset = User.objects.filter(pk=user.pk)
            self.fields['driver'].initial = user.pk
        else:
            self.fields['driver'].queryset = User.objects.none()
        self.fields['vehicle'].queryset = Vehicle.objects.filter(
            status=Vehicle.STATUS_ACTIVE,
        ).order_by('vehicle_number')
        self.fields['petrol_card'].queryset = PetrolCard.objects.filter(
            status=PetrolCard.STATUS_ACTIVE,
        ).order_by('card_name')
        self.fields['petrol_card'].required = False
        # Order PK is order_id — never order_by('id')
        self.fields['order'].queryset = Order.objects.select_related('client').order_by('-order_id')
        self.fields['order'].required = False
        self.fields['special_project'].queryset = SpecialProject.objects.select_related(
            'order',
        ).order_by('-pk')
        self.fields['special_project'].required = False
        self.fields['closing_odometer_km'].required = False

        if not self.is_bound and not self.instance.pk and user:
            self.fields['driver'].initial = user.pk

        if user and not manage:
            self.fields['payment_method'].choices = [
                c for c in FuelTransaction.PAYMENT_CHOICES
                if c[0] != FuelTransaction.PAY_PETTY
            ]

        vehicle = None
        if self.data.get('vehicle'):
            try:
                vehicle = Vehicle.objects.filter(pk=self.data.get('vehicle')).first()
            except Exception:
                vehicle = None
        elif self.instance and self.instance.vehicle_id:
            vehicle = self.instance.vehicle
        if vehicle and not self.is_bound and not self.instance.pk:
            self.fields['previous_odometer_km'].initial = previous_odometer_for_vehicle(vehicle)

    def clean(self):
        cleaned = super().clean()
        if self.user and not can_manage_fleet(self.user):
            cleaned['driver'] = self.user
        method = cleaned.get('payment_method')
        card = cleaned.get('petrol_card')
        if method == FuelTransaction.PAY_CARD and not card:
            self.add_error('petrol_card', 'Select a petrol card for card payments.')
        vehicle = cleaned.get('vehicle')
        if vehicle and cleaned.get('previous_odometer_km') is None:
            cleaned['previous_odometer_km'] = previous_odometer_for_vehicle(vehicle)
        if method != FuelTransaction.PAY_CARD:
            cleaned['petrol_card'] = None
        if method == FuelTransaction.PAY_PETTY and self.user and not can_manage_fleet(self.user):
            self.add_error(
                'payment_method',
                'Petty cash fuel payments require Accounts/Manager access.',
            )
        return cleaned
