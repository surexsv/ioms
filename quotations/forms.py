from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .covering_letter_utils import get_default_covering_letter_content
from .models import (
    Quotation,
    QuotationMaterialLine,
    QuotationServiceLine,
    QuotationSettings,
    CoveringLetterSettings,
    ProposalTemplate,
    ServiceRateCard,
    MaterialRateCard,
)
from company_settings.form_utils import AuthorizedSignatoryFormMixin
from company_settings.signatory import SIGNATORY_FIELD_NAMES

from .settings_utils import build_default_terms_text


class QuotationForm(AuthorizedSignatoryFormMixin, forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            'quotation_date', 'valid_until', 'client', 'contact_person',
            'site_location', 'subject', 'reference_number', 'scope_of_work',
            'proposal_template', 'covering_letter_subject', 'covering_letter_body',
            'include_covering_letter', 'include_terms', 'include_company_seal',
            'include_signature',
            'terms_and_conditions', 'remarks',
            *SIGNATORY_FIELD_NAMES,
        ]
        widgets = {
            'quotation_date': forms.DateInput(attrs={'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'type': 'date'}),
            'site_location': forms.Textarea(attrs={'rows': 2}),
            'scope_of_work': forms.Textarea(attrs={'rows': 4}),
            'covering_letter_subject': forms.TextInput(attrs={'class': 'cl-subject-input'}),
            'covering_letter_body': forms.HiddenInput(),
            'terms_and_conditions': forms.Textarea(attrs={'rows': 4}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ProposalTemplate.ensure_seed_templates()
        self.fields['proposal_template'].queryset = ProposalTemplate.objects.order_by('name')
        self.fields['proposal_template'].required = False
        self.fields['proposal_template'].empty_label = '— Use default settings —'

        if not self.instance.pk:
            master = QuotationSettings.get_solo()
            default_template = ProposalTemplate.get_default()
            if not self.initial.get('terms_and_conditions'):
                self.initial['terms_and_conditions'] = build_default_terms_text(master)
            if not self.initial.get('valid_until'):
                base_date = self.initial.get('quotation_date') or timezone.localdate()
                self.initial['valid_until'] = base_date + timedelta(days=master.validity_days)
            if default_template and not self.initial.get('proposal_template'):
                self.initial['proposal_template'] = default_template
            if not self.initial.get('covering_letter_subject') or not self.initial.get('covering_letter_body'):
                template = self.initial.get('proposal_template') or default_template
                subject, body = get_default_covering_letter_content(template=template)
                self.initial.setdefault('covering_letter_subject', subject)
                self.initial.setdefault('covering_letter_body', body)


class MaterialLineForm(forms.ModelForm):
    class Meta:
        model = QuotationMaterialLine
        fields = [
            'material_item', 'description', 'quantity', 'unit',
            'unit_rate', 'gst_percent',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material_item'].queryset = MaterialRateCard.objects.filter(is_active=True)
        self.fields['material_item'].required = False
        self.fields['material_item'].empty_label = '— Select material —'


class ServiceLineForm(forms.ModelForm):
    class Meta:
        model = QuotationServiceLine
        fields = [
            'service_item', 'description', 'quantity', 'unit',
            'unit_rate', 'gst_percent',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_item'].queryset = ServiceRateCard.objects.filter(is_active=True)
        self.fields['service_item'].required = False
        self.fields['service_item'].empty_label = '— Select service —'


MaterialLineFormSet = inlineformset_factory(
    Quotation,
    QuotationMaterialLine,
    form=MaterialLineForm,
    extra=2,
    can_delete=True,
)

ServiceLineFormSet = inlineformset_factory(
    Quotation,
    QuotationServiceLine,
    form=ServiceLineForm,
    extra=2,
    can_delete=True,
)


class ServiceRateCardForm(forms.ModelForm):
    class Meta:
        model = ServiceRateCard
        fields = [
            'service_code', 'service_name', 'description', 'unit',
            'rate', 'gst_percent', 'is_active',
        ]
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class MaterialRateCardForm(forms.ModelForm):
    class Meta:
        model = MaterialRateCard
        fields = [
            'item_code', 'item_name', 'description', 'brand', 'unit',
            'rate', 'gst_percent', 'is_active',
        ]
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


class CoveringLetterSettingsForm(forms.ModelForm):
    class Meta:
        model = CoveringLetterSettings
        fields = [
            'company_introduction',
            'default_subject',
            'default_body',
            'closing_paragraph',
        ]
        widgets = {
            'company_introduction': forms.Textarea(attrs={'rows': 3}),
            'default_subject': forms.TextInput(),
            'default_body': forms.Textarea(attrs={'rows': 12}),
            'closing_paragraph': forms.Textarea(attrs={'rows': 2}),
        }


class ProposalTemplateForm(forms.ModelForm):
    class Meta:
        model = ProposalTemplate
        fields = ['name', 'subject', 'body', 'is_default']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 14}),
        }


class QuotationSettingsForm(forms.ModelForm):
    class Meta:
        model = QuotationSettings
        fields = [
            'terms_and_conditions',
            'payment_terms',
            'validity_period',
            'validity_days',
            'bank_details',
            'footer_notes',
        ]
        widgets = {
            'terms_and_conditions': forms.Textarea(attrs={'rows': 14}),
            'payment_terms': forms.Textarea(attrs={'rows': 5}),
            'validity_period': forms.Textarea(attrs={'rows': 3}),
            'bank_details': forms.Textarea(attrs={'rows': 6}),
            'footer_notes': forms.Textarea(attrs={'rows': 3}),
        }


class QuotationSearchForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    client = forms.ModelChoiceField(
        queryset=None, required=False, empty_label='All clients',
    )
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + list(Quotation.STATUS_CHOICES))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        from clients.models import Client
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.order_by('name')
