from django.contrib import admin

from .models import (
    DailyExpenseLine,
    DailyLabourLine,
    DailyMaterialLine,
    DailyMedia,
    DailyServiceLine,
    ProjectDailyLog,
    SpecialProject,
)


class LabourInline(admin.TabularInline):
    model = DailyLabourLine
    extra = 0


class MaterialInline(admin.TabularInline):
    model = DailyMaterialLine
    extra = 0


class ServiceInline(admin.TabularInline):
    model = DailyServiceLine
    extra = 0


class ExpenseInline(admin.TabularInline):
    model = DailyExpenseLine
    extra = 0


class MediaInline(admin.TabularInline):
    model = DailyMedia
    extra = 0


@admin.register(SpecialProject)
class SpecialProjectAdmin(admin.ModelAdmin):
    list_display = (
        'project_number', 'name', 'order', 'status',
        'overall_progress_pct', 'budget', 'project_manager', 'updated_at',
    )
    list_filter = ('status', 'category')
    search_fields = ('project_number', 'name', 'order__order_no', 'order__client__name')
    raw_id_fields = ('order', 'project_manager', 'created_by')


@admin.register(ProjectDailyLog)
class ProjectDailyLogAdmin(admin.ModelAdmin):
    list_display = ('project', 'log_date', 'mentor', 'daily_progress_pct', 'created_by')
    list_filter = ('log_date',)
    search_fields = ('project__project_number', 'work_description')
    inlines = [LabourInline, MaterialInline, ServiceInline, ExpenseInline, MediaInline]
