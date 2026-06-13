import json

from datetime import date



from django.db.models import Q, Sum

from django.db.models.functions import TruncMonth



from accounts.models import User

from billing.models import Invoice

from clients.models import Client

from orders.models import Order

from quotations.models import Quotation

from scheduling.models import WorkSchedule





def _schedule_job_counts():

    today = date.today()

    scheduled = WorkSchedule.objects.exclude(status=WorkSchedule.STATUS_CANCELLED).count()

    unscheduled = Order.objects.filter(status='NEW', work_schedule__isnull=True).count()

    in_progress = WorkSchedule.objects.filter(

        status=WorkSchedule.STATUS_IN_PROGRESS,

    ).count()

    completed = WorkSchedule.objects.filter(

        status=WorkSchedule.STATUS_COMPLETED,

    ).count()

    overdue = WorkSchedule.objects.filter(

        scheduled_end_date__lt=today,

    ).exclude(

        status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],

    ).count()

    return {

        'scheduled_jobs': scheduled,

        'unscheduled_jobs': unscheduled,

        'jobs_in_progress': in_progress,

        'completed_jobs': completed,

        'overdue_scheduled_jobs': overdue,

    }





def build_dashboard_context(show_financial=True, show_quotations=True, show_operations=True):

    today = date.today()



    total_clients = Client.objects.count()

    total_orders = Order.objects.count()

    pending_orders = Order.objects.filter(status='IN_PROGRESS').count()

    wcr_pending = Order.objects.filter(status='COMPLETED').count()



    context = {

        'show_financial': show_financial,

        'show_quotations': show_quotations,

        'show_operations': show_operations,

        'total_clients': total_clients,

        'total_orders': total_orders,

        'pending_orders': pending_orders,

        'wcr_pending': wcr_pending,

    }



    if show_operations:

        context.update(_schedule_job_counts())



    if show_financial:

        total_invoices = Invoice.objects.count()

        payment_pending = Invoice.objects.filter(payment_status='PENDING').count()

        invoice_pending_approval = Invoice.objects.filter(
            approval_status__in=['SUBMITTED', 'UNDER_REVIEW'],
        ).count()
        invoice_approved_count = Invoice.objects.filter(approval_status='APPROVED').count()
        invoice_rejected_count = Invoice.objects.filter(approval_status='REJECTED').count()

        total_revenue = Invoice.objects.filter(
            approval_status='APPROVED',
        ).aggregate(Sum('total'))['total__sum'] or 0

        monthly_revenue = (

            Invoice.objects

            .annotate(month=TruncMonth('invoice_date'))

            .values('month')

            .annotate(total=Sum('total'))

            .order_by('month')

        )

        months, revenues = [], []

        for entry in monthly_revenue:

            months.append(entry['month'].strftime("%b %Y"))

            revenues.append(float(entry['total']))

        context.update({

            'total_invoices': total_invoices,

            'payment_pending': payment_pending,

            'invoice_pending_approval': invoice_pending_approval,

            'invoice_approved_count': invoice_approved_count,

            'invoice_rejected_count': invoice_rejected_count,

            'total_revenue': total_revenue,

            'months': json.dumps(months),

            'revenues': json.dumps(revenues),

        })

    else:

        context.update({

            'total_invoices': 0,

            'payment_pending': 0,

            'invoice_pending_approval': 0,

            'invoice_approved_count': 0,

            'invoice_rejected_count': 0,

            'total_revenue': 0,

            'months': json.dumps([]),

            'revenues': json.dumps([]),

        })



    if show_operations:

        survey_count = Order.objects.filter(order_type='SURVEY').count()

        install_count = Order.objects.filter(order_type='INSTALLATION').count()

        complaint_count = Order.objects.filter(order_type='COMPLAINT').count()

        maintenance_count = Order.objects.filter(order_type='MAINTENANCE').count()



        engineers = User.objects.filter(role__in=['ENGINEER', 'Technician'], is_active_employee=True)

        engineer_stats = []

        for engineer in engineers:

            assigned = WorkSchedule.objects.filter(

                assigned_engineers=engineer,

            ).exclude(status=WorkSchedule.STATUS_CANCELLED).count()

            completed = WorkSchedule.objects.filter(

                assigned_engineers=engineer,

                status=WorkSchedule.STATUS_COMPLETED,

            ).count()

            engineer_stats.append({

                'name': engineer.get_full_name() or engineer.username,

                'assigned': assigned,

                'completed': completed,

                'pending': max(assigned - completed, 0),

            })



        overdue_schedules = WorkSchedule.objects.filter(

            scheduled_end_date__lt=today,

        ).exclude(

            status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],

        ).select_related('order', 'order__client').prefetch_related('assigned_engineers')[:20]



        overdue_list = []

        for schedule in overdue_schedules:

            engineer = schedule.engineer_names()

            overdue_list.append({

                'order_id': schedule.order_id,

                'schedule_number': schedule.schedule_number,

                'client': schedule.order.client.name,

                'engineer': engineer,

                'target_date': schedule.scheduled_end_date,

                'delay_days': (today - schedule.scheduled_end_date).days,

            })



        context.update({

            'engineer_stats': engineer_stats,

            'overdue_orders': overdue_list,

            'survey_count': survey_count,

            'install_count': install_count,

            'complaint_count': complaint_count,

            'maintenance_count': maintenance_count,

        })

        try:
            from productivity.services import monthly_trend, productivity_dashboard_kpis
            prod = productivity_dashboard_kpis()
            context.update({
                'prod_active_engineers': prod['active_engineers'],
                'prod_active_technicians': prod['active_technicians'],
                'prod_man_days_month': prod['total_man_days_month'],
                'prod_jobs_completed': prod['jobs_completed'],
                'prod_pending_jobs': prod['pending_jobs'],
                'prod_utilization': prod['team_utilization_pct'],
                'prod_top_engineer': prod['top_engineer'],
                'prod_top_technician': prod['top_technician'],
                'prod_trend': monthly_trend(),
                'prod_eng_rank': prod['engineer_ranking'][:5],
                'prod_tech_rank': prod['technician_ranking'][:5],
            })
        except Exception:
            context.update({
                'prod_active_engineers': 0,
                'prod_active_technicians': 0,
                'prod_man_days_month': 0,
                'prod_jobs_completed': 0,
                'prod_pending_jobs': 0,
                'prod_utilization': None,
                'prod_top_engineer': None,
                'prod_top_technician': None,
                'prod_trend': [],
                'prod_eng_rank': [],
                'prod_tech_rank': [],
            })

    else:

        context.update({

            'engineer_stats': [],

            'overdue_orders': [],

            'survey_count': 0,

            'install_count': 0,

            'complaint_count': 0,

            'maintenance_count': 0,

            'scheduled_jobs': 0,

            'unscheduled_jobs': 0,

            'jobs_in_progress': 0,

            'completed_jobs': 0,

            'overdue_scheduled_jobs': 0,

        })



    if show_quotations:

        total_quotations = Quotation.objects.count()

        qt_pending_approval = Quotation.objects.filter(status='UNDER_REVIEW').count()

        qt_accepted = Quotation.objects.filter(status='ACCEPTED').count()

        qt_rejected = Quotation.objects.filter(status='REJECTED').count()

        quotation_value = Quotation.objects.aggregate(Sum('grand_total'))['grand_total__sum'] or 0

        monthly_quotations = (

            Quotation.objects

            .annotate(month=TruncMonth('quotation_date'))

            .values('month')

            .annotate(total=Sum('grand_total'))

            .order_by('month')

        )

        qt_months, qt_values = [], []

        for entry in monthly_quotations:

            if entry['month']:

                qt_months.append(entry['month'].strftime("%b %Y"))

                qt_values.append(float(entry['total'] or 0))

        context.update({

            'total_quotations': total_quotations,

            'qt_pending_approval': qt_pending_approval,

            'qt_accepted': qt_accepted,

            'qt_rejected': qt_rejected,

            'quotation_value': quotation_value,

            'qt_months': json.dumps(qt_months),

            'qt_values': json.dumps(qt_values),

        })

    else:

        context.update({

            'total_quotations': 0,

            'qt_pending_approval': 0,

            'qt_accepted': 0,

            'qt_rejected': 0,

            'quotation_value': 0,

            'qt_months': json.dumps([]),

            'qt_values': json.dumps([]),

        })



    from attendance.services import today_stats as att_today_stats

    if show_operations:

        context['attendance_stats'] = att_today_stats(today)

    else:

        context['attendance_stats'] = {'present': 0, 'attendance_percentage': 0}



    context.update(_enquiry_dashboard_stats())
    return context


def _enquiry_dashboard_stats():
    try:
        from enquiries.models import Enquiry
    except Exception:
        return {
            'total_enquiries': 0,
            'open_enquiries': 0,
            'quotations_submitted': 0,
            'won_opportunities': 0,
            'lost_opportunities': 0,
            'enquiry_pipeline_labels': json.dumps([]),
            'enquiry_pipeline_values': json.dumps([]),
        }

    closed_statuses = (
        Enquiry.STATUS_LOST,
        Enquiry.STATUS_CLOSED,
        Enquiry.STATUS_CONVERTED,
    )
    pipeline_map = {
        'NEW': Enquiry.STATUS_NEW,
        'ASSIGNED': Enquiry.STATUS_ASSIGNED,
        'SURVEY': [
            Enquiry.STATUS_SURVEY_SCHEDULED,
            Enquiry.STATUS_SURVEY_COMPLETED,
            Enquiry.STATUS_FEASIBILITY_IN_PROGRESS,
        ],
        'QUOTATION': [
            Enquiry.STATUS_QUOTATION_PREPARATION,
            Enquiry.STATUS_QUOTATION_SUBMITTED,
            Enquiry.STATUS_FOLLOW_UP,
        ],
        'WON': Enquiry.STATUS_WON,
        'LOST': Enquiry.STATUS_LOST,
    }
    labels, values = [], []
    for label, statuses in pipeline_map.items():
        labels.append(label)
        if isinstance(statuses, list):
            values.append(Enquiry.objects.filter(status__in=statuses).count())
        else:
            values.append(Enquiry.objects.filter(status=statuses).count())

    return {
        'total_enquiries': Enquiry.objects.count(),
        'open_enquiries': Enquiry.objects.exclude(status__in=closed_statuses).count(),
        'quotations_submitted': Enquiry.objects.filter(
            status=Enquiry.STATUS_QUOTATION_SUBMITTED,
        ).count(),
        'won_opportunities': Enquiry.objects.filter(status=Enquiry.STATUS_WON).count(),
        'lost_opportunities': Enquiry.objects.filter(status=Enquiry.STATUS_LOST).count(),
        'enquiry_pipeline_labels': json.dumps(labels),
        'enquiry_pipeline_values': json.dumps(values),
    }


def build_project_manager_context(user):
    from enquiries.models import Enquiry
    from scheduling.models import WorkSchedule

    today = date.today()
    my_enquiries = Enquiry.objects.filter(
        Q(assigned_project_manager=user) | Q(assigned_to=user),
    ).distinct()
    my_orders = Order.objects.filter(
        Q(source_enquiry__assigned_project_manager=user)
        | Q(work_schedule__team_leader=user),
    ).distinct()

    pending_surveys = my_enquiries.filter(
        survey_required=True,
        status__in=[
            Enquiry.STATUS_ASSIGNED,
            Enquiry.STATUS_SURVEY_SCHEDULED,
        ],
    )
    pending_quotations = my_enquiries.filter(
        status__in=[
            Enquiry.STATUS_QUOTATION_PREPARATION,
            Enquiry.STATUS_FOLLOW_UP,
        ],
    )
    delayed = WorkSchedule.objects.filter(
        scheduled_end_date__lt=today,
        order__source_enquiry__assigned_project_manager=user,
    ).exclude(
        status__in=[WorkSchedule.STATUS_COMPLETED, WorkSchedule.STATUS_CANCELLED],
    ).select_related('order', 'order__client')[:10]

    team = User.objects.filter(reports_to=user, is_active_employee=True)
    team_stats = []
    for member in team:
        assigned = WorkSchedule.objects.filter(assigned_engineers=member).exclude(
            status=WorkSchedule.STATUS_CANCELLED,
        ).count()
        team_stats.append({
            'name': member.get_full_name() or member.username,
            'role': member.get_role_display(),
            'assigned': assigned,
        })

    return {
        'assigned_enquiries': my_enquiries.count(),
        'assigned_orders': my_orders.count(),
        'pending_surveys': pending_surveys.count(),
        'pending_quotations': pending_quotations.count(),
        'delayed_projects': delayed,
        'team_stats': team_stats,
        'recent_enquiries': my_enquiries.order_by('-enquiry_date')[:8],
    }


def merge_attendance_widget(context, user):
    from dashboard.attendance_widget import personal_attendance_context
    context.update(personal_attendance_context(user))
    return context


