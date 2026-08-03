from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import (
    DailyExpenseLine,
    DailyLabourLine,
    DailyMaterialLine,
    DailyMedia,
    DailyServiceLine,
    ProjectDailyLog,
    SpecialProject,
)
from .permissions import can_manage_special_projects

User = get_user_model()


class SpecialProjectForm(forms.ModelForm):
    class Meta:
        model = SpecialProject
        fields = [
            'name', 'category', 'project_manager',
            'planned_start_date', 'planned_end_date',
            'actual_start_date', 'actual_end_date',
            'budget', 'status', 'overall_progress_pct', 'remarks',
        ]
        widgets = {
            'planned_start_date': forms.DateInput(attrs={'type': 'date'}),
            'planned_end_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_start_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_end_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project_manager'].queryset = User.objects.filter(
            is_active=True,
        ).order_by('first_name', 'username')
        self.fields['project_manager'].required = False


class ProjectDailyLogForm(forms.ModelForm):
    class Meta:
        model = ProjectDailyLog
        fields = [
            'log_date', 'site_location', 'mentor', 'assigned_employees',
            'work_description', 'daily_progress_pct',
            'planned_work', 'actual_work', 'issues_risks',
            'next_day_plan', 'remarks',
        ]
        widgets = {
            'log_date': forms.DateInput(attrs={'type': 'date'}),
            'work_description': forms.Textarea(attrs={'rows': 3}),
            'planned_work': forms.Textarea(attrs={'rows': 2}),
            'actual_work': forms.Textarea(attrs={'rows': 2}),
            'issues_risks': forms.Textarea(attrs={'rows': 2}),
            'next_day_plan': forms.Textarea(attrs={'rows': 2}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
            'assigned_employees': forms.SelectMultiple(attrs={'size': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['mentor'].queryset = active
        self.fields['assigned_employees'].queryset = active
        self.fields['mentor'].required = False


LabourFormSet = inlineformset_factory(
    ProjectDailyLog, DailyLabourLine,
    fields=['employee', 'attendance', 'hours_worked', 'overtime_hours',
            'special_work', 'emergency_callout', 'remarks'],
    extra=2, can_delete=True,
)

MaterialFormSet = inlineformset_factory(
    ProjectDailyLog, DailyMaterialLine,
    fields=['material', 'unit', 'opening_balance', 'issued_qty', 'consumed_qty',
            'returned_qty', 'linked_boq_item', 'remarks'],
    extra=2, can_delete=True,
)

ServiceFormSet = inlineformset_factory(
    ProjectDailyLog, DailyServiceLine,
    fields=['service_type', 'quantity', 'unit', 'remarks'],
    extra=2, can_delete=True,
)

ExpenseFormSet = inlineformset_factory(
    ProjectDailyLog, DailyExpenseLine,
    fields=['expense_type', 'amount', 'approval_status', 'bill_photo', 'remarks'],
    extra=2, can_delete=True,
)

# Field staff cannot set approval_status (would post into PEAMS ledger)
ExpenseFormSetField = inlineformset_factory(
    ProjectDailyLog, DailyExpenseLine,
    fields=['expense_type', 'amount', 'bill_photo', 'remarks'],
    extra=2, can_delete=True,
)

MediaFormSet = inlineformset_factory(
    ProjectDailyLog, DailyMedia,
    fields=['media_type', 'file', 'caption'],
    extra=2, can_delete=True,
)


def expense_formset_for_user(user, *args, **kwargs):
    """Managers may approve diary expenses; field staff create as PENDING only."""
    if can_manage_special_projects(user) if user else False:
        return ExpenseFormSet(*args, **kwargs)
    return ExpenseFormSetField(*args, **kwargs)
