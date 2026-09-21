from django.contrib import admin

from .models import PMObservation, PMObservationHistory, PMObservationOrder, PMObservationSnapshot


class PMObservationSnapshotInline(admin.TabularInline):
    model = PMObservationSnapshot
    extra = 0


class PMObservationOrderInline(admin.TabularInline):
    model = PMObservationOrder
    extra = 0


@admin.register(PMObservation)
class PMObservationAdmin(admin.ModelAdmin):
    list_display = (
        'pm_number', 'client', 'maintenance_type', 'priority',
        'admin_status', 'suggested_due_date', 'created_by', 'created_at',
    )
    list_filter = ('admin_status', 'maintenance_type', 'priority', 'source')
    search_fields = ('pm_number', 'client__name', 'observation', 'equipment_asset')
    inlines = [PMObservationOrderInline, PMObservationSnapshotInline]


@admin.register(PMObservationHistory)
class PMObservationHistoryAdmin(admin.ModelAdmin):
    list_display = ('observation', 'action', 'actor', 'created_at')
    list_filter = ('action',)
