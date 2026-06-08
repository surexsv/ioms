from django.shortcuts import render

from django.db.models import Q

from datetime import date



from accounts.decorators import module_required

from accounts.permissions import (

    MODULE_DASHBOARD_DIRECTOR,

    MODULE_DASHBOARD_OPERATIONS,

    MODULE_DASHBOARD_ACCOUNTS,

    MODULE_DASHBOARD_ENGINEER,

    MODULE_DASHBOARD_SUPERVISOR,

)

from orders.models import Order

from scheduling.models import WorkSchedule

from .services import build_dashboard_context





@module_required(MODULE_DASHBOARD_DIRECTOR)

def director_dashboard(request):

    context = build_dashboard_context(

        show_financial=True,

        show_quotations=True,

        show_operations=True,

    )

    context['dashboard_title'] = 'Director Dashboard'

    return render(request, 'dashboard/dashboard.html', context)





@module_required(MODULE_DASHBOARD_OPERATIONS)

def operations_dashboard(request):

    context = build_dashboard_context(

        show_financial=False,

        show_quotations=True,

        show_operations=True,

    )

    context['dashboard_title'] = 'Operations Dashboard'

    return render(request, 'dashboard/dashboard.html', context)





@module_required(MODULE_DASHBOARD_ACCOUNTS)

def accounts_dashboard(request):

    context = build_dashboard_context(

        show_financial=True,

        show_quotations=False,

        show_operations=False,

    )

    context['dashboard_title'] = 'Accounts Dashboard'

    return render(request, 'dashboard/dashboard.html', context)





@module_required(MODULE_DASHBOARD_ENGINEER)

def engineer_dashboard(request):

    user = request.user

    today = date.today()

    my_schedules = WorkSchedule.objects.filter(

        assigned_engineers=user,

    ).exclude(status=WorkSchedule.STATUS_CANCELLED).select_related('order', 'order__client')



    active = my_schedules.exclude(

        status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],

    )

    overdue = my_schedules.filter(scheduled_end_date__lt=today).exclude(

        status=WorkSchedule.STATUS_COMPLETED,

    )

    my_orders = Order.objects.filter(

        Q(work_schedule__assigned_engineers=user) | Q(assigned_to=user),

    ).distinct()

    needs_wcr = my_orders.filter(status='COMPLETED').filter(workcompletionreport__isnull=True)



    from attendance.services import employee_month_stats

    from attendance.models import Attendance

    att_month = employee_month_stats(user)

    today_att = Attendance.objects.filter(employee=user, attendance_date=today).first()



    context = {

        'total_assigned': my_schedules.count(),

        'active_count': active.count(),

        'completed_count': my_schedules.filter(status=WorkSchedule.STATUS_COMPLETED).count(),

        'overdue_count': overdue.count(),

        'active_orders': active.order_by('scheduled_start_date')[:10],

        'overdue_orders': overdue.order_by('scheduled_end_date')[:10],

        'needs_wcr': needs_wcr[:5],

        'attendance_month': att_month,

        'today_attendance': today_att,

    }

    return render(request, 'dashboard/engineer_dashboard.html', context)





@module_required(MODULE_DASHBOARD_SUPERVISOR)

def supervisor_dashboard(request):

    today = date.today()

    field_roles = ['ENGINEER', 'Technician']

    team_schedules = WorkSchedule.objects.filter(

        assigned_engineers__role__in=field_roles,

    ).exclude(status=WorkSchedule.STATUS_CANCELLED).select_related('order', 'order__client').distinct()



    from wcr.models import WorkCompletionReport

    pending_wcrs = WorkCompletionReport.objects.filter(

        approved=False,

    ).select_related('order', 'order__client', 'submitted_by')



    from accounts.models import User

    engineers = User.objects.filter(role__in=field_roles, is_active_employee=True)

    team_stats = []

    for eng in engineers:

        assigned = WorkSchedule.objects.filter(assigned_engineers=eng).exclude(

            status=WorkSchedule.STATUS_CANCELLED,

        ).count()

        in_progress = WorkSchedule.objects.filter(

            assigned_engineers=eng,

            status=WorkSchedule.STATUS_IN_PROGRESS,

        ).count()

        team_stats.append({

            'name': eng.get_full_name() or eng.username,

            'assigned': assigned,

            'in_progress': in_progress,

        })



    overdue = team_schedules.filter(scheduled_end_date__lt=today).exclude(

        status=WorkSchedule.STATUS_COMPLETED,

    )



    context = {

        'total_team_orders': team_schedules.count(),

        'in_progress_count': team_schedules.filter(status=WorkSchedule.STATUS_IN_PROGRESS).count(),

        'completed_awaiting_wcr': Order.objects.filter(status='COMPLETED').count(),

        'wcr_pending_count': pending_wcrs.count(),

        'overdue_count': overdue.count(),

        'pending_wcrs': pending_wcrs[:10],

        'team_stats': team_stats,

        'recent_orders': team_schedules.order_by('-created_at')[:10],

        'overdue_orders': overdue.order_by('scheduled_end_date')[:10],

    }

    return render(request, 'dashboard/supervisor_dashboard.html', context)


