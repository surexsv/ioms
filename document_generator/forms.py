from django import forms

from .constants import DOCUMENT_TYPES
from .models import DocumentNumberSettings


class DocumentNumberSettingsForm(forms.ModelForm):
    class Meta:
        model = DocumentNumberSettings
        fields = [
            'company_prefix',
            'order_prefix',
            'quotation_prefix',
            'wcr_prefix',
            'boq_prefix',
            'invoice_prefix',
            'purchase_order_prefix',
            'schedule_prefix',
            'enquiry_prefix',
            'estimate_boq_prefix',
            'request_prefix',
            'special_project_prefix',
            'serial_length',
            'year_format',
            'allow_editing',
        ]
        help_texts = {
            'invoice_prefix': (
                'Leave blank for Invoice series ITSPL26270001. '
                'Existing invoices keep their old numbers.'
            ),
        }
        widgets = {
            'invoice_prefix': forms.TextInput(attrs={
                'placeholder': '(blank = ITSPL + year + serial)',
            }),
        }


class CounterResetForm(forms.Form):
    document_type = forms.ChoiceField(choices=DOCUMENT_TYPES)
    confirm = forms.BooleanField(
        required=True,
        label='I understand this resets the serial counter for the current year series',
    )
