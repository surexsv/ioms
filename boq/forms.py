from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES
from config.company import COMPANY
from orders.models import Order

from .models import BOQ, BOQLineItem


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
        for field in self.fields.values():
            field.required = False
        if not self.instance.pk:
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
            cleaned['hsn_sac'] = COMPANY['default_hsn_sac']
        if not (cleaned.get('unit') or '').strip():
            cleaned['unit'] = 'Nos'
        if cleaned.get('qty') in (None, ''):
            cleaned['qty'] = 1
        return cleaned


class BaseBOQLineItemFormSet(BaseInlineFormSet):
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
                raise ValidationError(f'Duplicate Sl No {sl_no} on line items.')
            used_sl.add(sl_no)
            next_sl = max(next_sl, sl_no + 1)
            form.instance.sl_no = sl_no

        if active < 1:
            raise ValidationError('Add at least one BOQ line item.')

    def save(self, commit=True):
        saved = super().save(commit=False)
        if commit:
            for obj in saved:
                obj.save()
            self.save_m2m()
        return saved


BOQLineItemFormSet = inlineformset_factory(
    BOQ,
    BOQLineItem,
    form=BOQLineItemForm,
    formset=BaseBOQLineItemFormSet,
    extra=1,
    can_delete=True,
)
