from decimal import Decimal, ROUND_HALF_UP

from django import forms

from django.core.exceptions import ValidationError

from django.forms import inlineformset_factory, BaseInlineFormSet

from .models import Invoice, InvoiceLineItem

from orders.models import Order

from boq.models import BOQ

from billing.gst import GST_TYPE_CHOICES, GST_TYPE_INTRA, resolve_client_gst_type
from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES
from config.company import COMPANY





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

            'po_number', 'po_date', 'due_date', 'gst_type',
            *SIGNATORY_FIELD_NAMES,
        ]

        widgets = {

            'due_date': forms.DateInput(attrs={'type': 'date'}),

            'po_date': forms.DateInput(attrs={'type': 'date'}),

            'service_title': forms.TextInput(attrs={'placeholder': 'e.g. OFC Connectivity'}),

            'invoice_number': forms.TextInput(attrs={'placeholder': 'e.g. ITSPL26270001'}),

        }



    def __init__(self, *args, can_override_gst=False, **kwargs):

        self._can_override_gst = can_override_gst
        super().__init__(*args, **kwargs)

        self.fields['gst_type'].choices = GST_TYPE_CHOICES
        self.fields['gst_type'].widget.attrs.setdefault('id', 'id_gst_type')
        if not can_override_gst:
            self.fields['gst_type'].disabled = True

        self.fields['order'].queryset = Order.objects.filter(

            status__in=['APPROVED', 'WCR_SUBMITTED', 'BILLED']

        ).order_by('-order_id')
        self.fields['order'].required = True

        self.fields['boq'].queryset = BOQ.objects.filter(status='VERIFIED')

        self.fields['boq'].required = False

        self.fields['boq'].help_text = 'Optional — select verified BOQ to load quantities'

        self.fields['invoice_number'].required = False

        if self.instance.pk:
            self.fields['invoice_number'].widget.attrs['readonly'] = True
            self.fields['invoice_number_mode'].required = False
            if self.instance.order_id:
                self.fields['order'].queryset = Order.objects.filter(pk=self.instance.order_id)
            else:
                self.fields['order'].required = False
                self.fields['order'].queryset = Order.objects.none()

        if not self.instance.pk:

            try:

                from document_generator.services import preview_next_number

                from document_generator.constants import DOC_INVOICE

                self.fields['invoice_number'].widget.attrs['data-auto-preview'] = preview_next_number(DOC_INVOICE)

            except Exception:

                pass

        if not self.instance.pk:
            order = self.initial.get('order')
            if order:
                self._apply_client_gst_type(order)

    def _apply_client_gst_type(self, order_id):
        try:
            order = Order.objects.select_related('client').get(pk=order_id)
            self.fields['gst_type'].initial = resolve_client_gst_type(order.client)
        except Order.DoesNotExist:
            self.fields['gst_type'].initial = GST_TYPE_INTRA

    def clean(self):

        cleaned = super().clean()

        if self.instance.pk:
            cleaned['invoice_number'] = self.instance.invoice_number
            cleaned['invoice_number_mode'] = self.instance.number_mode
        else:
            mode = cleaned.get('invoice_number_mode', 'AUTO')
            invoice_number = (cleaned.get('invoice_number') or '').strip()
            if mode == 'MANUAL':
                if not invoice_number:
                    raise ValidationError({'invoice_number': 'Invoice number is required for manual entry.'})
                if Invoice.objects.filter(invoice_number=invoice_number).exists():
                    raise ValidationError({'invoice_number': 'Invoice Number already exists.'})
                cleaned['invoice_number'] = invoice_number
            else:
                cleaned['invoice_number'] = ''

        order = cleaned.get('order')
        gst_type = cleaned.get('gst_type')
        if not gst_type and self.instance.pk:
            gst_type = self.instance.gst_type
        client = None
        if order:
            client = order.client
        elif self.instance.pk:
            client = self.instance.billing_client
        if client:
            if not gst_type or not self._can_override_gst:
                gst_type = resolve_client_gst_type(client)
            cleaned['gst_type'] = gst_type
        elif not gst_type:
            cleaned['gst_type'] = GST_TYPE_INTRA

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        if not self.instance.pk:
            from config.company import COMPANY
            self.fields['hsn_sac'].initial = COMPANY['default_hsn_sac']
            self.fields['unit'].initial = 'Nos'
            self.fields['qty'].initial = 1

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned
        description = (cleaned.get('description') or '').strip()
        if not description:
            cleaned['description'] = ''
            return cleaned
        if not cleaned.get('sl_no'):
            cleaned.pop('sl_no', None)
        if not (cleaned.get('hsn_sac') or '').strip():
            from config.company import COMPANY
            cleaned['hsn_sac'] = COMPANY['default_hsn_sac']
        if not (cleaned.get('unit') or '').strip():
            cleaned['unit'] = 'Nos'
        if cleaned.get('qty') in (None, ''):
            cleaned['qty'] = 1
        if cleaned.get('rate') in (None, ''):
            cleaned['rate'] = 0
        return cleaned


class BaseInvoiceLineFormSet(BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        used_sl = set()
        next_sl = 1
        active = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            description = (form.cleaned_data.get('description') or '').strip()
            if not description:
                continue

            active += 1
            sl_no = form.cleaned_data.get('sl_no')
            if not sl_no:
                while next_sl in used_sl:
                    next_sl += 1
                sl_no = next_sl
                form.cleaned_data['sl_no'] = sl_no

            sl_no = int(sl_no)
            if sl_no in used_sl:
                raise ValidationError(f'Duplicate Sl No {sl_no} on invoice line items.')
            used_sl.add(sl_no)
            next_sl = max(next_sl, sl_no + 1)
            form.instance.sl_no = sl_no

        if active < 1:
            raise ValidationError('Add at least one invoice line item.')





class InvoiceApproveForm(forms.Form):
    approval_remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional approval remarks'}),
        label='Approval Remarks',
    )


class InvoiceRejectForm(forms.Form):
    rejection_reason = forms.ChoiceField(
        choices=[],
        required=True,
        label='Rejection Reason',
    )
    approval_remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Additional comments'}),
        label='Remarks',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from billing.approval import REJECTION_REASON_CHOICES
        self.fields['rejection_reason'].choices = REJECTION_REASON_CHOICES


InvoiceLineItemFormSet = inlineformset_factory(

    Invoice,

    InvoiceLineItem,

    form=InvoiceLineItemForm,

    formset=BaseInvoiceLineFormSet,

    extra=1,

    can_delete=True,

)

