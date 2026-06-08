from django import forms
from django.forms import inlineformset_factory

from .models import Order, OrderAttachment


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'client', 'order_date', 'order_type', 'project_site_name',
            'site_address', 'description', 'priority',
            'expected_completion_date', 'remarks',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'site_address': forms.Textarea(attrs={'rows': 2}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'site_address': 'Location',
            'expected_completion_date': 'Expected Completion Date (optional)',
            'project_site_name': 'Project / Site Name',
        }


class OrderAttachmentForm(forms.ModelForm):
    class Meta:
        model = OrderAttachment
        fields = ['file', 'caption']


OrderAttachmentFormSet = inlineformset_factory(
    Order,
    OrderAttachment,
    form=OrderAttachmentForm,
    extra=2,
    can_delete=True,
)
