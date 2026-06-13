from django.contrib import admin
from .models import Attendance, AttendancePhoto, AttendanceAuditLog


class AttendancePhotoInline(admin.TabularInline):
    model = AttendancePhoto
    extra = 0
    readonly_fields = ('photo_type', 'captured_at', 'latitude', 'longitude')


class AttendanceAuditLogInline(admin.TabularInline):
    model = AttendanceAuditLog
    extra = 0
    readonly_fields = ('action', 'performed_by', 'user_role', 'ip_address', 'created_at')
    can_delete = False


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'attendance_date', 'status',
        'check_in_time', 'check_out_time', 'working_hours',
        'location_short', 'is_corrected', 'updated_at',
    )
    list_filter = ('status', 'attendance_date', 'is_corrected', 'employee__role')
    search_fields = (
        'employee__username', 'employee__first_name',
        'employee__last_name', 'location', 'check_out_location', 'notes',
    )
    date_hierarchy = 'attendance_date'
    autocomplete_fields = ['employee', 'corrected_by']
    readonly_fields = ('working_hours', 'created_at', 'updated_at')
    inlines = [AttendancePhotoInline, AttendanceAuditLogInline]
    fieldsets = (
        (None, {
            'fields': (
                'employee', 'attendance_date', 'status',
                'check_in_time', 'check_out_time', 'check_in_at', 'check_out_at',
                'working_hours', 'is_corrected', 'corrected_by',
            ),
        }),
        ('Check-In Location', {
            'fields': (
                'location', 'latitude', 'longitude', 'check_in_maps_link',
                'device_info_in', 'ip_address_in', 'check_in_remarks',
            ),
        }),
        ('Check-Out Location', {
            'fields': (
                'check_out_location', 'check_out_latitude', 'check_out_longitude',
                'check_out_maps_link', 'device_info_out', 'ip_address_out', 'check_out_remarks',
            ),
        }),
        ('Notes', {'fields': ('notes',)}),
        ('Audit', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Location')
    def location_short(self, obj):
        if not obj.location:
            return '—'
        return obj.location[:50] + ('…' if len(obj.location) > 50 else '')


@admin.register(AttendancePhoto)
class AttendancePhotoAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'employee', 'photo_type', 'captured_at')
    list_filter = ('photo_type', 'captured_at')
    search_fields = ('employee__username', 'attendance__employee__username')


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'attendance', 'performed_by', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('action', 'performed_by__username', 'remarks')
    readonly_fields = (
        'attendance', 'action', 'performed_by', 'user_role',
        'ip_address', 'device_info', 'latitude', 'longitude', 'remarks', 'created_at',
    )
