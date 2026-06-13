import csv
from datetime import datetime

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.decorators import access_denied_response, module_required
from accounts.models import User
from productivity.activity_logger import log_activity
from productivity.constants import ACT_REPORT_GENERATED
from accounts.permissions import MODULE_PRODUCTIVITY
from productivity.permissions import (
    can_export_reports,
    can_view_full_productivity,
    can_view_productivity,
    can_view_team_productivity,
    productivity_scope_users,
)
from productivity.services import (
    activity_report,
    employee_productivity_detail,
    monthly_trend,
    productivity_dashboard_kpis,
)
from productivity.gps_dashboard import (
    field_activity_report,
    field_attendance_report,
    gps_dashboard_context,
)
from productivity.site_attendance import site_check_in, site_check_out
from scheduling.models import WorkSchedule
from productivity.permissions import can_view_gps_dashboard, can_view_full_gps


def _parse_period(request):
    try:
        year = int(request.GET.get('year', datetime.now().year))
        month = int(request.GET.get('month', datetime.now().month))
    except (TypeError, ValueError):
        year, month = datetime.now().year, datetime.now().month
    return year, month


@module_required(MODULE_PRODUCTIVITY)
def productivity_dashboard(request):
    if not can_view_productivity(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    kpis = productivity_dashboard_kpis(year, month)
    trend = monthly_trend(year)
    scope_users = productivity_scope_users(request.user)
    return render(request, 'productivity/dashboard.html', {
        'kpis': kpis,
        'trend': trend,
        'year': year,
        'month': month,
        'can_full': can_view_full_productivity(request.user),
        'can_team': can_view_team_productivity(request.user),
        'employees': scope_users.order_by('first_name', 'username')[:100],
    })


@module_required(MODULE_PRODUCTIVITY)
def employee_productivity(request, pk):
    if not can_view_productivity(request.user):
        return access_denied_response(request, module_key='productivity')
    employee = get_object_or_404(User, pk=pk)
    allowed = productivity_scope_users(request.user).filter(pk=pk).exists()
    if not allowed and not request.user.is_superuser:
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    detail = employee_productivity_detail(employee, year, month)
    activities = activity_report(year=year, month=month, employee=employee)[:50]
    return render(request, 'productivity/employee_detail.html', {
        'detail': detail,
        'activities': activities,
        'year': year,
        'month': month,
    })


@module_required(MODULE_PRODUCTIVITY)
def activity_list(request):
    if not can_view_team_productivity(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    dept = request.GET.get('department', '')
    employee_id = request.GET.get('employee')
    employee = None
    if employee_id:
        employee = get_object_or_404(User, pk=employee_id)
    logs = activity_report(department=dept or None, year=year, month=month, employee=employee)
    return render(request, 'productivity/activity_list.html', {
        'logs': logs[:300],
        'year': year,
        'month': month,
        'department': dept,
        'employees': productivity_scope_users(request.user).order_by('username'),
    })


@module_required(MODULE_PRODUCTIVITY)
def export_csv(request):
    if not can_export_reports(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    report_type = request.GET.get('type', 'field')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="productivity_{report_type}_{year}_{month:02d}.csv"'
    writer = csv.writer(response)
    if report_type == 'activities':
        writer.writerow(['Date', 'Employee', 'Department', 'Activity', 'Document', 'Remarks'])
        for log in activity_report(year=year, month=month):
            writer.writerow([
                log.activity_date,
                log.employee.get_full_name() if log.employee else '',
                log.get_department_display(),
                log.get_activity_type_display(),
                log.related_document,
                log.remarks,
            ])
    else:
        writer.writerow(['Employee', 'Role', 'Man-Days', 'Hours', 'Jobs Attended'])
        from productivity.calculator import field_productivity_ranking
        for row in field_productivity_ranking(year, month):
            writer.writerow([
                row.get('employee__username'),
                row.get('employee__role'),
                row.get('total_man_days'),
                row.get('total_hours'),
                row.get('job_count'),
            ])
    log_activity(request.user, ACT_REPORT_GENERATED, related_document=f'CSV {report_type} {year}-{month}')
    return response


@require_GET
@module_required(MODULE_PRODUCTIVITY)
def export_pdf(request):
    """Print-friendly HTML report (PDF via browser print)."""
    if not can_export_reports(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    kpis = productivity_dashboard_kpis(year, month)
    log_activity(request.user, ACT_REPORT_GENERATED, related_document=f'PDF {year}-{month}')
    return render(request, 'productivity/report_print.html', {
        'kpis': kpis,
        'year': year,
        'month': month,
        'generated_at': datetime.now(),
    })


@module_required(MODULE_PRODUCTIVITY)
def gps_dashboard(request):
    if not can_view_gps_dashboard(request.user):
        return access_denied_response(request, module_key='productivity')
    ctx = gps_dashboard_context(request.user)
    ctx['can_full_gps'] = can_view_full_gps(request.user)
    return render(request, 'productivity/gps_dashboard.html', ctx)


@module_required(MODULE_PRODUCTIVITY)
def field_activity_list(request):
    if not can_view_team_productivity(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    action = request.GET.get('action', '')
    logs = field_activity_report(year=year, month=month, action_type=action or None)
    if not can_view_full_gps(request.user):
        scope = productivity_scope_users(request.user)
        logs = logs.filter(employee__in=scope)
    from productivity.field_constants import FIELD_ACTION_CHOICES
    return render(request, 'productivity/field_activity_list.html', {
        'logs': logs[:400],
        'year': year,
        'month': month,
        'action_filter': action,
        'action_choices': FIELD_ACTION_CHOICES,
    })


@module_required(MODULE_PRODUCTIVITY)
def site_check_in_view(request, schedule_pk):
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related('order'),
        pk=schedule_pk,
    )
    if request.method == 'POST':
        att, ok, msg = site_check_in(
            schedule, request.user, request=request,
            site_photo=request.FILES.get('site_photo'),
        )
        if ok:
            from productivity.calculator import recalculate_daily_snapshot
            recalculate_daily_snapshot(request.user)
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
        return redirect('order_detail', pk=schedule.order_id)
    return render(request, 'productivity/site_checkin.html', {
        'schedule': schedule,
        'order': schedule.order,
        'mode': 'checkin',
    })


@module_required(MODULE_PRODUCTIVITY)
def site_check_out_view(request, schedule_pk):
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related('order'),
        pk=schedule_pk,
    )
    if request.method == 'POST':
        att, ok, msg = site_check_out(
            schedule, request.user, request=request,
            work_photo=request.FILES.get('work_photo'),
        )
        if ok:
            from productivity.calculator import recalculate_daily_snapshot
            recalculate_daily_snapshot(request.user)
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
        return redirect('order_detail', pk=schedule.order_id)
    return render(request, 'productivity/site_checkin.html', {
        'schedule': schedule,
        'order': schedule.order,
        'mode': 'checkout',
    })


@module_required(MODULE_PRODUCTIVITY)
def export_field_csv(request):
    if not can_export_reports(request.user) and not can_view_gps_dashboard(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    report = request.GET.get('report', 'attendance')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="field_{report}_{year}_{month:02d}.csv"'
    writer = csv.writer(response)
    if report == 'gps':
        writer.writerow(['Date', 'Time', 'Employee', 'Action', 'Latitude', 'Longitude', 'Address'])
        for log in field_activity_report(year=year, month=month):
            writer.writerow([
                log.activity_date, log.activity_time,
                log.employee.get_full_name() if log.employee else '',
                log.action_label, log.latitude, log.longitude, log.address,
            ])
    else:
        writer.writerow(['Employee', 'Schedule', 'Check-In', 'Check-Out', 'In Address', 'Out Address'])
        for att in field_attendance_report(year=year, month=month):
            writer.writerow([
                att.employee.get_full_name() if att.employee else '',
                att.schedule.schedule_number,
                att.check_in_at, att.check_out_at,
                att.check_in_address, att.check_out_address,
            ])
    log_activity(request.user, ACT_REPORT_GENERATED, related_document=f'Field CSV {report}')
    return response
