from django import forms

from .permissions import can_edit_document_signatory
from .signatory import SIGNATORY_FIELD_NAMES


SIGNATORY_FORM_WIDGETS = {
    'authorized_signatory_name': forms.TextInput(attrs={
        'placeholder': 'e.g. Surex S V',
    }),
    'authorized_signatory_designation': forms.TextInput(attrs={
        'placeholder': 'e.g. Director',
    }),
}


class AuthorizedSignatoryFormMixin:
    """Mixin for ModelForms — applies signatory fields and RBAC."""

    def __init__(self, *args, user=None, **kwargs):
        self._signatory_editable = can_edit_document_signatory(user)
        super().__init__(*args, **kwargs)
        for field_name, widget in SIGNATORY_FORM_WIDGETS.items():
            if field_name in self.fields:
                self.fields[field_name].widget = widget
                self.fields[field_name].required = False
        if not self._signatory_editable:
            for field_name in SIGNATORY_FIELD_NAMES:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def clean(self):
        cleaned = super().clean()
        if not self._signatory_editable and getattr(self.instance, 'pk', None):
            for field_name in SIGNATORY_FIELD_NAMES:
                if field_name in self.fields:
                    cleaned[field_name] = getattr(self.instance, field_name)
        return cleaned
