from datetime import date

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from accounts.decorators import module_required, access_denied_response
from accounts.permissions import MODULE_ATTENDANCE_MANAGE, MODULE_ATTENDANCE_SELF, MODULE_ATTENDANCE_TEAM, can_manage_attendance
from accounts.models import User
from attendance.audit import log_attendance_event
from attendance.permissions import (
    can_mark_own_attendance,
    can_correct_attendance,
    can_edit_attendance_records,
    user_requires_attendance,
)
from attendance.utils import (
    attendance_now, get_client_ip, get_device_info,
    maps_link, reverse_geocode,
)
from .models import Attendance, AttendancePhoto
from .forms import (
    AttendanceForm, AttendanceFilterForm, CheckInForm, CheckOutForm, ReportMonthForm,
)
from .services import (
    today_stats, daily_report, monthly_report, employee_summary,
    active_employees, employee_month_stats, today_widget,
    employees_for_manager, absent_report, late_report, leave_report,
    location_report, photo_verification_report, department_report,
)


def _require_attendance_marking(request):
    if not can_mark_own_attendance(request.user):
        return access_denied_response(request, module_key='attendance')
    return None


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
        '-attendance_date', '-check_in_time',
    )[:15]

    return render(request, 'attendance/dashboard.html', {
        'stats': stats,
        'recent': recent,
        'report_date': report_date,
    })


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_list(request):
    qs = Attendance.objects.select_related('employee').prefetch_related('photos').order_by('-attendance_date')
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
            record = form.save(commit=False)
            if can_correct_attendance(request.user):
                record.is_corrected = True
                record.corrected_by = request.user
            record.save()
            log_attendance_event('MANUAL_CREATE', attendance=record, user=request.user, request=request)
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
            record = form.save(commit=False)
            if can_correct_attendance(request.user):
                record.is_corrected = True
                record.corrected_by = request.user
            record.save()
            log_attendance_event('MANUAL_EDIT', attendance=record, user=request.user, request=request)
            messages.success(request, 'Attendance updated.')
            return redirect('attendance_list')
    else:
        form = AttendanceForm(instance=record)
    return render(request, 'attendance/attendance_form.html', {
        'form': form, 'title': 'Edit Attendance', 'record': record,
    })


@module_required(MODULE_ATTENDANCE_SELF)
def my_attendance(request):
    widget = today_widget(request.user)
    month_stats = employee_month_stats(request.user)
    history = Attendance.objects.filter(employee=request.user).order_by('-attendance_date')[:30]
    return render(request, 'attendance/my_attendance.html', {
        'today_record': widget['record'],
        'month_stats': month_stats,
        'history': history,
        'widget': widget,
        'attendance_required': user_requires_attendance(request.user),
    })


@module_required(MODULE_ATTENDANCE_SELF)
def check_in(request):
    denied = _require_attendance_marking(request)
    if denied:
        return denied

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
        form = CheckInForm(request.POST, request.FILES)
        if form.is_valid():
            now = attendance_now()
            lat = form.cleaned_data['latitude']
            lng = form.cleaned_data['longitude']
            address = form.cleaned_data.get('location') or reverse_geocode(lat, lng)

            record.check_in_time = now.time()
            record.check_in_at = now
            record.status = 'PRESENT'
            record.location = address
            record.latitude = lat
            record.longitude = lng
            record.check_in_maps_link = maps_link(lat, lng)
            record.device_info_in = get_device_info(request)
            record.ip_address_in = get_client_ip(request) or None
            record.check_in_remarks = form.cleaned_data.get('remarks', '')
            record.save()

            AttendancePhoto.objects.create(
                attendance=record,
                employee=request.user,
                photo_type=AttendancePhoto.TYPE_CHECK_IN,
                image=form.cleaned_data['photo'],
                captured_at=now,
                latitude=lat,
                longitude=lng,
            )
            log_attendance_event(
                'CHECK_IN', attendance=record, user=request.user, request=request,
                remarks=address, latitude=lat, longitude=lng,
            )
            messages.success(request, f'Checked in at {now.strftime("%H:%M")} with photo verification.')
            return redirect('my_attendance')
    else:
        form = CheckInForm()

    return render(request, 'attendance/check_in.html', {'form': form, 'record': record})


@module_required(MODULE_ATTENDANCE_SELF)
def check_out(request):
    denied = _require_attendance_marking(request)
    if denied:
        return denied

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
        form = CheckOutForm(request.POST, request.FILES)
        if form.is_valid():
            now = attendance_now()
            lat = form.cleaned_data['latitude']
            lng = form.cleaned_data['longitude']
            address = form.cleaned_data.get('location') or reverse_geocode(lat, lng)

            record.check_out_time = now.time()
            record.check_out_at = now
            record.check_out_location = address
            record.check_out_latitude = lat
            record.check_out_longitude = lng
            record.check_out_maps_link = maps_link(lat, lng)
            record.device_info_out = get_device_info(request)
            record.ip_address_out = get_client_ip(request) or None
            record.check_out_remarks = form.cleaned_data.get('remarks', '')
            record.save()

            AttendancePhoto.objects.create(
                attendance=record,
                employee=request.user,
                photo_type=AttendancePhoto.TYPE_CHECK_OUT,
                image=form.cleaned_data['photo'],
                captured_at=now,
                latitude=lat,
                longitude=lng,
            )
            log_attendance_event(
                'CHECK_OUT', attendance=record, user=request.user, request=request,
                remarks=address, latitude=lat, longitude=lng,
            )
            messages.success(
                request,
                f'Checked out at {now.strftime("%H:%M")}. Working hours: {record.working_hours}h',
            )
            return redirect('my_attendance')
    else:
        form = CheckOutForm()

    return render(request, 'attendance/check_out.html', {'form': form, 'record': record})


@module_required(MODULE_ATTENDANCE_MANAGE)
def attendance_detail(request, pk):
    record = get_object_or_404(
        Attendance.objects.select_related('employee', 'corrected_by').prefetch_related(
            'photos', 'audit_logs',
        ),
        pk=pk,
    )
    return render(request, 'attendance/attendance_detail.html', {
        'record': record,
        'can_edit_attendance': can_edit_attendance_records(request.user),
    })


@module_required(MODULE_ATTENDANCE_TEAM)
def team_attendance(request):
    today = timezone.localdate()
    report_date = today
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    employees = employees_for_manager(request.user)
    record_map = {
        r.employee_id: r
        for r in Attendance.objects.filter(
            attendance_date=report_date, employee__in=employees,
        ).select_related('employee')
    }
    rows = [{'employee': e, 'record': record_map.get(e.id)} for e in employees.order_by('username')]
    return render(request, 'attendance/team_attendance.html', {
        'rows': rows,
        'report_date': report_date,
        'read_only': not can_manage_attendance(request.user),
    })


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


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_absent(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    return render(request, 'attendance/report_absent.html', absent_report(report_date))


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_late(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    return render(request, 'attendance/report_late.html', late_report(report_date))


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_leave(request):
    year, month = date.today().year, date.today().month
    if request.GET.get('year'):
        year = int(request.GET['year'])
    if request.GET.get('month'):
        month = int(request.GET['month'])
    return render(request, 'attendance/report_leave.html', leave_report(year, month))


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_department(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    return render(request, 'attendance/report_department.html', department_report(report_date))


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_location(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    return render(request, 'attendance/report_location.html', location_report(report_date))


@module_required(MODULE_ATTENDANCE_MANAGE)
def report_photo(request):
    report_date = date.today()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    return render(request, 'attendance/report_photo.html', photo_verification_report(report_date))


@module_required(MODULE_ATTENDANCE_MANAGE)
def reports_index(request):
    return render(request, 'attendance/reports_index.html')
