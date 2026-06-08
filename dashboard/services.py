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

        total_revenue = Invoice.objects.aggregate(Sum('total'))['total__sum'] or 0

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

            'total_revenue': total_revenue,

            'months': json.dumps(months),

            'revenues': json.dumps(revenues),

        })

    else:

        context.update({

            'total_invoices': 0,

            'payment_pending': 0,

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



    return context


