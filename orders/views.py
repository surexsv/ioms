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
from accounts.roles import (
    user_role,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_ENGINEER,
    ROLE_TECHNICIAN,
    LEGACY_SUPERVISOR,
    FIELD_ROLES,
)


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
    role = user_role(user)
    if role in FIELD_ROLES:
        return qs.filter(
            Q(work_schedule__assigned_engineers=user) | Q(assigned_to=user),
        ).distinct()
    if role == ROLE_PROJECT_MANAGER:
        return qs.filter(
            Q(source_enquiry__assigned_project_manager=user)
            | Q(work_schedule__team_leader=user),
        ).distinct()
    if role == ROLE_SUPERVISOR:
        return qs.filter(
            Q(source_enquiry__assigned_supervisor=user)
            | Q(work_schedule__assigned_engineers__role__in=list(FIELD_ROLES))
            | Q(assigned_to__role__in=list(FIELD_ROLES))
            | Q(work_schedule__isnull=True, assigned_to__isnull=True),
        ).distinct()
    return qs


def _can_access_order(user, order):
    if user.is_superuser:
        return True
    if not can_access(user, MODULE_ORDERS):
        return False
    role = user_role(user)
    if role in (ROLE_DIRECTOR, ROLE_OPERATIONS):
        return True
    if role == ROLE_PROJECT_MANAGER:
        if hasattr(order, 'source_enquiry') and order.source_enquiry:
            return order.source_enquiry.assigned_project_manager_id == user.id
        return True
    if role == ROLE_SUPERVISOR:
        if hasattr(order, 'source_enquiry') and order.source_enquiry:
            if order.source_enquiry.assigned_supervisor_id == user.id:
                return True
        if hasattr(order, 'work_schedule'):
            engineers = order.work_schedule.assigned_engineers.all()
            if engineers.exists():
                return all(user_role(e) in FIELD_ROLES for e in engineers)
        if order.assigned_to is None:
            return True
        return user_role(order.assigned_to) in FIELD_ROLES
    if role in FIELD_ROLES:
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

    is_engineer = user_role(request.user) in FIELD_ROLES
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
