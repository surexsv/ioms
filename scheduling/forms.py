from django import forms

from accounts.models import User
from accounts.roles import ROLE_ENGINEER, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, ROLE_TECHNICIAN

from .models import WorkSchedule


class WorkScheduleForm(forms.ModelForm):
    assigned_engineers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role__in=['ENGINEER', 'Technician'], is_active_employee=True),
        widget=forms.SelectMultiple(attrs={'size': 4}),
        required=False,
        label='Assigned Engineers (Legacy)',
        help_text='Optional — use team fields below for multi-resource assignment',
    )
    supporting_engineers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role=ROLE_ENGINEER, is_active_employee=True),
        widget=forms.SelectMultiple(attrs={'size': 5}),
        required=False,
        label='Supporting Engineers',
    )
    technicians = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role=ROLE_TECHNICIAN, is_active_employee=True),
        widget=forms.SelectMultiple(attrs={'size': 5}),
        required=False,
        label='Technicians',
    )

    class Meta:
        model = WorkSchedule
        fields = [
            'scheduled_start_date',
            'scheduled_end_date',
            'scheduled_time',
            'expected_duration_hours',
            'expected_man_days',
            'project_manager',
            'supervisor',
            'lead_engineer',
            'supporting_engineers',
            'technicians',
            'assigned_engineers',
            'team_leader',
            'vehicle_assigned',
            'resource_requirements',
            'work_instructions',
            'status',
        ]
        widgets = {
            'scheduled_start_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_end_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
            'resource_requirements': forms.Textarea(attrs={'rows': 3}),
            'work_instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project_manager'].queryset = User.objects.filter(
            role=ROLE_PROJECT_MANAGER, is_active_employee=True,
        )
        self.fields['supervisor'].queryset = User.objects.filter(
            role__in=[ROLE_SUPERVISOR, 'Supervisor'], is_active_employee=True,
        )
        self.fields['lead_engineer'].queryset = User.objects.filter(
            role=ROLE_ENGINEER, is_active_employee=True,
        )
        self.fields['team_leader'].queryset = User.objects.filter(
            role__in=[ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR, 'Supervisor', 'OPERATIONS'],
            is_active_employee=True,
        )
        self.fields['team_leader'].required = False
        for f in ('project_manager', 'supervisor', 'lead_engineer'):
            self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('scheduled_start_date')
        end = cleaned.get('scheduled_end_date')
        if start and end and end < start:
            raise forms.ValidationError('Scheduled end date cannot be before start date.')
        return cleaned
