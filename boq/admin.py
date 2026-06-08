from django.contrib import admin
from .models import BOQ, BOQLineItem


class BOQLineItemInline(admin.TabularInline):
    model = BOQLineItem
    extra = 1


@admin.register(BOQ)
class BOQAdmin(admin.ModelAdmin):
    list_display = ('boq_number', 'order', 'status', 'created_at', 'verified_at')
    list_filter = ('status',)
    inlines = [BOQLineItemInline]
    fieldsets = (
        (None, {'fields': ('order', 'boq_number', 'status', 'notes', 'created_by', 'verified_by')}),
        ('Authorized Signatory', {
            'fields': (
                'authorized_signatory_name', 'authorized_signatory_designation',
                'signature_image',
            ),
        }),
    )
