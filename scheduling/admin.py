from django.contrib import admin

from .models import WorkSchedule


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'schedule_number', 'order', 'status',
        'scheduled_start_date', 'scheduled_end_date', 'created_at',
    )
    list_filter = ('status',)
    search_fields = ('schedule_number', 'order__order_no')
    filter_horizontal = ('assigned_engineers',)
