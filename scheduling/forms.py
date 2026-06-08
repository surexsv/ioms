from django import forms

from accounts.models import User

from .models import WorkSchedule


class WorkScheduleForm(forms.ModelForm):
    assigned_engineers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(role__in=['ENGINEER', 'Technician'], is_active_employee=True),
        widget=forms.SelectMultiple(attrs={'size': 6}),
        required=False,
        label='Assigned Engineers',
    )

    class Meta:
        model = WorkSchedule
        fields = [
            'scheduled_start_date',
            'scheduled_end_date',
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
            'resource_requirements': forms.Textarea(attrs={'rows': 3}),
            'work_instructions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        leaders = User.objects.filter(
            role__in=['ENGINEER', 'Technician', 'Supervisor', 'OPERATIONS'],
            is_active_employee=True,
        )
        self.fields['team_leader'].queryset = leaders
        self.fields['team_leader'].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('scheduled_start_date')
        end = cleaned.get('scheduled_end_date')
        if start and end and end < start:
            raise forms.ValidationError('Scheduled end date cannot be before start date.')
        return cleaned
