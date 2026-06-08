from django.contrib import admin
from django.utils.html import format_html
from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'attendance_date', 'status',
        'check_in_time', 'check_out_time', 'working_hours',
        'location_short', 'updated_at',
    )
    list_filter = ('status', 'attendance_date', 'employee__role')
    search_fields = (
        'employee__username', 'employee__first_name',
        'employee__last_name', 'location', 'notes',
    )
    date_hierarchy = 'attendance_date'
    autocomplete_fields = ['employee']
    readonly_fields = ('working_hours', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'employee', 'attendance_date', 'status',
                'check_in_time', 'check_out_time', 'working_hours',
            ),
        }),
        ('Location', {
            'fields': ('location', 'latitude', 'longitude'),
        }),
        ('Notes', {
            'fields': ('notes',),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Location')
    def location_short(self, obj):
        if not obj.location:
            return '—'
        return obj.location[:50] + ('…' if len(obj.location) > 50 else '')
