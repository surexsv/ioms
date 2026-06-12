from django import forms

from accounts.models import User
from accounts.roles import ROLE_ENGINEER, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR, ROLE_TECHNICIAN
from .models import Enquiry, SiteProgressUpdate


class EnquiryForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = [
            'enquiry_date', 'client', 'contact_person', 'mobile', 'email', 'location',
            'enquiry_type', 'description', 'source', 'assigned_to',
            'assigned_project_manager', 'assigned_supervisor',
            'survey_required', 'feasibility_required',
            'survey_date', 'survey_engineer', 'survey_remarks',
            'feasibility_status', 'feasibility_remarks',
            'follow_up_date', 'follow_up_notes', 'opportunity_value',
            'remarks', 'status',
        ]
        widgets = {
            'enquiry_date': forms.DateInput(attrs={'type': 'date'}),
            'survey_date': forms.DateInput(attrs={'type': 'date'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'location': forms.Textarea(attrs={'rows': 2}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
            'survey_remarks': forms.Textarea(attrs={'rows': 2}),
            'feasibility_remarks': forms.Textarea(attrs={'rows': 2}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_project_manager'].queryset = User.objects.filter(
            role=ROLE_PROJECT_MANAGER, is_active=True,
        )
        self.fields['assigned_supervisor'].queryset = User.objects.filter(
            role__in=[ROLE_SUPERVISOR, 'Supervisor'], is_active=True,
        )
        self.fields['survey_engineer'].queryset = User.objects.filter(
            role__in=[ROLE_ENGINEER, ROLE_TECHNICIAN], is_active=True,
        )


class SiteProgressUpdateForm(forms.ModelForm):
    class Meta:
        model = SiteProgressUpdate
        fields = [
            'enquiry', 'order', 'update_date', 'site_location',
            'work_description', 'progress_percent', 'photo', 'attendance_noted',
        ]
        widgets = {
            'update_date': forms.DateInput(attrs={'type': 'date'}),
            'work_description': forms.Textarea(attrs={'rows': 3}),
        }
