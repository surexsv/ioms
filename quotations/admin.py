from django.contrib import admin
from .models import (
    ServiceRateCard,
    MaterialRateCard,
    RateCardAuditLog,
    QuotationSettings,
    CoveringLetterSettings,
    ProposalTemplate,
    Quotation,
    QuotationMaterialLine,
    QuotationServiceLine,
)


class MaterialLineInline(admin.TabularInline):
    model = QuotationMaterialLine
    extra = 0


class ServiceLineInline(admin.TabularInline):
    model = QuotationServiceLine
    extra = 0


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        'quotation_number', 'client', 'quotation_date', 'status', 'grand_total',
        'authorized_signatory_name',
    )
    list_filter = ('status', 'quotation_date')
    search_fields = ('quotation_number', 'client__name', 'subject')
    inlines = [MaterialLineInline, ServiceLineInline]
    fieldsets = (
        (None, {
            'fields': (
                'quotation_number', 'quotation_date', 'valid_until', 'client',
                'contact_person', 'site_location', 'subject', 'scope_of_work',
                'status', 'grand_total',
            ),
        }),
        ('Authorized Signatory', {
            'fields': (
                'authorized_signatory_name', 'authorized_signatory_designation',
                'signature_image',
            ),
        }),
    )


@admin.register(ServiceRateCard)
class ServiceRateCardAdmin(admin.ModelAdmin):
    list_display = ('service_code', 'service_name', 'rate', 'gst_percent', 'is_active')
    list_filter = ('is_active',)


@admin.register(MaterialRateCard)
class MaterialRateCardAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'item_name', 'brand', 'rate', 'gst_percent', 'is_active')
    list_filter = ('is_active',)


@admin.register(RateCardAuditLog)
class RateCardAuditLogAdmin(admin.ModelAdmin):
    list_display = ('rate_type', 'record_code', 'action', 'revised_at', 'revised_by')
    list_filter = ('rate_type', 'action')


@admin.register(CoveringLetterSettings)
class CoveringLetterSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by')

    def has_add_permission(self, request):
        return not CoveringLetterSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProposalTemplate)
class ProposalTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'is_default', 'updated_at', 'created_by')
    list_filter = ('is_default',)


@admin.register(QuotationSettings)
class QuotationSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'validity_days', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by')

    def has_add_permission(self, request):
        return not QuotationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
