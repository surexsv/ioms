"""Dashboard KPIs and report data for productivity module."""

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import User
from accounts.roles import ROLE_ENGINEER, ROLE_TECHNICIAN, user_role
from attendance.models import Attendance
from orders.models import Order
from productivity.calculator import compute_performance_score, field_productivity_ranking
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
    scoreboard = performance_scoreboard(year, month)

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
        'scoreboard': scoreboard,
        'period_year': year,
        'period_month': month,
    }


def _month_metrics(employees, year, month):
    """Bulk month totals keyed by employee id."""
    employee_ids = [employee.pk for employee in employees]
    metrics = {
        employee.pk: {
            'jobs_attended': 0,
            'completed_jobs': 0,
            'hours_worked': Decimal('0'),
            'man_days': Decimal('0'),
            'wcr_submitted': 0,
            'activities_count': 0,
            'attendance_pct': None,
            'director_mark': None,
            'director_mark_note': '',
            'director_marked_by': '',
        }
        for employee in employees
    }
    if not employee_ids:
        return metrics

    parts = (
        WCRTeamParticipant.objects.filter(
            employee_id__in=employee_ids,
            attended=True,
            wcr__submitted_date__year=year,
            wcr__submitted_date__month=month,
        )
        .values('employee_id')
        .annotate(
            hours=Sum('hours_worked'),
            man_days=Sum('man_days'),
            jobs_attended=Count('wcr', distinct=True),
            completed_jobs=Count('wcr', filter=Q(wcr__completion_status='COMPLETED'), distinct=True),
        )
    )
    for row in parts:
        bucket = metrics[row['employee_id']]
        bucket['hours_worked'] = row['hours'] or Decimal('0')
        bucket['man_days'] = row['man_days'] or Decimal('0')
        bucket['jobs_attended'] = row['jobs_attended'] or 0
        bucket['completed_jobs'] = row['completed_jobs'] or 0

    from wcr.models import WorkCompletionReport
    submitted = (
        WorkCompletionReport.objects.filter(
            submitted_by_id__in=employee_ids,
            submitted_date__year=year,
            submitted_date__month=month,
        )
        .values('submitted_by_id')
        .annotate(total=Count('id'))
    )
    for row in submitted:
        metrics[row['submitted_by_id']]['wcr_submitted'] = row['total']

    activities = (
        EmployeeActivityLog.objects.filter(
            employee_id__in=employee_ids,
            activity_date__year=year,
            activity_date__month=month,
        )
        .values('employee_id')
        .annotate(total=Count('id'))
    )
    for row in activities:
        metrics[row['employee_id']]['activities_count'] = row['total']

    attendance = (
        Attendance.objects.filter(
            employee_id__in=employee_ids,
            attendance_date__year=year,
            attendance_date__month=month,
        )
        .values('employee_id')
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='PRESENT')),
        )
    )
    for row in attendance:
        if row['total']:
            metrics[row['employee_id']]['attendance_pct'] = round(row['present'] / row['total'] * 100, 1)

    snapshots = EmployeeProductivitySnapshot.objects.filter(
        employee_id__in=employee_ids,
        period_year=year,
        period_month=month,
    ).select_related('director_marked_by')
    for snap in snapshots:
        bucket = metrics.get(snap.employee_id)
        if bucket is None:
            continue
        bucket['director_mark'] = snap.director_mark
        bucket['director_mark_note'] = snap.director_mark_note
        if snap.director_marked_by_id:
            bucket['director_marked_by'] = snap.director_marked_by.full_name_display
    return metrics


def _score_row(employee, metrics):
    jobs_attended = metrics['jobs_attended']
    completed_jobs = metrics['completed_jobs']
    completion_pct = None
    if jobs_attended:
        completion_pct = round(completed_jobs / jobs_attended * 100, 1)
    pending_jobs = max(0, jobs_attended - completed_jobs)
    score = compute_performance_score(
        jobs_attended=jobs_attended,
        completed_jobs=completed_jobs,
        activities_count=metrics['activities_count'],
        attendance_pct=metrics['attendance_pct'],
        attendance_required=employee.attendance_required,
        wcr_submitted=metrics['wcr_submitted'],
        man_days=metrics['man_days'],
        director_mark=metrics['director_mark'],
    )
    return {
        'employee': employee,
        'employee_id': employee.pk,
        'name': employee.full_name_display,
        'role': user_role(employee),
        'role_label': employee.get_role_display() or '—',
        'score': score,
        'rank': None,
        'jobs_attended': jobs_attended,
        'completed_jobs': completed_jobs,
        'pending_jobs': pending_jobs,
        'completion_pct': completion_pct,
        'attendance_pct': metrics['attendance_pct'],
        'wcr_submitted': metrics['wcr_submitted'],
        'activities_count': metrics['activities_count'],
        'man_days': metrics['man_days'],
        'hours_worked': metrics['hours_worked'],
        'director_mark': metrics['director_mark'],
        'director_mark_note': metrics['director_mark_note'],
        'director_marked_by': metrics['director_marked_by'],
    }


def _assign_ranks(rows):
    rows.sort(key=lambda row: (-row['score'], row['name'].lower(), row['employee_id']))
    rank = 0
    previous_score = None
    for row in rows:
        if previous_score is None or row['score'] != previous_score:
            rank += 1
            previous_score = row['score']
        row['rank'] = rank
    return rows


def _persist_scoreboard(rows, year, month):
    for row in rows:
        EmployeeProductivitySnapshot.objects.update_or_create(
            employee_id=row['employee_id'],
            period_year=year,
            period_month=month,
            defaults={
                'jobs_attended': row['jobs_attended'],
                'wcr_submitted': row['wcr_submitted'],
                'hours_worked': row['hours_worked'],
                'man_days': row['man_days'],
                'completed_jobs': row['completed_jobs'],
                'pending_jobs': row['pending_jobs'],
                'activities_count': row['activities_count'],
                'attendance_percent': row['attendance_pct'],
                'completion_percent': row['completion_pct'],
                'incentive_score': row['score'],
                'ranking_position': row['rank'],
            },
        )


def performance_scoreboard(year=None, month=None, persist=True):
    """
    One monthly board for every active employee, including managers.

    Rank 1 is the highest score. Equal scores share a rank.
    """
    year, month = _month_bounds(year, month)
    employees = list(
        User.objects.filter(is_active=True, is_active_employee=True).order_by('pk')
    )
    metrics = _month_metrics(employees, year, month)
    rows = _assign_ranks([_score_row(employee, metrics[employee.pk]) for employee in employees])
    if persist:
        _persist_scoreboard(rows, year, month)
    return rows


def save_director_marks(actor, year, month, marks, notes=None):
    """
    Store director marks for a month, then rebuild scores and ranks.

    marks: {employee_id: Decimal or None}. None clears the mark.
    notes: {employee_id: str}
    Only active employees are updated. Existing work totals are left in place
    until the scoreboard rebuild writes them again.
    """
    year, month = _month_bounds(year, month)
    notes = notes or {}
    employees = {
        employee.pk: employee
        for employee in User.objects.filter(
            pk__in=list(marks.keys()),
            is_active=True,
            is_active_employee=True,
        )
    }
    now = timezone.now()
    for employee_id, employee in employees.items():
        mark = marks.get(employee_id)
        note = (notes.get(employee_id) or '').strip()[:255]
        EmployeeProductivitySnapshot.objects.update_or_create(
            employee=employee,
            period_year=year,
            period_month=month,
            defaults={
                'director_mark': mark,
                'director_mark_note': note if mark is not None else '',
                'director_marked_by': actor if mark is not None else None,
                'director_marked_at': now if mark is not None else None,
            },
        )
    return performance_scoreboard(year, month)


def employee_productivity_detail(employee, year=None, month=None):
    year, month = _month_bounds(year, month)
    board = performance_scoreboard(year, month)
    row = next((item for item in board if item['employee_id'] == employee.pk), None)
    if row is None:
        metrics = _month_metrics([employee], year, month)[employee.pk]
        row = _score_row(employee, metrics)
    return {
        'employee': employee,
        'role': row['role'],
        'role_label': row['role_label'],
        'jobs_attended': row['jobs_attended'],
        'wcr_submitted': row['wcr_submitted'],
        'hours_worked': row['hours_worked'],
        'man_days': row['man_days'],
        'activities_count': row['activities_count'],
        'attendance_pct': row['attendance_pct'],
        'completion_pct': row['completion_pct'],
        'completed_jobs': row['completed_jobs'],
        'pending_jobs': row['pending_jobs'],
        'score': row['score'],
        'rank': row['rank'],
        'director_mark': row['director_mark'],
        'director_mark_note': row['director_mark_note'],
        'director_marked_by': row['director_marked_by'],
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


def personal_monthly_trend(employee, months=6):
    """Personal productivity trend for a single employee."""
    today = timezone.localdate()
    points = []
    m = today.month
    y = today.year
    for _ in range(months):
        parts = WCRTeamParticipant.objects.filter(
            employee=employee,
            attended=True,
            wcr__submitted_date__year=y,
            wcr__submitted_date__month=m,
        )
        man_days = parts.aggregate(t=Sum('man_days'))['t'] or 0
        hours = parts.aggregate(t=Sum('hours_worked'))['t'] or 0
        jobs = parts.values('wcr').distinct().count()
        completed = parts.filter(
            wcr__completion_status='COMPLETED',
        ).values('wcr').distinct().count()
        points.insert(0, {
            'year': y,
            'month': m,
            'man_days': man_days,
            'hours': hours,
            'jobs': jobs,
            'completed': completed,
        })
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
