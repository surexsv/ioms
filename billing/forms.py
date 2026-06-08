from decimal import Decimal, ROUND_HALF_UP

from django import forms

from django.core.exceptions import ValidationError

from django.forms import inlineformset_factory, BaseInlineFormSet

from .models import Invoice, InvoiceLineItem

from orders.models import Order

from boq.models import BOQ

from config.company import COMPANY
from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES





class InvoiceForm(AuthorizedSignatoryFormMixin, forms.ModelForm):

    INVOICE_NUMBER_MODE = (

        ('AUTO', 'Auto Generate'),

        ('MANUAL', 'Manual Entry'),

    )



    invoice_number_mode = forms.ChoiceField(

        choices=INVOICE_NUMBER_MODE,

        initial='AUTO',

        widget=forms.RadioSelect,

        label='Invoice Number Mode',

    )



    class Meta:

        model = Invoice

        fields = [

            'order', 'boq', 'invoice_number', 'service_title',

            'po_number', 'po_date', 'due_date',
            *SIGNATORY_FIELD_NAMES,
        ]

        widgets = {

            'due_date': forms.DateInput(attrs={'type': 'date'}),

            'po_date': forms.DateInput(attrs={'type': 'date'}),

            'service_title': forms.TextInput(attrs={'placeholder': 'e.g. OFC Connectivity'}),

            'invoice_number': forms.TextInput(attrs={'placeholder': 'e.g. ITSPL26270001 or ITSPLINV26270001'}),

        }



    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['order'].queryset = Order.objects.filter(

            status__in=['APPROVED', 'WCR_SUBMITTED', 'BILLED']

        ).order_by('-order_id')

        self.fields['boq'].queryset = BOQ.objects.filter(status='VERIFIED')

        self.fields['boq'].required = False

        self.fields['boq'].help_text = 'Optional — select verified BOQ to load quantities'

        self.fields['invoice_number'].required = False

        if not self.instance.pk:

            try:

                from document_generator.services import preview_next_number

                from document_generator.constants import DOC_INVOICE

                self.fields['invoice_number'].widget.attrs['data-auto-preview'] = preview_next_number(DOC_INVOICE)

            except Exception:

                pass



    def clean(self):

        cleaned = super().clean()

        mode = cleaned.get('invoice_number_mode', 'AUTO')

        invoice_number = (cleaned.get('invoice_number') or '').strip()



        if mode == 'MANUAL':

            if not invoice_number:

                raise ValidationError({'invoice_number': 'Invoice number is required for manual entry.'})

            qs = Invoice.objects.filter(invoice_number=invoice_number)

            if self.instance.pk:

                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():

                raise ValidationError({'invoice_number': 'Invoice Number already exists.'})

            cleaned['invoice_number'] = invoice_number

        else:

            cleaned['invoice_number'] = ''

        return cleaned





class InvoiceLineItemForm(forms.ModelForm):

    class Meta:

        model = InvoiceLineItem

        fields = ['sl_no', 'description', 'hsn_sac', 'unit', 'qty', 'rate', 'remarks']

        widgets = {

            'description': forms.TextInput(attrs={'placeholder': 'Item / Service Description'}),

            'hsn_sac': forms.TextInput(attrs={'placeholder': 'HSN/SAC'}),

            'unit': forms.TextInput(attrs={'placeholder': 'Nos', 'style': 'width:70px'}),

            'qty': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'style': 'width:80px'}),

            'rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'style': 'width:100px'}),

            'remarks': forms.TextInput(attrs={'placeholder': 'Remarks'}),

            'sl_no': forms.NumberInput(attrs={'min': '1', 'style': 'width:50px'}),

        }





class BaseInvoiceLineFormSet(BaseInlineFormSet):

    def clean(self):

        if any(self.errors):

            return

        active = 0

        for form in self.forms:

            if not form.cleaned_data or form.cleaned_data.get('DELETE'):

                continue

            if form.cleaned_data.get('description'):

                active += 1

        if active < 1:

            raise ValidationError('Add at least one invoice line item.')





InvoiceLineItemFormSet = inlineformset_factory(

    Invoice,

    InvoiceLineItem,

    form=InvoiceLineItemForm,

    formset=BaseInvoiceLineFormSet,

    extra=2,

    can_delete=True,

    min_num=1,

    validate_min=True,

)

