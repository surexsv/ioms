from django import forms
from django.utils import timezone
from accounts.models import User
from .models import Attendance
from .services import active_employees


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = [
            'employee', 'attendance_date', 'status',
            'check_in_time', 'check_out_time',
            'location', 'latitude', 'longitude', 'notes',
        ]
        widgets = {
            'attendance_date': forms.DateInput(attrs={'type': 'date'}),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'location': forms.TextInput(attrs={'placeholder': 'Work location / site'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = active_employees().order_by('username')


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
    location = forms.CharField(max_length=500, required=False)
    latitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7)
    longitude = forms.DecimalField(required=False, max_digits=10, decimal_places=7)


class ReportMonthForm(forms.Form):
    month = forms.IntegerField(min_value=1, max_value=12)
    year = forms.IntegerField(min_value=2020, max_value=2100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.is_bound:
            self.initial.setdefault('month', today.month)
            self.initial.setdefault('year', today.year)
