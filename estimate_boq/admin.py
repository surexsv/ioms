from django.contrib import admin
from .models import EstimateBOQ, EstimateBOQLineItem


class EstimateBOQLineInline(admin.TabularInline):
    model = EstimateBOQLineItem
    extra = 1


@admin.register(EstimateBOQ)
class EstimateBOQAdmin(admin.ModelAdmin):
    list_display = ('estimate_boq_number', 'enquiry', 'status', 'created_at')
    inlines = [EstimateBOQLineInline]
