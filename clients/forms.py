from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'company_type', 'gst_number',
            'address', 'contact_person', 'phone',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
