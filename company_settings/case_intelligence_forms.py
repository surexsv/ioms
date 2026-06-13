from django import forms

from company_settings.case_intelligence import CaseIntelligenceSettings


class CaseIntelligenceSettingsForm(forms.ModelForm):
    class Meta:
        model = CaseIntelligenceSettings
        fields = (
            'enquiry_delay_days',
            'survey_delay_days',
            'quotation_followup_days',
            'order_delay_days',
            'wcr_delay_days',
            'invoice_approval_days',
            'payment_followup_days',
        )
