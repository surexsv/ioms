from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import User
from attendance.models import Attendance
from attendance.services import active_employees

from .constants import DEFAULT_AGENDA_ITEMS, DEFAULT_OPEN_ITEMS
from .models import (
    AgendaTemplateItem,
    DailyMeeting,
    DailyMeetingsSettings,
    ManagementMessage,
    MeetingActionItem,
    MeetingAgendaItem,
    MeetingAttendance,
    MeetingDiscussion,
    MeetingOpenItemSnapshot,
    OpenItemRegister,
)


def get_settings():
    return DailyMeetingsSettings.get_solo()


def seed_agenda_template():
    created = 0
    for i, title in enumerate(DEFAULT_AGENDA_ITEMS, start=1):
        _, was_created = AgendaTemplateItem.objects.get_or_create(
            title=title,
            defaults={'sort_order': i, 'is_system': True, 'is_active': True},
        )
        if was_created:
            created += 1
    return created


def seed_open_items(user=None):
    created = 0
    for title, desc in DEFAULT_OPEN_ITEMS:
        _, was_created = OpenItemRegister.objects.get_or_create(
            title=title,
            defaults={
                'description': desc,
                'status': OpenItemRegister.STATUS_OPEN,
                'is_recurring': True,
                'created_by': user,
            },
        )
        if was_created:
            created += 1
    return created


def apply_agenda_template(meeting):
    """Copy active template items into meeting agenda."""
    items = AgendaTemplateItem.objects.filter(is_active=True).order_by('sort_order')
    if not items.exists():
        seed_agenda_template()
        items = AgendaTemplateItem.objects.filter(is_active=True).order_by('sort_order')
    for tpl in items:
        MeetingAgendaItem.objects.get_or_create(
            meeting=meeting,
            title=tpl.title,
            defaults={'sort_order': tpl.sort_order},
        )


def attach_open_items_to_meeting(meeting):
    """Snapshot recurring open items into meeting."""
    open_items = OpenItemRegister.objects.filter(
        is_recurring=True,
    ).exclude(status=OpenItemRegister.STATUS_CLOSED).exclude(status=OpenItemRegister.STATUS_CANCELLED)
    for item in open_items:
        MeetingOpenItemSnapshot.objects.get_or_create(
            meeting=meeting,
            open_item=item,
            defaults={'status_at_meeting': item.status},
        )


def _meeting_start_datetime(meeting_date, start_time=None):
    settings = get_settings()
    t = start_time or settings.meeting_start_time
    return datetime.combine(meeting_date, t)


def determine_attendance_status(check_in_time, meeting_date, grace_minutes=None):
    """Return PRESENT, LATE, or ABSENT based on check-in vs meeting start."""
    if not check_in_time:
        return MeetingAttendance.STATUS_ABSENT
    settings = get_settings()
    grace = grace_minutes if grace_minutes is not None else settings.late_grace_minutes
    start = _meeting_start_datetime(meeting_date, settings.meeting_start_time)
    deadline = start + timedelta(minutes=grace)
    check_dt = datetime.combine(meeting_date, check_in_time)
    if check_dt <= deadline:
        return MeetingAttendance.STATUS_PRESENT
    return MeetingAttendance.STATUS_LATE


def sync_meeting_attendance(meeting, employees=None, overwrite_manual=False):
    """
    Auto-populate meeting attendance from Attendance module.
    Compare check-in time with meeting start (default 09:00).
    """
    employees = employees or active_employees()
    settings = get_settings()
    att_map = {
        a.employee_id: a
        for a in Attendance.objects.filter(
            employee__in=employees,
            attendance_date=meeting.meeting_date,
        )
    }
    created = 0
    for emp in employees:
        att_rec = att_map.get(emp.id)
        existing = MeetingAttendance.objects.filter(meeting=meeting, employee=emp).first()
        if existing and existing.is_manual_override and not overwrite_manual:
            continue

        check_in = att_rec.check_in_time if att_rec else None
        if att_rec and att_rec.status == 'ABSENT':
            status = MeetingAttendance.STATUS_ABSENT
            check_in = None
        elif att_rec and att_rec.status == 'LEAVE':
            status = MeetingAttendance.STATUS_ABSENT
            check_in = None
        else:
            status = determine_attendance_status(check_in, meeting.meeting_date)

        MeetingAttendance.objects.update_or_create(
            meeting=meeting,
            employee=emp,
            defaults={
                'role_snapshot': emp.role or '',
                'status': status,
                'join_time': check_in,
                'attendance_record_id': att_rec.pk if att_rec else None,
                'is_manual_override': False,
            },
        )
        created += 1
    return created


def meeting_attendance_stats(meeting):
    qs = meeting.attendees.all()
    total = qs.count()
    if not total:
        return {'total': 0, 'present': 0, 'late': 0, 'absent': 0, 'present_pct': 0, 'late_pct': 0}
    present = qs.filter(status=MeetingAttendance.STATUS_PRESENT).count()
    late = qs.filter(status=MeetingAttendance.STATUS_LATE).count()
    absent = qs.filter(status=MeetingAttendance.STATUS_ABSENT).count()
    return {
        'total': total,
        'present': present,
        'late': late,
        'absent': absent,
        'present_pct': round(present / total * 100, 1),
        'late_pct': round(late / total * 100, 1),
    }


def refresh_overdue_actions():
    today = timezone.localdate()
    return MeetingActionItem.objects.filter(
        target_date__lt=today,
        status__in=[MeetingActionItem.STATUS_OPEN, MeetingActionItem.STATUS_IN_PROGRESS],
    ).update(status=MeetingActionItem.STATUS_OVERDUE)


def action_stats(user=None):
    refresh_overdue_actions()
    qs = MeetingActionItem.objects.all()
    if user:
        qs = qs.filter(assigned_to=user)
    return {
        'open': qs.filter(status=MeetingActionItem.STATUS_OPEN).count(),
        'in_progress': qs.filter(status=MeetingActionItem.STATUS_IN_PROGRESS).count(),
        'completed': qs.filter(status__in=[MeetingActionItem.STATUS_COMPLETED, MeetingActionItem.STATUS_CLOSED]).count(),
        'overdue': qs.filter(status=MeetingActionItem.STATUS_OVERDUE).count(),
        'total': qs.count(),
    }


def dashboard_summary(for_date=None):
    for_date = for_date or timezone.localdate()
    refresh_overdue_actions()
    today_meeting = DailyMeeting.objects.filter(meeting_date=for_date).order_by('-meeting_time').first()
    att_stats = meeting_attendance_stats(today_meeting) if today_meeting else {}
    open_items = OpenItemRegister.objects.exclude(
        status__in=[OpenItemRegister.STATUS_CLOSED, OpenItemRegister.STATUS_CANCELLED],
    ).count()
    actions = action_stats()
    return {
        'date': for_date,
        'today_meeting': today_meeting,
        'attendance': att_stats,
        'open_actions': actions['open'] + actions['in_progress'],
        'overdue_actions': actions['overdue'],
        'completed_actions': actions['completed'],
        'recurring_open_items': open_items,
        'action_stats': actions,
    }


def create_daily_meeting(user, meeting_date=None, **kwargs):
    meeting_date = meeting_date or timezone.localdate()
    settings = get_settings()
    meeting, created = DailyMeeting.objects.get_or_create(
        meeting_date=meeting_date,
        meeting_type=kwargs.get('meeting_type', settings.default_meeting_type),
        department=kwargs.get('department', 'Operations'),
        defaults={
            'meeting_time': kwargs.get('meeting_time', settings.meeting_start_time),
            'topic_of_day': kwargs.get('topic_of_day', ''),
            'conducted_by': kwargs.get('conducted_by', user),
            'status': DailyMeeting.STATUS_DRAFT,
            'created_by': user,
            'remarks': kwargs.get('remarks', ''),
        },
    )
    if created:
        apply_agenda_template(meeting)
        attach_open_items_to_meeting(meeting)
        sync_meeting_attendance(meeting)
    return meeting, created


def mom_context(meeting):
    """Build context dict for MOM print/PDF."""
    att = meeting_attendance_stats(meeting)
    return {
        'meeting': meeting,
        'agenda': meeting.agenda_items.all(),
        'attendees': meeting.attendees.select_related('employee').all(),
        'discussions': meeting.discussions.all(),
        'actions': meeting.action_items.select_related('assigned_to').all(),
        'messages': meeting.management_messages.all(),
        'open_items': meeting.open_item_reviews.select_related('open_item').all(),
        'attendance_stats': att,
        'generated_at': timezone.localtime(),
    }


def meeting_register(year=None, month=None):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    meetings = DailyMeeting.objects.filter(
        meeting_date__year=year,
        meeting_date__month=month,
    ).select_related('conducted_by', 'created_by')
    return {'year': year, 'month': month, 'meetings': meetings}


def effectiveness_report(year=None):
    year = year or timezone.localdate().year
    meetings = DailyMeeting.objects.filter(meeting_date__year=year, status=DailyMeeting.STATUS_COMPLETED)
    total = meetings.count()
    actions = MeetingActionItem.objects.filter(meeting__meeting_date__year=year)
    completed = actions.filter(status__in=[MeetingActionItem.STATUS_COMPLETED, MeetingActionItem.STATUS_CLOSED]).count()
    action_total = actions.count()
    return {
        'year': year,
        'meetings_held': total,
        'meetings_total': DailyMeeting.objects.filter(meeting_date__year=year).count(),
        'actions_raised': action_total,
        'actions_completed': completed,
        'completion_rate': round(completed / action_total * 100, 1) if action_total else 0,
    }
