from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import EstimateBOQ, EstimateBOQLineItem


class EstimateBOQForm(forms.ModelForm):
    class Meta:
        model = EstimateBOQ
        fields = ['enquiry', 'title', 'notes', 'status']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2})}


class EstimateBOQLineForm(forms.ModelForm):
    class Meta:
        model = EstimateBOQLineItem
        fields = ['sl_no', 'item', 'description', 'quantity', 'unit', 'rate']
        widgets = {
            'item': forms.TextInput(attrs={'placeholder': 'Item name'}),
            'description': forms.TextInput(attrs={'placeholder': 'Item / description'}),
            'quantity': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'rate': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'unit': forms.TextInput(attrs={'placeholder': 'Nos'}),
            'sl_no': forms.NumberInput(attrs={'min': '1', 'style': 'width:60px'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        if not self.instance.pk:
            self.fields['unit'].initial = 'Nos'
            self.fields['quantity'].initial = 1
            self.fields['rate'].initial = 0

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned

        item = (cleaned.get('item') or '').strip()
        description = (cleaned.get('description') or '').strip()
        if not item and not description:
            cleaned['item'] = ''
            cleaned['description'] = ''
            return cleaned

        if not item:
            cleaned['item'] = description[:200]
        if not description:
            cleaned['description'] = cleaned['item']

        if not cleaned.get('sl_no'):
            cleaned.pop('sl_no', None)
        if not (cleaned.get('unit') or '').strip():
            cleaned['unit'] = 'Nos'
        if cleaned.get('quantity') in (None, ''):
            cleaned['quantity'] = 1
        if cleaned.get('rate') in (None, ''):
            cleaned['rate'] = 0
        return cleaned


class BaseEstimateBOQLineFormSet(BaseInlineFormSet):
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

            item = (form.cleaned_data.get('item') or '').strip()
            if not item:
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
            raise ValidationError('Add at least one line item.')

    def save(self, commit=True):
        saved = super().save(commit=False)
        if commit:
            for obj in saved:
                obj.save()
            self.save_m2m()
        return saved


EstimateBOQLineFormSet = inlineformset_factory(
    EstimateBOQ,
    EstimateBOQLineItem,
    form=EstimateBOQLineForm,
    formset=BaseEstimateBOQLineFormSet,
    extra=1,
    can_delete=True,
)
