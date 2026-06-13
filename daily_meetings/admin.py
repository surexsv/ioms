from django.contrib import admin
from .models import (
    AgendaTemplateItem, DailyMeeting, DailyMeetingsSettings,
    ManagementMessage, MeetingActionItem, MeetingAgendaItem,
    MeetingAttendance, MeetingDiscussion, MeetingOpenItemSnapshot,
    OpenItemRegister,
)


@admin.register(DailyMeetingsSettings)
class DailyMeetingsSettingsAdmin(admin.ModelAdmin):
    list_display = ('meeting_start_time', 'default_meeting_type', 'late_grace_minutes', 'updated_at')


@admin.register(AgendaTemplateItem)
class AgendaTemplateItemAdmin(admin.ModelAdmin):
    list_display = ('sort_order', 'title', 'is_active', 'is_system')
    list_display_links = ('title',)
    list_editable = ('sort_order', 'is_active')


class MeetingAgendaItemInline(admin.TabularInline):
    model = MeetingAgendaItem
    extra = 0


class MeetingAttendanceInline(admin.TabularInline):
    model = MeetingAttendance
    extra = 0
    autocomplete_fields = ['employee']


class MeetingDiscussionInline(admin.StackedInline):
    model = MeetingDiscussion
    extra = 0


class MeetingActionItemInline(admin.TabularInline):
    model = MeetingActionItem
    extra = 0
    fk_name = 'meeting'


@admin.register(DailyMeeting)
class DailyMeetingAdmin(admin.ModelAdmin):
    list_display = ('meeting_number', 'meeting_date', 'meeting_type', 'status', 'conducted_by', 'department')
    list_filter = ('status', 'meeting_type', 'meeting_date')
    search_fields = ('meeting_number', 'topic_of_day')
    date_hierarchy = 'meeting_date'
    inlines = [MeetingAgendaItemInline, MeetingAttendanceInline, MeetingDiscussionInline, MeetingActionItemInline]


@admin.register(OpenItemRegister)
class OpenItemRegisterAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'title', 'status', 'owner', 'target_date', 'is_recurring')
    list_filter = ('status', 'is_recurring')


@admin.register(MeetingActionItem)
class MeetingActionItemAdmin(admin.ModelAdmin):
    list_display = ('action_number', 'description', 'assigned_to', 'target_date', 'priority', 'status')
    list_filter = ('status', 'priority')
    search_fields = ('action_number', 'description')


@admin.register(ManagementMessage)
class ManagementMessageAdmin(admin.ModelAdmin):
    list_display = ('message_date', 'category', 'meeting', 'created_by')
    list_filter = ('category',)
