from django import forms

from accounts.models import User

from scheduling.staff_selectors import (
    engineer_queryset,
    field_staff_queryset,
    order_team_initial,
    project_manager_queryset,
    supervisor_queryset,
    team_leader_queryset,
    technician_queryset,
)

from .models import WorkSchedule


FIELD_STATUS_CHOICES = (
    (WorkSchedule.STATUS_ASSIGNED, 'Assigned'),
    (WorkSchedule.STATUS_IN_PROGRESS, 'In Progress'),
    (WorkSchedule.STATUS_COMPLETED, 'Completed'),
)


class FieldScheduleUpdateForm(forms.ModelForm):
    """Limited schedule update for assigned field team members."""

    class Meta:
        model = WorkSchedule
        fields = ['status', 'field_work_remarks']
        widgets = {
            'field_work_remarks': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Work notes, findings, completion remarks…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.status if self.instance else WorkSchedule.STATUS_ASSIGNED
        allowed = {current}
        if current == WorkSchedule.STATUS_ASSIGNED:
            allowed.add(WorkSchedule.STATUS_IN_PROGRESS)
        elif current == WorkSchedule.STATUS_IN_PROGRESS:
            allowed.add(WorkSchedule.STATUS_COMPLETED)
        elif current == WorkSchedule.STATUS_PLANNED:
            allowed.add(WorkSchedule.STATUS_ASSIGNED)
        self.fields['status'].choices = [
            c for c in FIELD_STATUS_CHOICES if c[0] in allowed
        ]


class WorkScheduleForm(forms.ModelForm):
    assigned_engineers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={'size': 4}),
        required=False,
        label='Assigned Engineers (Legacy)',
        help_text='Optional — use team fields below for multi-resource assignment',
    )
    supporting_engineers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={'size': 5}),
        required=False,
        label='Supporting Engineers',
    )
    technicians = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
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
        labels = {
            'lead_engineer': 'Engineer',
            'supervisor': 'Team Leader',
            'project_manager': 'Project Manager',
            'team_leader': 'On-site Team Leader',
        }
        widgets = {
            'scheduled_start_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_end_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
            'resource_requirements': forms.Textarea(attrs={'rows': 3}),
            'work_instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, order=None, enquiry=None, **kwargs):
        super().__init__(*args, **kwargs)
        if order is not None:
            self.instance.order = order
        if enquiry is not None:
            self.instance.enquiry = enquiry

        self.fields['project_manager'].queryset = project_manager_queryset()
        self.fields['supervisor'].queryset = supervisor_queryset()
        self.fields['lead_engineer'].queryset = engineer_queryset()
        self.fields['team_leader'].queryset = team_leader_queryset()
        self.fields['supporting_engineers'].queryset = engineer_queryset()
        self.fields['technicians'].queryset = technician_queryset()
        self.fields['assigned_engineers'].queryset = field_staff_queryset()

        self.fields['team_leader'].required = False
        for field_name in ('project_manager', 'supervisor', 'lead_engineer'):
            self.fields[field_name].required = False

        if order is not None and not self.is_bound and not kwargs.get('instance'):
            for key, value in order_team_initial(order).items():
                if key in self.fields and key not in self.initial:
                    self.initial[key] = value

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('scheduled_start_date')
        end = cleaned.get('scheduled_end_date')
        if start and end and end < start:
            raise forms.ValidationError('Scheduled end date cannot be before start date.')
        return cleaned
