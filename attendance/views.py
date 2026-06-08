from datetime import date

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from accounts.decorators import module_required, access_denied_response
from accounts.permissions import MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF, can_manage_attendance
from accounts.models import User
from .models import Attendance
from .forms import AttendanceForm, AttendanceFilterForm, CheckInForm, ReportMonthForm
from .services import (
    today_stats, daily_report, monthly_report, employee_summary,
    active_employees, employee_month_stats,
)

FIELD_ROLES = ('ENGINEER', 'Technician', 'Supervisor')


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_dashboard(request):
    report_date = request.GET.get('date')
    if report_date:
        try:
            report_date = date.fromisoformat(report_date)
        except ValueError:
            report_date = date.today()
    else:
        report_date = date.today()

    stats = today_stats(report_date)
    recent = Attendance.objects.select_related('employee').order_by(
        '-attendance_date', '-check_in_time'
    )[:15]

    return render(request, 'attendance/dashboard.html', {
        'stats': stats,
        'recent': recent,
        'report_date': report_date,
    })


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_list(request):

    qs = Attendance.objects.select_related('employee').order_by('-attendance_date')
    form = AttendanceFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('employee'):
            qs = qs.filter(employee=form.cleaned_data['employee'])
        if form.cleaned_data.get('date_from'):
            qs = qs.filter(attendance_date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data.get('date_to'):
            qs = qs.filter(attendance_date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data.get('status'):
            qs = qs.filter(status=form.cleaned_data['status'])

    return render(request, 'attendance/attendance_list.html', {
        'records': qs[:200],
        'filter_form': form,
    })


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_create(request):
    if request.method == 'POST':
        form = AttendanceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance record saved.')
            return redirect('attendance_list')
    else:
        form = AttendanceForm(initial={'attendance_date': timezone.localdate()})
    return render(request, 'attendance/attendance_form.html', {
        'form': form, 'title': 'Add Attendance',
    })


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_edit(request, pk):
    record = get_object_or_404(Attendance, pk=pk)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance updated.')
            return redirect('attendance_list')
    else:
        form = AttendanceForm(instance=record)
    return render(request, 'attendance/attendance_form.html', {
        'form': form, 'title': 'Edit Attendance', 'record': record,
    })


@module_required(MODULE_ATTENDANCE_SELF)
def my_attendance(request):
    today = timezone.localdate()
    record = Attendance.objects.filter(
        employee=request.user, attendance_date=today,
    ).first()
    month_stats = employee_month_stats(request.user)
    history = Attendance.objects.filter(employee=request.user).order_by('-attendance_date')[:30]
    return render(request, 'attendance/my_attendance.html', {
        'today_record': record,
        'month_stats': month_stats,
        'history': history,
        'is_field': request.user.role in FIELD_ROLES,
    })


@module_required(MODULE_ATTENDANCE_SELF)
def check_in(request):
    today = timezone.localdate()
    record, _ = Attendance.objects.get_or_create(
        employee=request.user,
        attendance_date=today,
        defaults={'status': 'PRESENT'},
    )
    if record.check_in_time:
        messages.info(request, f'Already checked in at {record.check_in_time.strftime("%H:%M")}.')
        return redirect('my_attendance')

    if request.method == 'POST':
        form = CheckInForm(request.POST)
        if form.is_valid():
            now = timezone.localtime().time()
            record.check_in_time = now
            record.status = 'PRESENT'
            record.location = form.cleaned_data.get('location', '')
            record.latitude = form.cleaned_data.get('latitude')
            record.longitude = form.cleaned_data.get('longitude')
            record.save()
            messages.success(request, f'Checked in at {now.strftime("%H:%M")}.')
            return redirect('my_attendance')
    else:
        form = CheckInForm()

    return render(request, 'attendance/check_in.html', {'form': form, 'record': record})


@module_required(MODULE_ATTENDANCE_SELF)
def check_out(request):
    today = timezone.localdate()
    record = Attendance.objects.filter(
        employee=request.user, attendance_date=today,
    ).first()
    if not record or not record.check_in_time:
        messages.error(request, 'Please check in first.')
        return redirect('my_attendance')
    if record.check_out_time:
        messages.info(request, 'Already checked out.')
        return redirect('my_attendance')

    if request.method == 'POST':
        now = timezone.localtime().time()
        record.check_out_time = now
        record.save()
        messages.success(request, f'Checked out at {now.strftime("%H:%M")}. Working hours: {record.working_hours}h')
        return redirect('my_attendance')

    return render(request, 'attendance/check_out.html', {'record': record})


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_daily(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    data = daily_report(report_date)
    return render(request, 'attendance/report_daily.html', data)


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_monthly(request):
    form = ReportMonthForm(request.GET or None)
    year, month = date.today().year, date.today().month
    if form.is_valid():
        year = form.cleaned_data['year']
        month = form.cleaned_data['month']
    data = monthly_report(year, month)
    data['form'] = form
    return render(request, 'attendance/report_monthly.html', data)


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_employee(request):
    employees = active_employees()
    employee_id = request.GET.get('employee')
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    employee = None
    summary = None
    if employee_id:
        employee = get_object_or_404(User, pk=employee_id)
        summary = employee_summary(employee, year, month)
    return render(request, 'attendance/report_employee.html', {
        'employees': employees,
        'selected_employee': employee,
        'summary': summary,
        'year': year,
        'month': month,
    })
