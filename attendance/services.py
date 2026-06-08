from calendar import monthrange
from datetime import date

from accounts.models import User
from .models import Attendance

TRACKED_ROLES = ('ENGINEER', 'Technician', 'Supervisor', 'OPERATIONS', 'ACCOUNTS')
PRESENT_STATUSES = ('PRESENT', 'HALF_DAY')


def active_employees():
    return User.objects.filter(
        is_active_employee=True,
        role__in=TRACKED_ROLES,
        is_active=True,
    )


def today_stats(for_date=None):
    for_date = for_date or date.today()
    employees = active_employees()
    total = employees.count()
    records = Attendance.objects.filter(attendance_date=for_date)
    present = records.filter(status__in=PRESENT_STATUSES).count()
    absent = records.filter(status='ABSENT').count()
    half_day = records.filter(status='HALF_DAY').count()
    leave = records.filter(status='LEAVE').count()
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
    present_days = records.filter(status='PRESENT').count()
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
