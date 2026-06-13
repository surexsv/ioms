"""GPS dashboard and field report data."""

import json
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from productivity.field_constants import (
    FA_ORDER_COMPLETED,
    FA_SITE_CHECK_IN,
    FA_SITE_CHECK_OUT,
    FA_SURVEY_COMPLETED,
    FA_WCR_SUBMITTED,
)
from productivity.models import FieldActivityLog, GPSLocationRecord, ScheduleSiteAttendance


def gps_dashboard_context(user=None):
    today = timezone.localdate()
    gps_today = GPSLocationRecord.objects.filter(captured_at__date=today)
    activities_today = FieldActivityLog.objects.filter(activity_date=today)

    if user and not user.is_superuser:
        from productivity.permissions import can_view_full_gps, productivity_scope_users
        if not can_view_full_gps(user):
            scope = productivity_scope_users(user)
            gps_today = gps_today.filter(employee__in=scope)
            activities_today = activities_today.filter(employee__in=scope)

    recent_checkins = (
        FieldActivityLog.objects.filter(action_type=FA_SITE_CHECK_IN)
        .select_related('employee', 'order', 'schedule')
        .order_by('-created_at')[:15]
    )
    recent_checkouts = (
        FieldActivityLog.objects.filter(action_type=FA_SITE_CHECK_OUT)
        .select_related('employee', 'order', 'schedule')
        .order_by('-created_at')[:15]
    )
    order_completions = (
        FieldActivityLog.objects.filter(action_type=FA_ORDER_COMPLETED)
        .select_related('employee', 'order')
        .order_by('-created_at')[:10]
    )
    survey_completions = (
        FieldActivityLog.objects.filter(action_type=FA_SURVEY_COMPLETED)
        .select_related('employee', 'enquiry')
        .order_by('-created_at')[:10]
    )

    map_points = []
    for rec in gps_today.select_related('employee').order_by('-captured_at')[:50]:
        map_points.append({
            'lat': float(rec.latitude),
            'lng': float(rec.longitude),
            'label': rec.action_label,
            'employee': (rec.employee.get_full_name() or rec.employee.username) if rec.employee else '',
            'address': rec.address[:80] if rec.address else '',
            'time': rec.captured_at.strftime('%H:%M'),
        })

    site_visits_today = activities_today.filter(
        action_type__in=(FA_SITE_CHECK_IN, FA_SITE_CHECK_OUT, FA_WCR_SUBMITTED),
    ).count()

    week_start = today - timedelta(days=6)
    visit_trend = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        count = FieldActivityLog.objects.filter(
            activity_date=d,
            action_type=FA_SITE_CHECK_IN,
        ).count()
        visit_trend.append({'date': d.isoformat(), 'label': d.strftime('%a'), 'visits': count})

    return {
        'site_visits_today': site_visits_today,
        'gps_captures_today': gps_today.count(),
        'recent_checkins': recent_checkins,
        'recent_checkouts': recent_checkouts,
        'order_completions': order_completions,
        'survey_completions': survey_completions,
        'map_points': map_points,
        'map_points_json': json.dumps(map_points),
        'visit_trend': visit_trend,
        'visit_trend_json': json.dumps(visit_trend),
    }


def field_attendance_report(year=None, month=None):
    from django.db.models.functions import TruncDate
    year = year or timezone.localdate().year
    month = month or timezone.localdate().month
    return (
        ScheduleSiteAttendance.objects.filter(
            check_in_at__year=year,
            check_in_at__month=month,
        )
        .select_related('employee', 'schedule', 'schedule__order')
        .order_by('-check_in_at')
    )


def field_activity_report(year=None, month=None, action_type=None, employee=None):
    year = year or timezone.localdate().year
    month = month or timezone.localdate().month
    qs = FieldActivityLog.objects.filter(
        activity_date__year=year,
        activity_date__month=month,
    ).select_related('employee', 'order', 'schedule', 'wcr', 'enquiry')
    if action_type:
        qs = qs.filter(action_type=action_type)
    if employee:
        qs = qs.filter(employee=employee)
    return qs.order_by('-activity_date', '-activity_time')
