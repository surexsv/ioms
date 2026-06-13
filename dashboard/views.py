from django.shortcuts import redirect, render
from django.db.models import Q
from datetime import date, timedelta

from accounts.decorators import module_required
from accounts.permissions import (
    MODULE_DASHBOARD_DIRECTOR,
    MODULE_DASHBOARD_OPERATIONS,
    MODULE_DASHBOARD_ACCOUNTS,
    MODULE_DASHBOARD_ENGINEER,
    MODULE_DASHBOARD_SUPERVISOR,
    MODULE_DASHBOARD_PROJECT_MANAGER,
    can_manage_billing,
)
from accounts.roles import ROLE_SUPERVISOR, ROLE_TECHNICIAN, ROLE_ENGINEER

from orders.models import Order
from scheduling.models import WorkSchedule
from .services import build_dashboard_context, build_project_manager_context, merge_attendance_widget, merge_erms_widget


@module_required(MODULE_DASHBOARD_DIRECTOR)
def director_dashboard(request):
    context = build_dashboard_context(
        show_financial=can_manage_billing(request.user),
        show_quotations=True,
        show_operations=True,
    )
    context['dashboard_title'] = 'Director Dashboard'
    from case_intelligence.stuck_cases import director_monitoring_summary
    from django.urls import reverse
    summary = director_monitoring_summary()
    c = summary['counts']
    context['case_monitoring'] = {
        'title': 'Case Monitoring',
        'cards': [
            {'label': 'Total Open Cases', 'value': summary['total_open_cases'],
             'url': reverse('case_stuck_dashboard')},
            {'label': 'Cases Awaiting Action', 'value': summary['cases_awaiting_action'],
             'url': reverse('case_stuck_dashboard') + '?category=stuck_total', 'warn': True},
            {'label': 'Stuck Cases', 'value': summary['stuck_cases'],
             'url': reverse('case_stuck_dashboard') + '?category=stuck_total', 'warn': True},
            {'label': 'Overdue Cases', 'value': summary['overdue_cases'],
             'url': reverse('case_stuck_dashboard') + '?category=pending_payments', 'danger': True},
        ],
    }
    from daily_meetings.services import dashboard_summary
    from daily_meetings.permissions import can_access_daily_meetings
    if can_access_daily_meetings(request.user):
        context['dom_summary'] = dashboard_summary()
    merge_attendance_widget(context, request.user)
    merge_erms_widget(context, request.user)
    return render(request, 'dashboard/dashboard.html', context)


@module_required(MODULE_DASHBOARD_OPERATIONS)
def operations_dashboard(request):
    context = build_dashboard_context(
        show_financial=False,
        show_quotations=True,
        show_operations=True,
    )
    context['dashboard_title'] = 'Operations Dashboard'
    from case_intelligence.stuck_cases import operations_monitoring_summary
    from django.urls import reverse
    summary = operations_monitoring_summary()
    context['case_monitoring'] = {
        'title': 'Operational Monitoring',
        'cards': [
            {'label': 'Pending Surveys', 'value': summary['pending_surveys'],
             'url': reverse('case_stuck_dashboard') + '?category=delayed_surveys', 'warn': True},
            {'label': 'Pending Quotations', 'value': summary['pending_quotations'],
             'url': reverse('case_stuck_dashboard') + '?category=quotation_followup', 'warn': True},
            {'label': 'Pending Orders', 'value': summary['pending_orders'],
             'url': reverse('case_stuck_dashboard') + '?category=delayed_orders', 'warn': True},
            {'label': 'Pending WCR', 'value': summary['pending_wcr'],
             'url': reverse('case_stuck_dashboard') + '?category=pending_wcr', 'warn': True},
            {'label': 'Delayed Cases', 'value': summary['delayed_cases'],
             'url': reverse('case_stuck_dashboard') + '?category=stuck_total', 'danger': True},
        ],
    }
    from daily_meetings.services import dashboard_summary
    from daily_meetings.permissions import can_access_daily_meetings
    if can_access_daily_meetings(request.user):
        context['dom_summary'] = dashboard_summary()
    merge_attendance_widget(context, request.user)
    merge_erms_widget(context, request.user)
    return render(request, 'dashboard/dashboard.html', context)


@module_required(MODULE_DASHBOARD_ACCOUNTS)
def accounts_dashboard(request):
    context = build_dashboard_context(
        show_financial=can_manage_billing(request.user),
        show_quotations=False,
        show_operations=False,
    )
    context['dashboard_title'] = 'Accounts Dashboard'
    merge_attendance_widget(context, request.user)
    merge_erms_widget(context, request.user)
    return render(request, 'dashboard/dashboard.html', context)


def _build_field_team_context(user):
    today = date.today()
    from scheduling.engine import schedules_for_user
    from attendance.services import employee_month_stats, today_widget
    from productivity.services import employee_productivity_detail, personal_monthly_trend
    from dashboard.attendance_widget import personal_attendance_context

    my_schedules = schedules_for_user(user)
    active = my_schedules.exclude(
        status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],
    )
    overdue = my_schedules.filter(scheduled_end_date__lt=today).exclude(
        status=WorkSchedule.STATUS_COMPLETED,
    )
    my_orders = Order.objects.filter(
        Q(work_schedule__lead_engineer=user)
        | Q(work_schedule__assigned_engineers=user)
        | Q(work_schedule__supporting_engineers=user)
        | Q(work_schedule__technicians=user)
        | Q(assigned_to=user),
    ).distinct()
    needs_wcr = my_orders.filter(status='COMPLETED').filter(workcompletionreport__isnull=True)
    survey_schedules = my_schedules.filter(enquiry__isnull=False).exclude(
        status=WorkSchedule.STATUS_COMPLETED,
    )[:10]
    today_assignments = active.filter(scheduled_start_date=today).order_by('scheduled_time')[:10]
    upcoming_tasks = active.filter(
        scheduled_start_date__gt=today,
        scheduled_start_date__lte=today + timedelta(days=14),
    ).order_by('scheduled_start_date')[:10]
    pending_activities = active.exclude(status=WorkSchedule.STATUS_COMPLETED).order_by('scheduled_start_date')[:10]
    completed_recent = my_schedules.filter(
        status=WorkSchedule.STATUS_COMPLETED,
    ).order_by('-updated_at')[:8]

    att_month = employee_month_stats(user)
    att_widget = today_widget(user)
    today_att = att_widget['record']
    my_productivity = employee_productivity_detail(user)
    personal_trend = personal_monthly_trend(user)
    att_ctx = personal_attendance_context(user)

    return {
        'total_assigned': my_schedules.count(),
        'active_count': active.count(),
        'completed_count': my_schedules.filter(status=WorkSchedule.STATUS_COMPLETED).count(),
        'pending_count': active.count(),
        'overdue_count': overdue.count(),
        'active_orders': active.order_by('scheduled_start_date')[:10],
        'overdue_orders': overdue.order_by('scheduled_end_date')[:10],
        'needs_wcr': needs_wcr[:5],
        'survey_schedules': survey_schedules,
        'today_assignments': today_assignments,
        'upcoming_tasks': upcoming_tasks,
        'pending_activities': pending_activities,
        'completed_recent': completed_recent,
        'attendance_month': att_month,
        'today_attendance': today_att,
        'attendance_widget': att_widget,
        **att_ctx,
        'my_productivity': my_productivity,
        'personal_trend': personal_trend,
    }


@module_required(MODULE_DASHBOARD_ENGINEER)
def field_team_dashboard(request):
    """Unified dashboard for Engineers and Technicians."""
    return render(request, 'dashboard/field_team_dashboard.html', _build_field_team_context(request.user))


def engineer_dashboard(request):
    """Legacy URL — redirects to unified Field Team Dashboard."""
    return redirect('field_team_dashboard')


@module_required(MODULE_DASHBOARD_PROJECT_MANAGER)
def project_manager_dashboard(request):
    context = build_project_manager_context(request.user)
    context['dashboard_title'] = 'Project Manager Dashboard'
    merge_attendance_widget(context, request.user)
    merge_erms_widget(context, request.user)
    return render(request, 'dashboard/project_manager_dashboard.html', context)


@module_required(MODULE_DASHBOARD_SUPERVISOR)
def supervisor_dashboard(request):
    """Project Supervisor — Team Management Dashboard."""
    today = date.today()
    user = request.user
    field_roles = [ROLE_ENGINEER, ROLE_TECHNICIAN]

    from accounts.models import User
    from wcr.models import WorkCompletionReport
    from enquiries.models import SiteProgressUpdate
    from attendance.models import Attendance
    from scheduling.engine import schedules_for_user

    team_members = User.objects.filter(role__in=field_roles, is_active_employee=True)
    team_schedules = WorkSchedule.objects.filter(
        Q(supervisor=user)
        | Q(lead_engineer__in=team_members)
        | Q(supporting_engineers__in=team_members)
        | Q(technicians__in=team_members)
        | Q(assigned_engineers__in=team_members),
    ).exclude(status=WorkSchedule.STATUS_CANCELLED).select_related(
        'order', 'order__client', 'enquiry', 'enquiry__client',
    ).distinct()

    pending_wcrs = WorkCompletionReport.objects.filter(
        approved=False,
    ).select_related('order', 'order__client', 'submitted_by')
    engineers = team_members
    team_stats = []
    for eng in engineers:
        eng_schedules = schedules_for_user(eng)
        team_stats.append({
            'name': eng.get_full_name() or eng.username,
            'assigned': eng_schedules.exclude(status=WorkSchedule.STATUS_CANCELLED).count(),
            'in_progress': eng_schedules.filter(status=WorkSchedule.STATUS_IN_PROGRESS).count(),
            'completed': eng_schedules.filter(status=WorkSchedule.STATUS_COMPLETED).count(),
        })

    overdue = team_schedules.filter(scheduled_end_date__lt=today).exclude(
        status=WorkSchedule.STATUS_COMPLETED,
    )
    recent_updates = SiteProgressUpdate.objects.filter(
        supervisor=user,
    ).select_related('enquiry', 'order')[:8]
    att_today = Attendance.objects.filter(attendance_date=today, status='PRESENT').count()
    att_total = Attendance.objects.filter(attendance_date=today).count()
    team_attendance_pct = round(att_today / att_total * 100, 1) if att_total else 0

    open_schedules = team_schedules.exclude(status=WorkSchedule.STATUS_COMPLETED).count()
    completed_schedules = team_schedules.filter(status=WorkSchedule.STATUS_COMPLETED).count()
    today_assignments = team_schedules.filter(scheduled_start_date=today)[:12]
    pending_activities = team_schedules.exclude(
        status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],
    ).order_by('scheduled_start_date')[:12]

    completion_rate = 0
    if team_schedules.count():
        completion_rate = round(completed_schedules / team_schedules.count() * 100, 1)

    context = {
        'active_team_count': team_members.count(),
        'assigned_projects': team_schedules.values('reference_number').distinct().count(),
        'open_schedules': open_schedules,
        'completed_schedules': completed_schedules,
        'team_attendance_pct': team_attendance_pct,
        'wcr_pending_count': pending_wcrs.count(),
        'completion_rate': completion_rate,
        'pending_wcrs': pending_wcrs[:10],
        'team_stats': team_stats,
        'today_assignments': today_assignments,
        'pending_activities': pending_activities,
        'recent_wcrs': pending_wcrs[:8],
        'recent_orders': team_schedules.order_by('-created_at')[:10],
        'overdue_orders': overdue.order_by('scheduled_end_date')[:10],
        'recent_site_updates': recent_updates,
        'can_add_site_update': True,
    }
    merge_attendance_widget(context, user)
    merge_erms_widget(context, user)
    return render(request, 'dashboard/supervisor_dashboard.html', context)
