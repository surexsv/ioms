from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import User
from .models import Attendance
from .services import active_employees


SENSITIVE_FORM_FIELDS = (
    'location', 'latitude', 'longitude',
    'check_out_location', 'check_out_latitude', 'check_out_longitude',
)


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = [
            'employee', 'attendance_date', 'status',
            'check_in_time', 'check_out_time',
            'location', 'latitude', 'longitude',
            'check_out_location', 'check_out_latitude', 'check_out_longitude',
            'notes', 'check_in_remarks', 'check_out_remarks',
        ]
        widgets = {
            'attendance_date': forms.DateInput(attrs={'type': 'date'}),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'check_in_remarks': forms.Textarea(attrs={'rows': 2}),
            'check_out_remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = active_employees().order_by('username')
        if user is not None:
            from attendance.permissions import can_view_attendance_audit_data
            if not can_view_attendance_audit_data(user):
                for name in SENSITIVE_FORM_FIELDS:
                    self.fields.pop(name, None)


class AttendanceFilterForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label='All employees',
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(Attendance.STATUS_CHOICES),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = active_employees().order_by('username')


class CheckInForm(forms.Form):
    latitude = forms.DecimalField(required=True, max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(required=True, max_digits=10, decimal_places=7)
    location = forms.CharField(max_length=500, required=False, widget=forms.HiddenInput())
    photo = forms.ImageField(required=True)
    remarks = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            raise ValidationError('Photo is required for check-in.')
        if photo.size > 8 * 1024 * 1024:
            raise ValidationError('Photo must be under 8 MB.')
        return photo


class CheckOutForm(forms.Form):
    latitude = forms.DecimalField(required=True, max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(required=True, max_digits=10, decimal_places=7)
    location = forms.CharField(max_length=500, required=False, widget=forms.HiddenInput())
    photo = forms.ImageField(required=True)
    remarks = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if not photo:
            raise ValidationError('Photo is required for check-out.')
        if photo.size > 8 * 1024 * 1024:
            raise ValidationError('Photo must be under 8 MB.')
        return photo


class ReportMonthForm(forms.Form):
    month = forms.IntegerField(min_value=1, max_value=12)
    year = forms.IntegerField(min_value=2020, max_value=2100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.is_bound:
            self.initial.setdefault('month', today.month)
            self.initial.setdefault('year', today.year)
