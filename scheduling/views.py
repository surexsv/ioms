from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import module_required
from accounts.navigation import redirect_target_after_schedule, schedule_back_navigation
from accounts.permissions import MODULE_ORDERS

from orders.models import Order
from orders.views import _can_access_order

from productivity.activity_logger import log_activity
from productivity.constants import ACT_SCHEDULE_CREATED

from scheduling.constants import REF_ORDER
from scheduling.engine import category_from_order, survey_reference_context
from .forms import FieldScheduleUpdateForm, WorkScheduleForm
from .models import WorkSchedule
from .permissions import can_field_update_schedule, can_manage_scheduling, can_view_schedule


def _redirect_after_schedule(request, schedule):
    target = redirect_target_after_schedule(request.user, schedule)
    if len(target) == 2:
        return redirect(reverse(target[0], args=[target[1]]))
    return redirect(target[0])


@module_required('scheduling')
def schedule_list(request):
    from scheduling.engine import schedules_for_user
    qs = schedules_for_user(request.user).order_by('-scheduled_start_date')
    category = request.GET.get('category')
    if category:
        qs = qs.filter(schedule_category=category)
    return render(request, 'scheduling/schedule_list.html', {
        'schedules': qs[:200],
        'category_filter': category,
    })


@module_required('scheduling')
def schedule_calendar(request):
    from scheduling.engine import schedules_for_user
    from collections import defaultdict
    import json
    qs = schedules_for_user(request.user).order_by('scheduled_start_date')
    by_date = defaultdict(list)
    for s in qs:
        by_date[s.scheduled_start_date.isoformat()].append(s)
    return render(request, 'scheduling/schedule_calendar.html', {
        'schedules': qs[:100],
        'by_date_json': json.dumps({k: len(v) for k, v in by_date.items()}),
    })


@module_required(MODULE_ORDERS)
def schedule_create(request, order_pk):
    order = get_object_or_404(Order.objects.select_related('client'), pk=order_pk)
    if not _can_access_order(request.user, order):
        from accounts.decorators import access_denied_response
        from accounts.access_control import REASON_UNAUTHORIZED
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    if hasattr(order, 'work_schedule'):
        messages.info(request, 'A schedule already exists for this order.')
        return redirect('schedule_edit', pk=order.work_schedule.pk)

    if not can_manage_scheduling(request.user):
        from accounts.decorators import access_denied_response
        from accounts.access_control import REASON_ROLE
        return access_denied_response(request, reason=REASON_ROLE)

    if request.method == 'POST':
        form = WorkScheduleForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                schedule = form.save(commit=False)
                schedule.order = order
                schedule.reference_type = REF_ORDER
                schedule.reference_number = order.order_no
                schedule.schedule_category = category_from_order(order)
                schedule.created_by = request.user
                schedule.save()
                form.save_m2m()
                if schedule.assigned_engineers.exists() and schedule.status == WorkSchedule.STATUS_PLANNED:
                    schedule.status = WorkSchedule.STATUS_ASSIGNED
                    schedule.save(update_fields=['status'])
            log_activity(
                request.user, ACT_SCHEDULE_CREATED,
                related_document=schedule.schedule_number,
                related_model='WorkSchedule',
                related_object_id=schedule.pk,
            )
            from case_intelligence.integrations import schedule_created
            schedule_created(request.user, schedule)
            messages.success(request, f'Schedule {schedule.schedule_number} created.')
            return redirect('order_detail', pk=order.pk)
    else:
        initial = {}
        if order.expected_completion_date:
            initial['scheduled_end_date'] = order.expected_completion_date
        form = WorkScheduleForm(initial=initial)

    return render(request, 'scheduling/schedule_form.html', {
        'form': form,
        'order': order,
        'title': 'Create Schedule',
        'back_nav': schedule_back_navigation(request.user, None),
    })


@module_required('scheduling')
def schedule_edit(request, pk):
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related(
            'order', 'order__client', 'enquiry', 'enquiry__client',
        ).prefetch_related(
            'assigned_engineers', 'supporting_engineers', 'technicians',
        ),
        pk=pk,
    )
    if not can_view_schedule(request.user, schedule):
        from accounts.decorators import access_denied_response
        from accounts.access_control import REASON_UNAUTHORIZED
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    can_edit = can_manage_scheduling(request.user)
    can_field_edit = can_field_update_schedule(request.user, schedule)
    back_nav = schedule_back_navigation(request.user, schedule)
    survey_ref = survey_reference_context(schedule)

    if request.method == 'POST':
        if can_edit:
            form = WorkScheduleForm(request.POST, instance=schedule)
            form_class = WorkScheduleForm
        elif can_field_edit:
            form = FieldScheduleUpdateForm(request.POST, instance=schedule)
            form_class = FieldScheduleUpdateForm
        else:
            from accounts.decorators import access_denied_response
            from accounts.access_control import REASON_ROLE
            return access_denied_response(request, reason=REASON_ROLE)

        if form.is_valid():
            old_status = schedule.status
            form.save()
            schedule.refresh_from_db()
            if schedule.status != old_status:
                from productivity.gps_service import record_schedule_status_gps
                record_schedule_status_gps(request.user, schedule, old_status, schedule.status, request)
            messages.success(request, 'Schedule updated.')
            return _redirect_after_schedule(request, schedule)
    else:
        if can_edit:
            form = WorkScheduleForm(instance=schedule)
        elif can_field_edit:
            form = FieldScheduleUpdateForm(instance=schedule)
        else:
            form = WorkScheduleForm(instance=schedule)
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'scheduling/schedule_form.html', {
        'form': form,
        'order': schedule.order,
        'enquiry': schedule.enquiry,
        'schedule': schedule,
        'title': f'Edit Schedule {schedule.schedule_number}',
        'can_edit': can_edit,
        'can_field_edit': can_field_edit,
        'back_nav': back_nav,
        'survey_ref': survey_ref,
    })
