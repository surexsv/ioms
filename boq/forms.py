from django import forms
from django.forms import inlineformset_factory
from .models import BOQ, BOQLineItem
from orders.models import Order
from config.company import COMPANY
from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES


class BOQForm(AuthorizedSignatoryFormMixin, forms.ModelForm):
    class Meta:
        model = BOQ
        fields = ['order', 'notes', *SIGNATORY_FIELD_NAMES]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['order'].queryset = Order.objects.exclude(
            status__in=['CLOSED', 'NEW']
        ).order_by('-order_id')


class BOQLineItemForm(forms.ModelForm):
    class Meta:
        model = BOQLineItem
        fields = ['sl_no', 'description', 'hsn_sac', 'unit', 'qty']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': 'Item / Service Description'}),
            'hsn_sac': forms.TextInput(attrs={'placeholder': 'HSN/SAC'}),
            'unit': forms.TextInput(attrs={'placeholder': 'Nos'}),
            'qty': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'sl_no': forms.NumberInput(attrs={'min': '1', 'style': 'width:60px'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['hsn_sac'].initial = COMPANY['default_hsn_sac']


BOQLineItemFormSet = inlineformset_factory(
    BOQ,
    BOQLineItem,
    form=BOQLineItemForm,
    extra=3,
    can_delete=True,
)
