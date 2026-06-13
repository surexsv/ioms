from django import forms

from company_settings.field_ops import FieldOperationsSettings


class FieldOperationsSettingsForm(forms.ModelForm):
    class Meta:
        model = FieldOperationsSettings
        fields = [
            'gps_tracking_enabled',
            'checkin_checkout_enabled',
            'productivity_tracking_enabled',
            'site_photos_enabled',
            'device_tracking_enabled',
            'auto_survey_schedule_enabled',
        ]
