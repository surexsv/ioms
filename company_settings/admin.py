from django.contrib import admin

from .models import CompanySettings
from .field_ops import FieldOperationsSettings
from .case_intelligence import CaseIntelligenceSettings


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by')

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FieldOperationsSettings)
class FieldOperationsSettingsAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 'gps_tracking_enabled', 'checkin_checkout_enabled',
        'productivity_tracking_enabled', 'auto_survey_schedule_enabled',
    )

    def has_add_permission(self, request):
        return not FieldOperationsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CaseIntelligenceSettings)
class CaseIntelligenceSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'enquiry_delay_days', 'survey_delay_days', 'quotation_followup_days',
        'order_delay_days', 'wcr_delay_days', 'invoice_approval_days',
        'payment_followup_days', 'updated_at',
    )

    def has_add_permission(self, request):
        return not CaseIntelligenceSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
