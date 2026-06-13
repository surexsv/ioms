from django import forms
from django.utils import timezone

from accounts.models import User
from .models import (
    AgendaTemplateItem,
    DailyMeeting,
    ManagementMessage,
    MeetingActionItem,
    MeetingAttendance,
    MeetingDiscussion,
    OpenItemRegister,
)


class DailyMeetingForm(forms.ModelForm):
    class Meta:
        model = DailyMeeting
        fields = [
            'meeting_date', 'meeting_time', 'meeting_type',
            'topic_of_day', 'conducted_by', 'department', 'status', 'remarks', 'closing_message',
        ]
        widgets = {
            'meeting_date': forms.DateInput(attrs={'type': 'date'}),
            'meeting_time': forms.TimeInput(attrs={'type': 'time'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
            'closing_message': forms.Textarea(attrs={'rows': 2}),
            'topic_of_day': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conducted_by'].queryset = User.objects.filter(
            is_active=True,
        ).order_by('username')


class MeetingAttendanceForm(forms.ModelForm):
    class Meta:
        model = MeetingAttendance
        fields = ['status', 'join_time', 'remarks']
        widgets = {
            'join_time': forms.TimeInput(attrs={'type': 'time'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.is_manual_override = True
        if commit:
            obj.save()
        return obj


class MeetingDiscussionForm(forms.ModelForm):
    class Meta:
        model = MeetingDiscussion
        fields = [
            'agenda_title', 'discussion_notes', 'key_learnings',
            'challenges', 'improvement_areas', 'decisions_taken', 'sort_order',
        ]
        widgets = {
            'discussion_notes': forms.Textarea(attrs={'rows': 3}),
            'key_learnings': forms.Textarea(attrs={'rows': 2}),
            'challenges': forms.Textarea(attrs={'rows': 2}),
            'improvement_areas': forms.Textarea(attrs={'rows': 2}),
            'decisions_taken': forms.Textarea(attrs={'rows': 2}),
        }


class MeetingActionItemForm(forms.ModelForm):
    class Meta:
        model = MeetingActionItem
        fields = [
            'description', 'assigned_to', 'target_date',
            'priority', 'status', 'remarks', 'completion_date',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'target_date': forms.DateInput(attrs={'type': 'date'}),
            'completion_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('username')


class ManagementMessageForm(forms.ModelForm):
    class Meta:
        model = ManagementMessage
        fields = ['message_date', 'category', 'message']
        widgets = {
            'message_date': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 4}),
        }


class OpenItemRegisterForm(forms.ModelForm):
    class Meta:
        model = OpenItemRegister
        fields = [
            'title', 'description', 'category', 'status',
            'owner', 'target_date', 'is_recurring', 'remarks',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'target_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }


class AgendaTemplateItemForm(forms.ModelForm):
    class Meta:
        model = AgendaTemplateItem
        fields = ['sort_order', 'title', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class MeetingFilterForm(forms.Form):
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(DailyMeeting.STATUS_CHOICES),
    )
    meeting_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(DailyMeeting.TYPE_CHOICES),
    )


class ActionFilterForm(forms.Form):
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(MeetingActionItem.STATUS_CHOICES),
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        empty_label='All assignees',
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + list(MeetingActionItem.PRIORITY_CHOICES),
    )


class ReportMonthForm(forms.Form):
    month = forms.IntegerField(min_value=1, max_value=12)
    year = forms.IntegerField(min_value=2020, max_value=2100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.is_bound:
            self.initial.setdefault('month', today.month)
            self.initial.setdefault('year', today.year)
