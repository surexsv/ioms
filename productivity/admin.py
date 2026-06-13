from django.contrib import admin
from productivity.models import (
    EmployeeActivityLog,
    EmployeeProductivityDaily,
    EmployeeProductivitySnapshot,
    FieldActivityLog,
    GPSLocationRecord,
    ScheduleSiteAttendance,
    WCRTeamParticipant,
)


@admin.register(EmployeeActivityLog)
class EmployeeActivityLogAdmin(admin.ModelAdmin):
    list_display = ('activity_date', 'employee', 'department', 'activity_type', 'related_document', 'status')
    list_filter = ('department', 'activity_type', 'activity_date')
    search_fields = ('related_document', 'remarks', 'employee__username')


@admin.register(GPSLocationRecord)
class GPSLocationRecordAdmin(admin.ModelAdmin):
    list_display = ('captured_at', 'employee', 'action_type', 'latitude', 'longitude', 'address')
    list_filter = ('action_type', 'captured_at')
    search_fields = ('address', 'employee__username')


@admin.register(FieldActivityLog)
class FieldActivityLogAdmin(admin.ModelAdmin):
    list_display = ('activity_date', 'employee', 'action_type', 'order', 'address')
    list_filter = ('action_type', 'activity_date')
    search_fields = ('address', 'remarks', 'employee__username')


@admin.register(ScheduleSiteAttendance)
class ScheduleSiteAttendanceAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'employee', 'check_in_at', 'check_out_at', 'check_in_address')
    list_filter = ('check_in_at',)


@admin.register(WCRTeamParticipant)
class WCRTeamParticipantAdmin(admin.ModelAdmin):
    list_display = ('wcr', 'employee', 'participant_role', 'attended', 'hours_worked', 'man_days')
    list_filter = ('participant_role', 'attended')


@admin.register(EmployeeProductivitySnapshot)
class EmployeeProductivitySnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'period_year', 'period_month',
        'man_days', 'hours_worked', 'jobs_attended', 'completion_percent',
    )
    list_filter = ('period_year', 'period_month')


@admin.register(EmployeeProductivityDaily)
class EmployeeProductivityDailyAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period_date', 'man_days', 'hours_worked', 'site_check_ins')
    list_filter = ('period_date',)
