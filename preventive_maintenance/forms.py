from django import forms
from django.forms import inlineformset_factory

from clients.models import Client
from orders.models import Order
from special_projects.models import SpecialProject

from .models import PMObservation, PMObservationSnapshot


class PMObservationForm(forms.ModelForm):
    class Meta:
        model = PMObservation
        fields = [
            'client', 'site_location', 'related_order', 'related_project',
            'system_service', 'equipment_asset',
            'observation', 'recommended_work',
            'maintenance_type', 'priority', 'current_condition', 'potential_impact',
            'suggested_due_date', 'source', 'remarks',
        ]
        widgets = {
            'site_location': forms.TextInput(attrs={'placeholder': 'Site / location'}),
            'system_service': forms.TextInput(attrs={'placeholder': 'e.g. OFC, CCTV, UPS'}),
            'equipment_asset': forms.TextInput(attrs={'placeholder': 'Equipment / asset'}),
            'observation': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What was observed?'}),
            'recommended_work': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Recommended work'}),
            'remarks': forms.Textarea(attrs={'rows': 2}),
            'suggested_due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.all().order_by('name')
        self.fields['related_order'].queryset = Order.objects.select_related('client').order_by('-order_id')
        self.fields['related_order'].required = False
        self.fields['related_order'].label = 'Related Project / Order (optional)'
        self.fields['related_project'].queryset = SpecialProject.objects.select_related(
            'order', 'order__client',
        ).order_by('-created_at')
        self.fields['related_project'].required = False
        self.fields['related_project'].label = 'Related Special Project (optional)'
        self.fields['potential_impact'].required = False
        self.fields['recommended_work'].required = False
        self.fields['current_condition'].required = False


class PMObservationSnapshotForm(forms.ModelForm):
    class Meta:
        model = PMObservationSnapshot
        fields = ['kind', 'file', 'caption']
        widgets = {
            'file': forms.ClearableFileInput(attrs={
                'accept': 'image/*,application/pdf',
                'capture': 'environment',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].required = False
        self.fields['kind'].required = False
        self.fields['caption'].required = False


SnapshotFormSet = inlineformset_factory(
    PMObservation,
    PMObservationSnapshot,
    form=PMObservationSnapshotForm,
    extra=2,
    can_delete=True,
)


class LinkExistingOrderForm(forms.Form):
    order = forms.ModelChoiceField(queryset=Order.objects.none(), label='Existing Order')
    work_item = forms.CharField(max_length=200, required=False, label='Work item')

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Order.objects.select_related('client').order_by('-order_id')
        if client is not None:
            qs = qs.filter(client=client)
        self.fields['order'].queryset = qs


class CreateOrderFromPMForm(forms.Form):
    work_item = forms.CharField(
        max_length=200,
        required=False,
        label='Work item (optional)',
        help_text='If this observation needs more than one Order, name this work item.',
    )
