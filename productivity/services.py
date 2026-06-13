"""Dashboard KPIs and report data for productivity module."""

from decimal import Decimal
from datetime import date

from django.db.models import Count, Sum, Q
from django.utils import timezone

from accounts.models import User
from accounts.roles import ROLE_ENGINEER, ROLE_TECHNICIAN, user_role
from attendance.models import Attendance
from orders.models import Order
from productivity.calculator import field_productivity_ranking
from productivity.models import EmployeeActivityLog, EmployeeProductivitySnapshot, WCRTeamParticipant
from scheduling.models import WorkSchedule


def _month_bounds(year=None, month=None):
    today = timezone.localdate()
    year = int(year or today.year)
    month = int(month or today.month)
    return year, month


def productivity_dashboard_kpis(year=None, month=None):
    year, month = _month_bounds(year, month)

    active_engineers = User.objects.filter(
        role=ROLE_ENGINEER, is_active_employee=True, is_active=True,
    ).count()
    active_technicians = User.objects.filter(
        role=ROLE_TECHNICIAN, is_active_employee=True, is_active=True,
    ).count()

    parts = WCRTeamParticipant.objects.filter(
        attended=True,
        wcr__submitted_date__year=year,
        wcr__submitted_date__month=month,
    )
    total_man_days = parts.aggregate(t=Sum('man_days'))['t'] or Decimal('0')
    total_hours = parts.aggregate(t=Sum('hours_worked'))['t'] or Decimal('0')
    jobs_completed = parts.filter(
        wcr__completion_status='COMPLETED',
    ).values('wcr').distinct().count()
    jobs_attended = parts.values('wcr').distinct().count()
    pending_jobs = Order.objects.filter(
        status__in=['SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'WCR_SUBMITTED'],
    ).count()

    scheduled_count = WorkSchedule.objects.exclude(
        status=WorkSchedule.STATUS_CANCELLED,
    ).count()
    utilization = None
    if scheduled_count and (active_engineers + active_technicians):
        utilization = min(
            100,
            round(float(jobs_attended) / float(scheduled_count) * 100, 1),
        ) if scheduled_count else 0

    eng_rank = field_productivity_ranking(year, month, ROLE_ENGINEER)
    tech_rank = field_productivity_ranking(year, month, ROLE_TECHNICIAN)
    top_engineer = eng_rank[0] if eng_rank else None
    top_technician = tech_rank[0] if tech_rank else None

    return {
        'active_engineers': active_engineers,
        'active_technicians': active_technicians,
        'total_man_days_month': total_man_days,
        'total_hours_month': total_hours,
        'jobs_completed': jobs_completed,
        'pending_jobs': pending_jobs,
        'team_utilization_pct': utilization,
        'top_engineer': top_engineer,
        'top_technician': top_technician,
        'engineer_ranking': eng_rank[:10],
        'technician_ranking': tech_rank[:10],
        'period_year': year,
        'period_month': month,
    }


def employee_productivity_detail(employee, year=None, month=None):
    year, month = _month_bounds(year, month)
    role = user_role(employee)

    parts = WCRTeamParticipant.objects.filter(
        employee=employee,
        attended=True,
        wcr__submitted_date__year=year,
        wcr__submitted_date__month=month,
    )
    hours = parts.aggregate(t=Sum('hours_worked'))['t'] or Decimal('0')
    man_days = parts.aggregate(t=Sum('man_days'))['t'] or Decimal('0')
    jobs_attended = parts.values('wcr').distinct().count()
    completed = parts.filter(wcr__completion_status='COMPLETED').values('wcr').distinct().count()

    from wcr.models import WorkCompletionReport
    wcr_submitted = WorkCompletionReport.objects.filter(
        submitted_by=employee,
        submitted_date__year=year,
        submitted_date__month=month,
    ).count()

    activities = EmployeeActivityLog.objects.filter(
        employee=employee,
        activity_date__year=year,
        activity_date__month=month,
    ).count()

    att_present = Attendance.objects.filter(
        employee=employee,
        attendance_date__year=year,
        attendance_date__month=month,
        status='PRESENT',
    ).count()
    att_total = Attendance.objects.filter(
        employee=employee,
        attendance_date__year=year,
        attendance_date__month=month,
    ).count()
    attendance_pct = round(att_present / att_total * 100, 1) if att_total else None
    completion_pct = round(completed / jobs_attended * 100, 1) if jobs_attended else None

    return {
        'employee': employee,
        'role': role,
        'jobs_attended': jobs_attended,
        'wcr_submitted': wcr_submitted,
        'hours_worked': hours,
        'man_days': man_days,
        'activities_count': activities,
        'attendance_pct': attendance_pct,
        'completion_pct': completion_pct,
        'completed_jobs': completed,
        'pending_jobs': max(0, jobs_attended - completed),
    }


def monthly_trend(year=None, months=6):
    today = timezone.localdate()
    year = int(year or today.year)
    points = []
    m = today.month
    y = year
    for _ in range(months):
        parts = WCRTeamParticipant.objects.filter(
            attended=True,
            wcr__submitted_date__year=y,
            wcr__submitted_date__month=m,
        )
        man_days = parts.aggregate(t=Sum('man_days'))['t'] or 0
        jobs = parts.values('wcr').distinct().count()
        points.insert(0, {'year': y, 'month': m, 'man_days': man_days, 'jobs': jobs})
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return points


def activity_report(department=None, year=None, month=None, employee=None):
    year, month = _month_bounds(year, month)
    qs = EmployeeActivityLog.objects.filter(
        activity_date__year=year,
        activity_date__month=month,
    ).select_related('employee')
    if department:
        qs = qs.filter(department=department)
    if employee:
        qs = qs.filter(employee=employee)
    return qs.order_by('-activity_date')
