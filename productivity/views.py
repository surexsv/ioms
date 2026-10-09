import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import access_denied_response, module_required
from accounts.models import User
from productivity.activity_logger import log_activity
from productivity.constants import ACT_REPORT_GENERATED
from accounts.permissions import MODULE_PRODUCTIVITY
from productivity.permissions import (
    can_enter_director_mark,
    can_export_reports,
    can_view_activity_log,
    can_view_field_activity_log,
    can_view_full_productivity,
    can_view_gps_dashboard,
    can_view_management_productivity,
    can_view_productivity,
    can_view_team_productivity,
    productivity_scope_users,
)
from productivity.services import (
    activity_report,
    employee_productivity_detail,
    monthly_trend,
    performance_scoreboard,
    personal_monthly_trend,
    productivity_dashboard_kpis,
    save_director_marks,
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
    if not can_view_management_productivity(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    kpis = productivity_dashboard_kpis(year, month)
    trend = monthly_trend(year)
    scope_users = productivity_scope_users(request.user)
    scoreboard_chart = [
        {'name': row['name'], 'score': float(row['score'])}
        for row in kpis['scoreboard'][:10]
    ]
    return render(request, 'productivity/dashboard.html', {
        'kpis': kpis,
        'trend': trend,
        'year': year,
        'month': month,
        'scoreboard_chart': scoreboard_chart,
        'can_full': can_view_full_productivity(request.user),
        'can_team': can_view_team_productivity(request.user),
        'can_activity_log': can_view_activity_log(request.user),
        'can_gps': can_view_gps_dashboard(request.user),
        'can_field_log': can_view_field_activity_log(request.user),
        'can_enter_director_mark': can_enter_director_mark(request.user),
        'employees': scope_users.order_by('first_name', 'username')[:100],
    })


def _posted_director_marks(request):
    """Return (marks, notes, error_message) from a director-mark form."""
    marks = {}
    notes = {}
    for key, value in request.POST.items():
        if not key.startswith('mark-'):
            continue
        try:
            employee_id = int(key.split('-', 1)[1])
        except (TypeError, ValueError):
            return None, None, 'A director mark could not be read.'
        raw = (value or '').strip()
        note = (request.POST.get(f'note-{employee_id}') or '').strip()
        if raw == '':
            marks[employee_id] = None
            notes[employee_id] = ''
            continue
        try:
            mark = Decimal(raw)
        except (InvalidOperation, ValueError):
            return None, None, 'Enter each director mark as a number from 0 to 100.'
        if mark < 0 or mark > 100:
            return None, None, 'Each director mark must be from 0 to 100.'
        marks[employee_id] = mark.quantize(Decimal('0.01'))
        notes[employee_id] = note[:255]
    if not marks:
        return None, None, 'No director marks were submitted.'
    return marks, notes, None


@require_POST
@module_required(MODULE_PRODUCTIVITY)
def save_director_marks_view(request):
    if not can_enter_director_mark(request.user):
        return access_denied_response(request, module_key='productivity')
    year, month = _parse_period(request)
    try:
        year = int(request.POST.get('year', year))
        month = int(request.POST.get('month', month))
    except (TypeError, ValueError):
        year, month = _parse_period(request)
    if month < 1 or month > 12:
        messages.error(request, 'Choose a month from 1 to 12.')
        return redirect(f"{reverse('productivity_dashboard')}?year={year}&month={month}")
    marks, notes, error = _posted_director_marks(request)
    next_employee = request.POST.get('next')
    if error:
        messages.error(request, error)
    else:
        save_director_marks(request.user, year, month, marks, notes)
        messages.success(request, 'Director marks saved. Scores and ranks are updated.')
    if next_employee and str(next_employee).isdigit():
        return redirect(
            f"{reverse('employee_productivity', args=[int(next_employee)])}?year={year}&month={month}"
        )
    return redirect(f"{reverse('productivity_dashboard')}?year={year}&month={month}")


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
        'can_enter_director_mark': can_enter_director_mark(request.user),
    })


@module_required(MODULE_PRODUCTIVITY)
def activity_list(request):
    if not can_view_activity_log(request.user):
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
        writer.writerow([
            'Rank', 'Employee', 'Role', 'Score', 'Director Mark', 'Director Note',
            'Completion %', 'Attendance %',
            'Jobs Completed', 'Activities', 'Reports Submitted', 'Man-Days', 'Hours',
        ])
        for row in performance_scoreboard(year, month):
            writer.writerow([
                row['rank'],
                row['name'],
                row['role_label'],
                row['score'],
                row['director_mark'] if row['director_mark'] is not None else '',
                row['director_mark_note'],
                row['completion_pct'] if row['completion_pct'] is not None else '',
                row['attendance_pct'] if row['attendance_pct'] is not None else '',
                row['completed_jobs'],
                row['activities_count'],
                row['wcr_submitted'],
                row['man_days'],
                row['hours_worked'],
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
    if not can_view_field_activity_log(request.user):
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
        WorkSchedule.objects.select_related('order', 'enquiry'),
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
        from accounts.navigation import redirect_target_after_schedule
        from django.urls import reverse
        target = redirect_target_after_schedule(request.user, schedule)
        if len(target) == 2:
            return redirect(reverse(target[0], args=[target[1]]))
        return redirect(target[0])
    from accounts.navigation import schedule_back_navigation
    return render(request, 'productivity/site_checkin.html', {
        'schedule': schedule,
        'order': schedule.order,
        'enquiry': schedule.enquiry,
        'mode': 'checkin',
        'back_nav': schedule_back_navigation(request.user, schedule),
    })


@module_required(MODULE_PRODUCTIVITY)
def site_check_out_view(request, schedule_pk):
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related('order', 'enquiry'),
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
        from accounts.navigation import redirect_target_after_schedule
        from django.urls import reverse
        target = redirect_target_after_schedule(request.user, schedule)
        if len(target) == 2:
            return redirect(reverse(target[0], args=[target[1]]))
        return redirect(target[0])
    from accounts.navigation import schedule_back_navigation
    return render(request, 'productivity/site_checkin.html', {
        'schedule': schedule,
        'order': schedule.order,
        'enquiry': schedule.enquiry,
        'mode': 'checkout',
        'back_nav': schedule_back_navigation(request.user, schedule),
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
