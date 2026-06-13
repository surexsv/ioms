from decimal import Decimal

from django import forms
from django.db import models

from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES
from productivity.constants import COMPLETION_STATUS_CHOICES, PARTICIPANT_ROLE_CHOICES
from productivity.models import WCRTeamParticipant

from .models import WorkCompletionReport
from orders.models import Order


class WCRForm(AuthorizedSignatoryFormMixin, forms.ModelForm):
    work_start_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Work Start Time',
    )
    work_end_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Work End Time',
    )

    class Meta:
        model = WorkCompletionReport
        fields = [
            'order', 'work_description', 'material_used', 'photo',
            'work_start_time', 'work_end_time', 'completion_status',
            *SIGNATORY_FIELD_NAMES,
        ]
        widgets = {
            'work_description': forms.Textarea(attrs={'rows': 4}),
            'material_used': forms.Textarea(attrs={'rows': 3}),
            'completion_status': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, user=user, **kwargs)
        qs = Order.objects.filter(status='COMPLETED').filter(workcompletionreport__isnull=True)
        if user and user.role in ('ENGINEER', 'Technician'):
            qs = qs.filter(
                models.Q(work_schedule__assigned_engineers=user)
                | models.Q(work_schedule__lead_engineer=user)
                | models.Q(work_schedule__supporting_engineers=user)
                | models.Q(work_schedule__technicians=user)
                | models.Q(assigned_to=user),
            ).distinct()
        self.fields['order'].queryset = qs


class WCRParticipantForm(forms.ModelForm):
    class Meta:
        model = WCRTeamParticipant
        fields = ['employee', 'participant_role', 'attended', 'hours_worked', 'man_days']
        widgets = {
            'hours_worked': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
            'man_days': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = self.fields['employee'].queryset.filter(
            is_active_employee=True,
        )
        self.fields['hours_worked'].required = False
        self.fields['man_days'].required = False


WCRParticipantFormSet = forms.inlineformset_factory(
    WorkCompletionReport,
    WCRTeamParticipant,
    form=WCRParticipantForm,
    extra=0,
    can_delete=True,
)


class WCRApproveForm(forms.ModelForm):
    class Meta:
        model = WorkCompletionReport
        fields = ['approved']
