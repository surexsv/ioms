from calendar import monthrange
from datetime import date, time

from accounts.models import User
from accounts.permissions import (
    MODULE_ATTENDANCE_TEAM,
    MODULE_ATTENDANCE_SUPERVISOR_TEAM,
    can_manage_attendance,
    can_access,
)
from accounts.roles import ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR
from attendance.permissions import user_requires_attendance
from .models import Attendance, AttendancePhoto

PRESENT_STATUSES = ('PRESENT', 'LATE', 'HALF_DAY')


def active_employees():
    """Employees subject to attendance tracking — driven by attendance_required."""
    return User.objects.filter(
        is_active_employee=True,
        is_active=True,
        attendance_required=True,
    ).order_by('username')


def employees_for_manager(user):
    """Scoped employee list for team monitoring or full management."""
    if user.is_superuser or can_manage_attendance(user):
        return active_employees()
    if can_access(user, MODULE_ATTENDANCE_TEAM):
        return User.objects.filter(
            is_active=True,
            attendance_required=True,
            role__in=[ROLE_ENGINEER, ROLE_TECHNICIAN, ROLE_SUPERVISOR, 'Technician', 'Supervisor'],
        ).order_by('username')
    if can_access(user, MODULE_ATTENDANCE_SUPERVISOR_TEAM):
        from scheduling.models import WorkSchedule
        team_ids = set()
        team_ids.update(
            User.objects.filter(reports_to=user, is_active=True).values_list('pk', flat=True)
        )
        for s in WorkSchedule.objects.filter(supervisor=user):
            if s.lead_engineer_id:
                team_ids.add(s.lead_engineer_id)
            team_ids.update(s.assigned_engineers.values_list('pk', flat=True))
            team_ids.update(s.supporting_engineers.values_list('pk', flat=True))
            team_ids.update(s.technicians.values_list('pk', flat=True))
        return User.objects.filter(pk__in=team_ids, attendance_required=True, is_active=True)
    return User.objects.filter(pk=user.pk)


def today_stats(for_date=None):
    for_date = for_date or date.today()
    employees = active_employees()
    total = employees.count()
    records = Attendance.objects.filter(attendance_date=for_date)
    present = records.filter(status__in=PRESENT_STATUSES).count()
    absent = records.filter(status='ABSENT').count()
    half_day = records.filter(status='HALF_DAY').count()
    leave = records.filter(status='LEAVE').count()
    late = records.filter(status='LATE').count()
    marked = records.count()
    unmarked = max(0, total - marked)
    pct = round((present + half_day * 0.5) / total * 100, 1) if total else 0
    return {
        'date': for_date,
        'total_employees': total,
        'present': present,
        'absent': absent + unmarked,
        'half_day': half_day,
        'leave': leave,
        'late': late,
        'marked': marked,
        'unmarked': unmarked,
        'attendance_percentage': pct,
    }


def employee_month_stats(employee, year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    _, days_in_month = monthrange(year, month)

    records = Attendance.objects.filter(
        employee=employee,
        attendance_date__year=year,
        attendance_date__month=month,
    )
    present_days = records.filter(status__in=('PRESENT', 'LATE')).count()
    half_days = records.filter(status='HALF_DAY').count()
    absent_days = records.filter(status='ABSENT').count()
    leave_days = records.filter(status='LEAVE').count()

    working_days = days_in_month
    effective_present = present_days + (half_days * 0.5)
    pct = round(effective_present / working_days * 100, 1) if working_days else 0

    return {
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
        'present': present_days,
        'half_day': half_days,
        'absent': absent_days,
        'leave': leave_days,
        'attendance_percentage': pct,
        'records': records.order_by('attendance_date'),
    }


def today_widget(user):
    """Dashboard widget data for attendance-enabled users."""
    today = date.today()
    record = Attendance.objects.filter(employee=user, attendance_date=today).first()
    month_stats = employee_month_stats(user)
    return {
        'record': record,
        'month_pct': month_stats['attendance_percentage'],
        'can_check_in': user_requires_attendance(user) and (not record or not record.check_in_time),
        'can_check_out': user_requires_attendance(user) and record and record.check_in_time and not record.check_out_time,
    }


def daily_report(for_date=None):
    for_date = for_date or date.today()
    employees = active_employees().order_by('username')
    record_map = {
        r.employee_id: r
        for r in Attendance.objects.filter(attendance_date=for_date).select_related('employee')
    }
    rows = []
    for emp in employees:
        rec = record_map.get(emp.id)
        rows.append({'employee': emp, 'record': rec})
    return {'date': for_date, 'rows': rows, 'stats': today_stats(for_date)}


def monthly_report(year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    employees = active_employees().order_by('username')
    rows = []
    for emp in employees:
        stats = employee_month_stats(emp, year, month)
        rows.append({'employee': emp, **stats})
    return {'year': year, 'month': month, 'rows': rows}


def employee_summary(employee, year=None, month=None):
    stats = employee_month_stats(employee, year, month)
    stats['employee'] = employee
    return stats


def absent_report(for_date=None):
    data = daily_report(for_date)
    data['rows'] = [r for r in data['rows'] if not r['record'] or r['record'].status == 'ABSENT']
    return data


def late_report(for_date=None):
    for_date = for_date or date.today()
    rows = Attendance.objects.filter(
        attendance_date=for_date, status='LATE',
    ).select_related('employee')
    return {'date': for_date, 'records': rows}


def leave_report(year=None, month=None):
    today = date.today()
    year = year or today.year
    month = month or today.month
    records = Attendance.objects.filter(
        attendance_date__year=year,
        attendance_date__month=month,
        status='LEAVE',
    ).select_related('employee').order_by('attendance_date')
    return {'year': year, 'month': month, 'records': records}


def location_report(for_date=None):
    for_date = for_date or date.today()
    records = Attendance.objects.filter(
        attendance_date=for_date,
        check_in_time__isnull=False,
    ).select_related('employee').prefetch_related('photos')
    return {'date': for_date, 'records': records}


def photo_verification_report(for_date=None):
    for_date = for_date or date.today()
    records = Attendance.objects.filter(attendance_date=for_date).select_related('employee').prefetch_related('photos')
    rows = []
    for rec in records:
        rows.append({
            'record': rec,
            'has_in_photo': rec.has_check_in_photo,
            'has_out_photo': rec.has_check_out_photo,
            'verified': rec.has_check_in_photo and (not rec.check_out_time or rec.has_check_out_photo),
        })
    return {'date': for_date, 'rows': rows}


def department_report(for_date=None):
    for_date = for_date or date.today()
    employees = active_employees()
    dept_map = {}
    for emp in employees:
        dept = emp.department or 'Unassigned'
        dept_map.setdefault(dept, {'total': 0, 'present': 0})
        dept_map[dept]['total'] += 1
        rec = Attendance.objects.filter(employee=emp, attendance_date=for_date).first()
        if rec and rec.status in PRESENT_STATUSES:
            dept_map[dept]['present'] += 1
    rows = [
        {
            'department': k,
            'total': v['total'],
            'present': v['present'],
            'pct': round(v['present'] / v['total'] * 100, 1) if v['total'] else 0,
        }
        for k, v in sorted(dept_map.items())
    ]
    return {'date': for_date, 'rows': rows}
