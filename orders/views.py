from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q

from .models import Order
from .forms import OrderForm, OrderAttachmentFormSet
from accounts.access_control import REASON_UNAUTHORIZED
from accounts.decorators import module_required, access_denied_response
from accounts.permissions import (
    MODULE_ORDERS,
    MODULE_ORDERS_CREATE,
    can_access,
)
from scheduling.permissions import can_manage_scheduling


STATUS_LABELS = {
    'NEW': 'New',
    'SCHEDULED': 'Scheduled',
    'IN_PROGRESS': 'In Progress',
    'COMPLETED': 'Completed',
    'WCR_SUBMITTED': 'WCR Submitted',
    'APPROVED': 'Approved',
    'BILLED': 'Billed',
    'PAYMENT_PENDING': 'Payment Pending',
    'CLOSED': 'Closed',
}

ENGINEER_TRANSITIONS = {
    'SCHEDULED': [('IN_PROGRESS', 'Start Work')],
    'IN_PROGRESS': [('COMPLETED', 'Mark Completed')],
}


def _orders_for_user(user):
    qs = Order.objects.select_related('client', 'assigned_to').order_by('-order_id')
    if user.role in ('ENGINEER', 'Technician'):
        return qs.filter(
            Q(work_schedule__assigned_engineers=user) | Q(assigned_to=user),
        ).distinct()
    if user.role == 'Supervisor':
        return qs.filter(
            Q(work_schedule__assigned_engineers__role__in=['ENGINEER', 'Technician'])
            | Q(assigned_to__role__in=['ENGINEER', 'Technician'])
            | Q(work_schedule__isnull=True, assigned_to__isnull=True),
        ).distinct()
    return qs


def _can_access_order(user, order):
    if user.is_superuser:
        return True
    if not can_access(user, MODULE_ORDERS):
        return False
    if user.role in ('DIRECTOR', 'OPERATIONS', 'Supervisor'):
        if user.role == 'Supervisor':
            if hasattr(order, 'work_schedule'):
                engineers = order.work_schedule.assigned_engineers.all()
                if engineers.exists():
                    return all(e.role in ('ENGINEER', 'Technician') for e in engineers)
            if order.assigned_to is None:
                return True
            return order.assigned_to.role in ('ENGINEER', 'Technician')
        return True
    if user.role in ('ENGINEER', 'Technician'):
        if hasattr(order, 'work_schedule'):
            return order.work_schedule.assigned_engineers.filter(pk=user.pk).exists()
        return order.assigned_to_id == user.id
    return False


@module_required(MODULE_ORDERS)
def order_list(request):
    orders = _orders_for_user(request.user)
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    return render(request, 'orders/order_list.html', {
        'orders': orders,
        'current_status': status,
        'status_choices': Order.STATUS_CHOICES,
        'can_create': can_access(request.user, MODULE_ORDERS_CREATE),
    })


@module_required(MODULE_ORDERS_CREATE)
def create_order(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        attachment_formset = OrderAttachmentFormSet(request.POST, request.FILES)
        if form.is_valid() and attachment_formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.status = 'NEW'
                order.save()
                attachment_formset.instance = order
                attachment_formset.save()
            messages.success(request, f'Order {order.order_no} created.')
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm()
        attachment_formset = OrderAttachmentFormSet()

    return render(request, 'orders/create_order.html', {
        'form': form,
        'attachment_formset': attachment_formset,
    })


@module_required(MODULE_ORDERS)
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related(
            'client', 'assigned_to', 'work_schedule', 'work_schedule__team_leader',
        ).prefetch_related('attachments', 'work_schedule__assigned_engineers'),
        pk=pk,
    )
    if not _can_access_order(request.user, order):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    schedule = getattr(order, 'work_schedule', None)

    is_engineer = request.user.role in ('ENGINEER', 'Technician')
    next_statuses = {
        'NEW': [],
        'SCHEDULED': [('IN_PROGRESS', 'Start Work')],
        'IN_PROGRESS': [('COMPLETED', 'Mark Completed')],
        'COMPLETED': [],
        'WCR_SUBMITTED': [('APPROVED', 'Approve (manual)')],
        'APPROVED': [('BILLED', 'Mark Billed')],
        'BILLED': [('PAYMENT_PENDING', 'Payment Pending')],
        'PAYMENT_PENDING': [('CLOSED', 'Close Order')],
        'CLOSED': [],
    }
    if is_engineer:
        next_statuses = ENGINEER_TRANSITIONS

    if request.method == 'POST' and 'new_status' in request.POST:
        new_status = request.POST['new_status']
        if order.update_status(new_status):
            messages.success(request, f'Status updated to {STATUS_LABELS.get(new_status, new_status)}.')
        else:
            messages.error(request, 'Invalid status transition.')
        return redirect('order_detail', pk=pk)

    wcr = getattr(order, 'workcompletionreport', None)
    invoice = getattr(order, 'invoice', None)
    transitions = next_statuses.get(order.status, [])
    boqs = order.boqs.all().order_by('-created_at') if hasattr(order, 'boqs') else []

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'schedule': schedule,
        'transitions': transitions,
        'wcr': wcr,
        'invoice': invoice,
        'is_engineer': is_engineer,
        'boqs': boqs,
        'can_manage_schedule': can_manage_scheduling(request.user),
    })
