from django import forms
from django.forms import inlineformset_factory

from scheduling.staff_selectors import project_manager_queryset, supervisor_queryset

from .models import Order, OrderAttachment


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'client', 'order_date', 'order_type', 'source',
            'contact_person', 'mobile', 'email',
            'project_site_name', 'site_address', 'description', 'priority',
            'expected_completion_date', 'assigned_project_manager', 'assigned_supervisor',
            'remarks',
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
            'source': 'Source',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_project_manager'].queryset = project_manager_queryset()
        self.fields['assigned_supervisor'].queryset = supervisor_queryset()
        self.fields['assigned_project_manager'].label = 'Project Manager'
        self.fields['assigned_supervisor'].label = 'Team Leader'
        self.fields['assigned_project_manager'].required = False
        self.fields['assigned_supervisor'].required = False
        self.fields['source'].required = False


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
