from django import forms

from billing.gst import gstin_state_code, pan_from_gstin, state_name_from_code

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'company_type',
            'gst_number', 'pan_number', 'state', 'state_code', 'gst_type',
            'address', 'contact_person', 'phone',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'gst_type': forms.Select(),
            'gst_number': forms.TextInput(attrs={'placeholder': 'e.g. 32AABCU9603R1Z5'}),
            'pan_number': forms.TextInput(attrs={'placeholder': 'e.g. AABCU9603R', 'maxlength': '10'}),
            'state_code': forms.TextInput(attrs={'placeholder': 'e.g. 32', 'maxlength': '2'}),
        }

    def clean(self):
        cleaned = super().clean()
        gst_number = (cleaned.get('gst_number') or '').strip().upper()
        cleaned['gst_number'] = gst_number

        state_code = (cleaned.get('state_code') or '').strip()
        if not state_code and gst_number:
            state_code = gstin_state_code(gst_number)
            cleaned['state_code'] = state_code

        state = (cleaned.get('state') or '').strip()
        if not state and state_code:
            inferred = state_name_from_code(state_code)
            if inferred:
                cleaned['state'] = inferred

        pan_number = (cleaned.get('pan_number') or '').strip().upper()
        if not pan_number and gst_number:
            pan_number = pan_from_gstin(gst_number)
        cleaned['pan_number'] = pan_number

        return cleaned

    def save(self, commit=True):
        client = super().save(commit=False)
        client.sync_gst_metadata(save=False)
        if commit:
            client.save()
        return client
