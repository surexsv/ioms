from django import forms
from django.core.exceptions import ValidationError

from accounts.models import User

from .constants import EDITABLE_STATUSES, MAX_ATTACHMENT_MB, PRIORITY_CHOICES, STATUS_CHOICES
from .models import EmployeeRequest, RequestType
from .services import approver_users_for_type


class EmployeeRequestForm(forms.ModelForm):
    class Meta:
        model = EmployeeRequest
        fields = [
            'request_type', 'request_date', 'department', 'submitted_to',
            'priority', 'subject', 'description', 'amount', 'remarks',
        ]
        widgets = {
            'request_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['request_type'].queryset = RequestType.objects.filter(is_active=True)
        self.fields['submitted_to'].queryset = User.objects.none()
        self.fields['submitted_to'].required = False
        rt = None
        if self.data.get('request_type'):
            rt = RequestType.objects.filter(pk=self.data.get('request_type')).first()
        elif self.instance.pk and self.instance.request_type_id:
            rt = self.instance.request_type
        if rt and user:
            self.fields['submitted_to'].queryset = approver_users_for_type(rt, exclude_user=user)

    def clean(self):
        cleaned = super().clean()
        rt = cleaned.get('request_type')
        amount = cleaned.get('amount')
        if rt and rt.requires_amount and amount is None:
            self.add_error('amount', 'Amount is required for this request type.')
        return cleaned


class RequestSubmitForm(forms.Form):
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class RequestActionForm(forms.Form):
    remarks = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Remarks',
    )


class RequestFilterForm(forms.Form):
    request_type = forms.ModelChoiceField(
        queryset=RequestType.objects.filter(is_active=True),
        required=False,
        empty_label='All types',
    )
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + list(STATUS_CHOICES))
    department = forms.CharField(required=False)
    employee = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        empty_label='All employees',
    )


class RequestAttachmentForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data['file']
        if f.size > MAX_ATTACHMENT_MB * 1024 * 1024:
            raise ValidationError(f'File must be under {MAX_ATTACHMENT_MB} MB.')
        return f
