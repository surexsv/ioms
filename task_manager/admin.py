from django.contrib import admin

from .models import TaskHistory, TeamTask


class TaskHistoryInline(admin.TabularInline):
    model = TaskHistory
    extra = 0
    can_delete = False
    readonly_fields = (
        'action', 'actor', 'remarks', 'from_assignee', 'to_assignee',
        'from_status', 'to_status', 'created_at',
    )


@admin.register(TeamTask)
class TeamTaskAdmin(admin.ModelAdmin):
    list_display = (
        'task_number', 'title', 'status', 'priority', 'assignee',
        'scheduled_on', 'due_on', 'next_reminder_on',
    )
    list_filter = ('status', 'priority')
    search_fields = ('task_number', 'title', 'description', 'latest_remarks')
    raw_id_fields = ('assignee', 'created_by', 'related_order')
    inlines = [TaskHistoryInline]


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'task', 'action', 'actor', 'from_status', 'to_status')
    list_filter = ('action',)
    search_fields = ('task__task_number', 'remarks')
    raw_id_fields = ('task', 'actor', 'from_assignee', 'to_assignee')
