from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from fleet.models import FuelTransaction
from orders.models import Order
from special_projects.models import SpecialProject

from .models import ApprovalLimit, EmployeeAdvance, ExpenseCategory, PeamsSettings, ProjectExpense
from .permissions import can_manage_peams

User = get_user_model()


def _order_queryset():
    """Order PK is order_id — never order_by('id'). Avoid slicing ModelChoiceField querysets."""
    return Order.objects.select_related('client').order_by('-order_id')


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['code', 'name', 'sort_order', 'is_active', 'gl_account_code', 'remarks']


class PeamsSettingsForm(forms.ModelForm):
    class Meta:
        model = PeamsSettings
        fields = ['director_approval_threshold', 'default_currency']


class ApprovalLimitForm(forms.ModelForm):
    class Meta:
        model = ApprovalLimit
        fields = [
            'step_code', 'step_order', 'min_amount', 'max_amount',
            'can_approve_up_to', 'is_active', 'remarks',
        ]


class EmployeeAdvanceForm(forms.ModelForm):
    class Meta:
        model = EmployeeAdvance
        fields = [
            'advance_date', 'employee', 'special_project', 'order',
            'purpose', 'amount', 'remarks',
        ]
        widgets = {
            'advance_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = User.objects.filter(is_active=True).order_by(
            'first_name', 'username',
        )
        self.fields['special_project'].queryset = SpecialProject.objects.select_related(
            'order', 'order__client',
        ).order_by('-pk')
        self.fields['special_project'].required = False
        self.fields['order'].queryset = _order_queryset()
        self.fields['order'].required = False


class AdvanceSettleForm(forms.Form):
    amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)
    remarks = forms.CharField(required=False, max_length=255)


class ProjectExpenseForm(forms.ModelForm):
    class Meta:
        model = ProjectExpense
        fields = [
            'expense_date', 'employee', 'special_project', 'order', 'category',
            'amount', 'payment_method', 'advance', 'fuel_transaction',
            'vendor_name', 'description', 'location', 'bill_upload', 'remarks',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        manage = can_manage_peams(user) if user else False

        if manage:
            self.fields['employee'].queryset = User.objects.filter(is_active=True).order_by(
                'first_name', 'username',
            )
        elif user:
            self.fields['employee'].queryset = User.objects.filter(pk=user.pk)
            self.fields['employee'].initial = user.pk
        else:
            self.fields['employee'].queryset = User.objects.none()

        if user and not self.instance.pk:
            self.fields['employee'].initial = user.pk

        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        self.fields['special_project'].queryset = SpecialProject.objects.select_related(
            'order',
        ).order_by('-pk')
        self.fields['special_project'].required = False
        self.fields['order'].queryset = _order_queryset()
        self.fields['order'].required = False

        adv_qs = EmployeeAdvance.objects.filter(
            status__in=[EmployeeAdvance.STATUS_OPEN, EmployeeAdvance.STATUS_ADJUSTED],
        )
        fuel_qs = FuelTransaction.objects.select_related('vehicle').order_by(
            '-transaction_date', '-pk',
        )
        if user and not manage:
            adv_qs = adv_qs.filter(employee=user)
            fuel_qs = fuel_qs.filter(Q(driver=user) | Q(created_by=user)).distinct()
        self.fields['advance'].queryset = adv_qs
        self.fields['advance'].required = False
        self.fields['fuel_transaction'].queryset = fuel_qs
        self.fields['fuel_transaction'].required = False

        self.fields['payment_method'].choices = [
            c for c in ProjectExpense.PAYMENT_CHOICES
            if c[0] != ProjectExpense.PAY_CREDIT_CARD
        ]

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('payment_method')
        fuel = cleaned.get('fuel_transaction')
        employee = cleaned.get('employee')

        if self.user and not can_manage_peams(self.user):
            cleaned['employee'] = self.user
            employee = self.user

        if method == ProjectExpense.PAY_PETROL_CARD:
            if not fuel:
                self.add_error('fuel_transaction', 'Link a Fleet fuel transaction.')
            else:
                cleaned['amount'] = fuel.total_amount
        if method == ProjectExpense.PAY_ADVANCE:
            advance = cleaned.get('advance')
            if not advance:
                self.add_error('advance', 'Select an open advance.')
            elif employee and advance.employee_id != employee.pk:
                self.add_error('advance', 'Advance must belong to the selected employee.')
            elif advance:
                from .services import advance_remaining
                remaining = advance_remaining(advance)
                amount = cleaned.get('amount') or Decimal('0')
                if amount > remaining:
                    self.add_error('amount', f'Exceeds remaining advance balance ({remaining}).')
        if method == ProjectExpense.PAY_PETROL_CARD and fuel:
            dup = ProjectExpense.objects.filter(
                fuel_transaction=fuel,
            ).exclude(
                status__in=[ProjectExpense.STATUS_REJECTED, ProjectExpense.STATUS_DRAFT],
            )
            if self.instance and self.instance.pk:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                self.add_error('fuel_transaction', 'This Fleet fuel entry is already linked in PEAMS.')
        if method == ProjectExpense.PAY_CREDIT_CARD:
            self.add_error('payment_method', 'Credit card is not available in Phase 1.')
        return cleaned


class ExpenseActionForm(forms.Form):
    remarks = forms.CharField(required=False, max_length=255, widget=forms.Textarea(attrs={'rows': 2}))
