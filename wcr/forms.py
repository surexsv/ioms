from django import forms
from django.db import models

from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES

from .models import WorkCompletionReport
from orders.models import Order


class WCRForm(AuthorizedSignatoryFormMixin, forms.ModelForm):
    class Meta:
        model = WorkCompletionReport
        fields = [
            'order', 'work_description', 'material_used', 'photo',
            *SIGNATORY_FIELD_NAMES,
        ]
        widgets = {
            'work_description': forms.Textarea(attrs={'rows': 4}),
            'material_used': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, user=user, **kwargs)
        qs = Order.objects.filter(status='COMPLETED').filter(workcompletionreport__isnull=True)
        if user and user.role in ('ENGINEER', 'Technician'):
            qs = qs.filter(
                models.Q(work_schedule__assigned_engineers=user) | models.Q(assigned_to=user),
            ).distinct()
        self.fields['order'].queryset = qs


class WCRApproveForm(forms.ModelForm):
    class Meta:
        model = WorkCompletionReport
        fields = ['approved']
