"""Man-day and productivity calculation engine."""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from accounts.roles import (
    ROLE_ENGINEER,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
    user_role,
)
from productivity.constants import (
    PARTICIPANT_LEAD_ENGINEER,
    PARTICIPANT_PM,
    PARTICIPANT_SUPERVISOR,
    PARTICIPANT_SUPPORTING_ENGINEER,
    PARTICIPANT_TECHNICIAN,
    SCORE_ACTIVITY_JOB_WEIGHT,
    SCORE_FULL_ACTIVITIES,
    SCORE_FULL_JOBS,
    SCORE_FULL_MAN_DAYS,
    SCORE_FULL_REPORTS,
    SCORE_AUTOMATIC_SHARE,
    SCORE_WEIGHT_ATTENDANCE,
    SCORE_WEIGHT_COMPLETION,
    SCORE_WEIGHT_DELIVERED,
    SCORE_WEIGHT_DIRECTOR,
    SCORE_WEIGHT_MAN_DAYS,
    SCORE_WEIGHT_REPORTS,
)
from productivity.models import EmployeeProductivitySnapshot, WCRTeamParticipant


def _quantize(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _scale_to_hundred(value, full_marks):
    """Map a raw count onto 0–100. full_marks is a perfect score on that part."""
    amount = Decimal(value or 0)
    if amount <= 0:
        return Decimal('0')
    points = amount / Decimal(full_marks) * Decimal('100')
    if points > 100:
        points = Decimal('100')
    return _quantize(points)


def compute_performance_score(
    *,
    jobs_attended=0,
    completed_jobs=0,
    activities_count=0,
    attendance_pct=None,
    attendance_required=True,
    wcr_submitted=0,
    man_days=0,
    director_mark=None,
):
    """
    Monthly score from 0 to 100 for any role.

    90% comes from work: completion 40, delivered work 25, attendance 20,
    reports 10, man-days 5, scaled to that 90%.
    10% is the director's mark (0–100). A blank mark counts as zero.
    Field staff are scored on jobs they attended. Someone with no field jobs
    (typical for managers and office staff) is scored on back-office activities
    for the completion and delivered-work parts.
    People who are not required to mark attendance have that attendance share
    folded into the other work parts. The director's 10% stays 10%.
    """
    jobs_attended = int(jobs_attended or 0)
    completed_jobs = int(completed_jobs or 0)
    activities_count = int(activities_count or 0)
    wcr_submitted = int(wcr_submitted or 0)

    if jobs_attended:
        completion_points = _quantize(Decimal(completed_jobs) / Decimal(jobs_attended) * Decimal('100'))
        delivered_units = Decimal(completed_jobs) + (Decimal(activities_count) * SCORE_ACTIVITY_JOB_WEIGHT)
        delivered_points = _scale_to_hundred(delivered_units, SCORE_FULL_JOBS)
    else:
        activity_points = _scale_to_hundred(activities_count, SCORE_FULL_ACTIVITIES)
        completion_points = activity_points
        delivered_points = activity_points

    if attendance_pct is None:
        attendance_points = Decimal('0')
    else:
        attendance_points = Decimal(attendance_pct)
        if attendance_points < 0:
            attendance_points = Decimal('0')
        if attendance_points > 100:
            attendance_points = Decimal('100')
        attendance_points = _quantize(attendance_points)

    report_points = _scale_to_hundred(wcr_submitted, SCORE_FULL_REPORTS)
    man_day_points = _scale_to_hundred(man_days, SCORE_FULL_MAN_DAYS)
    if director_mark is None:
        director_points = Decimal('0')
    else:
        director_points = Decimal(director_mark)
        if director_points < 0:
            director_points = Decimal('0')
        if director_points > 100:
            director_points = Decimal('100')
        director_points = _quantize(director_points)

    automatic = {
        'completion': SCORE_WEIGHT_COMPLETION,
        'delivered': SCORE_WEIGHT_DELIVERED,
        'attendance': SCORE_WEIGHT_ATTENDANCE if attendance_required else Decimal('0'),
        'reports': SCORE_WEIGHT_REPORTS,
        'man_days': SCORE_WEIGHT_MAN_DAYS,
    }
    automatic_total = sum(automatic.values(), Decimal('0'))
    if automatic_total <= 0:
        weights = {key: Decimal('0') for key in automatic}
    else:
        weights = {
            key: value / automatic_total * SCORE_AUTOMATIC_SHARE
            for key, value in automatic.items()
        }
    weights['director'] = SCORE_WEIGHT_DIRECTOR

    parts = {
        'completion': completion_points,
        'delivered': delivered_points,
        'attendance': attendance_points,
        'reports': report_points,
        'man_days': man_day_points,
        'director': director_points,
    }
    score = sum((parts[key] * weights[key] for key in parts), Decimal('0'))
    if score > 100:
        score = Decimal('100')
    return _quantize(score)


def compute_hours_from_times(start_dt, end_dt):
    if not start_dt or not end_dt:
        return Decimal('0')
    if end_dt < start_dt:
        end_dt = end_dt + timedelta(days=1)
    seconds = (end_dt - start_dt).total_seconds()
    return _quantize(Decimal(seconds) / Decimal(3600))


def compute_man_days(hours_worked, hours_per_day=8):
    if not hours_worked or hours_worked <= 0:
        return Decimal('0')
    return _quantize(Decimal(hours_worked) / Decimal(hours_per_day))


def compute_man_days_from_schedule(schedule, participant_count=1):
    """Estimate man-days from schedule date range and expected duration."""
    if not schedule:
        return Decimal('0')
    if schedule.expected_man_days:
        return _quantize(schedule.expected_man_days)
    days = 1
    if schedule.scheduled_start_date and schedule.scheduled_end_date:
        delta = (schedule.scheduled_end_date - schedule.scheduled_start_date).days
        days = max(1, delta + 1)
    if schedule.expected_duration_hours:
        per_person = compute_man_days(schedule.expected_duration_hours)
        return _quantize(per_person * max(1, participant_count))
    return _quantize(Decimal(days))


def sync_wcr_participants(wcr, participants_data):
    """
    participants_data: list of dicts
      {employee, participant_role, attended, hours_worked, man_days, from_schedule}
    """
    WCRTeamParticipant.objects.filter(wcr=wcr).delete()
    created = []
    seen_employee_ids = set()
    for row in participants_data:
        if not row.get('attended', True):
            continue
        emp = row['employee']
        if emp.pk in seen_employee_ids:
            continue
        seen_employee_ids.add(emp.pk)
        hours = row.get('hours_worked') or Decimal('0')
        man_days = row.get('man_days')
        if man_days is None and hours:
            man_days = compute_man_days(hours)
        elif man_days is None:
            man_days = compute_man_days_from_schedule(wcr.schedule, 1)
        part = WCRTeamParticipant.objects.create(
            wcr=wcr,
            employee=emp,
            participant_role=row['participant_role'],
            attended=True,
            hours_worked=_quantize(hours),
            man_days=_quantize(man_days or 0),
            from_schedule=row.get('from_schedule', False),
        )
        created.append(part)
    return created


def build_participants_from_schedule(schedule, wcr=None):
    """Build default participant rows from schedule team assignment."""
    if not schedule:
        return []
    hours = Decimal('0')
    man_days = Decimal('0')
    if wcr and wcr.total_hours:
        hours = wcr.total_hours
        man_days = compute_man_days(hours)
    elif schedule.expected_duration_hours:
        hours = schedule.expected_duration_hours
        man_days = compute_man_days(hours)
    else:
        man_days = compute_man_days_from_schedule(schedule, 1)

    rows = []
    seen_employee_ids = set()

    def add(user, role):
        if not user or user.pk in seen_employee_ids:
            return
        seen_employee_ids.add(user.pk)
        rows.append({
            'employee': user,
            'participant_role': role,
            'attended': True,
            'hours_worked': hours,
            'man_days': man_days,
            'from_schedule': True,
        })

    add(schedule.project_manager, PARTICIPANT_PM)
    add(schedule.supervisor, PARTICIPANT_SUPERVISOR)
    add(schedule.lead_engineer, PARTICIPANT_LEAD_ENGINEER)
    for eng in schedule.supporting_engineers.all():
        add(eng, PARTICIPANT_SUPPORTING_ENGINEER)
    for tech in schedule.technicians.all():
        add(tech, PARTICIPANT_TECHNICIAN)
    # Legacy: assigned_engineers when no structured team fields populated
    if not rows:
        for eng in schedule.assigned_engineers.all():
            role = PARTICIPANT_TECHNICIAN if user_role(eng) == ROLE_TECHNICIAN else PARTICIPANT_SUPPORTING_ENGINEER
            add(eng, role)
        if schedule.team_leader:
            add(schedule.team_leader, PARTICIPANT_LEAD_ENGINEER)
    return rows


def recalculate_monthly_snapshot(employee, year=None, month=None):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    from productivity.models import EmployeeActivityLog
    from wcr.models import WorkCompletionReport

    parts = WCRTeamParticipant.objects.filter(
        employee=employee,
        wcr__submitted_date__year=year,
        wcr__submitted_date__month=month,
        attended=True,
    )
    hours = parts.aggregate(t=Sum('hours_worked'))['t'] or Decimal('0')
    man_days = parts.aggregate(t=Sum('man_days'))['t'] or Decimal('0')
    jobs_attended = parts.values('wcr').distinct().count()
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
    completed = parts.filter(wcr__completion_status='COMPLETED').values('wcr').distinct().count()
    pending = max(0, jobs_attended - completed)
    completion_pct = None
    if jobs_attended:
        completion_pct = _quantize(Decimal(completed) / Decimal(jobs_attended) * 100)

    snap, _ = EmployeeProductivitySnapshot.objects.update_or_create(
        employee=employee,
        period_year=year,
        period_month=month,
        defaults={
            'jobs_attended': jobs_attended,
            'wcr_submitted': wcr_submitted,
            'hours_worked': hours,
            'man_days': man_days,
            'completed_jobs': completed,
            'pending_jobs': pending,
            'activities_count': activities,
            'completion_percent': completion_pct,
        },
    )
    return snap


def recalculate_daily_snapshot(employee, period_date=None):
    from productivity.field_constants import FA_SITE_CHECK_IN
    from productivity.models import EmployeeActivityLog, EmployeeProductivityDaily

    today = timezone.localdate()
    period_date = period_date or today

    parts = WCRTeamParticipant.objects.filter(
        employee=employee,
        wcr__submitted_date__date=period_date,
        attended=True,
    )
    hours = parts.aggregate(t=Sum('hours_worked'))['t'] or Decimal('0')
    man_days = parts.aggregate(t=Sum('man_days'))['t'] or Decimal('0')
    jobs_attended = parts.values('wcr').distinct().count()
    completed = parts.filter(wcr__completion_status='COMPLETED').values('wcr').distinct().count()
    from productivity.models import FieldActivityLog
    check_ins = FieldActivityLog.objects.filter(
        employee=employee, activity_date=period_date, action_type=FA_SITE_CHECK_IN,
    ).count()
    completion_pct = None
    if jobs_attended:
        completion_pct = _quantize(Decimal(completed) / Decimal(jobs_attended) * 100)

    snap, _ = EmployeeProductivityDaily.objects.update_or_create(
        employee=employee,
        period_date=period_date,
        defaults={
            'jobs_attended': jobs_attended,
            'hours_worked': hours,
            'man_days': man_days,
            'completed_jobs': completed,
            'site_check_ins': check_ins,
            'completion_percent': completion_pct,
        },
    )
    return snap


def field_productivity_ranking(year, month, role_filter=None):
    from accounts.models import User
    from productivity.models import WCRTeamParticipant

    qs = WCRTeamParticipant.objects.filter(
        wcr__submitted_date__year=year,
        wcr__submitted_date__month=month,
        attended=True,
    ).values('employee', 'employee__first_name', 'employee__last_name', 'employee__username', 'employee__role')
    if role_filter == ROLE_ENGINEER:
        qs = qs.filter(employee__role=ROLE_ENGINEER)
    elif role_filter == ROLE_TECHNICIAN:
        qs = qs.filter(employee__role=ROLE_TECHNICIAN)
    elif role_filter == ROLE_SUPERVISOR:
        qs = qs.filter(employee__role__in=[ROLE_SUPERVISOR, 'Supervisor'])
    elif role_filter == ROLE_PROJECT_MANAGER:
        qs = qs.filter(employee__role=ROLE_PROJECT_MANAGER)

    ranked = (
        qs.annotate(
            total_man_days=Sum('man_days'),
            total_hours=Sum('hours_worked'),
            job_count=Count('wcr', distinct=True),
        )
        .order_by('-total_man_days', '-total_hours')
    )
    return list(ranked[:20])
