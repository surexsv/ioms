from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import module_required
from accounts.permissions import MODULE_SCHEDULING, MODULE_ORDERS

from orders.models import Order
from orders.views import _can_access_order

from productivity.activity_logger import log_activity
from productivity.constants import ACT_SCHEDULE_CREATED

from .forms import WorkScheduleForm
from .models import WorkSchedule
from .permissions import can_manage_scheduling, can_view_schedule


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
    })


@module_required(MODULE_SCHEDULING)
def schedule_edit(request, pk):
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related('order', 'order__client').prefetch_related(
            'assigned_engineers', 'supporting_engineers', 'technicians',
        ),
        pk=pk,
    )
    if not can_view_schedule(request.user, schedule):
        from accounts.decorators import access_denied_response
        from accounts.access_control import REASON_UNAUTHORIZED
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    can_edit = can_manage_scheduling(request.user)

    if request.method == 'POST':
        if not can_edit:
            from accounts.decorators import access_denied_response
            from accounts.access_control import REASON_ROLE
            return access_denied_response(request, reason=REASON_ROLE)
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            old_status = schedule.status
            form.save()
            schedule.refresh_from_db()
            if schedule.status != old_status:
                from productivity.gps_service import record_schedule_status_gps
                record_schedule_status_gps(request.user, schedule, old_status, schedule.status, request)
            messages.success(request, 'Schedule updated.')
            return redirect('order_detail', pk=schedule.order_id)
    else:
        form = WorkScheduleForm(instance=schedule)
        if not can_edit:
            for field in form.fields.values():
                field.disabled = True

    return render(request, 'scheduling/schedule_form.html', {
        'form': form,
        'order': schedule.order,
        'schedule': schedule,
        'title': f'Edit Schedule {schedule.schedule_number}',
        'can_edit': can_edit,
    })
