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
    can_manage_billing,
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
            Q(assigned_project_manager=user)
            | Q(source_enquiry__assigned_project_manager=user)
            | Q(work_schedule__team_leader=user)
            | Q(created_by=user),
        ).distinct()
    if role == ROLE_SUPERVISOR:
        return qs.filter(
            Q(assigned_supervisor=user)
            | Q(source_enquiry__assigned_supervisor=user)
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
        if order.assigned_project_manager_id == user.id:
            return True
        if hasattr(order, 'source_enquiry') and order.source_enquiry:
            return order.source_enquiry.assigned_project_manager_id == user.id
        return order.created_by_id == user.id
    if role == ROLE_SUPERVISOR:
        if order.assigned_supervisor_id == user.id:
            return True
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
                order.created_by = request.user
                order.save()
                attachment_formset.instance = order
                attachment_formset.save()
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_ORDER_PROCESSED
            log_activity(
                request.user, ACT_ORDER_PROCESSED,
                related_document=order.order_no or str(order.order_id),
                related_model='Order',
                related_object_id=order.pk,
            )
            from case_intelligence.integrations import order_created
            order_created(request.user, order)
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
            'client', 'assigned_to', 'assigned_project_manager', 'assigned_supervisor',
            'work_schedule', 'work_schedule__team_leader',
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
        old_status = order.status
        if order.update_status(new_status):
            from productivity.gps_service import record_order_status_gps
            record_order_status_gps(request.user, order, old_status, new_status, request)
            from case_intelligence.logger import log_case_event
            from case_intelligence.constants import MOD_ORDER
            if new_status == 'IN_PROGRESS' and schedule:
                from case_intelligence.integrations import work_started
                work_started(request.user, schedule, remarks=order.order_no)
            else:
                log_case_event(
                    request.user,
                    module=MOD_ORDER,
                    document_type='Order',
                    document_number=order.order_no or str(order.order_id),
                    description=f'Order {STATUS_LABELS.get(new_status, new_status)}',
                    previous_status=old_status,
                    new_status=new_status,
                    client=order.client,
                    content_object=order,
                )
            messages.success(request, f'Status updated to {STATUS_LABELS.get(new_status, new_status)}.')
        else:
            messages.error(request, 'Invalid status transition.')
        return redirect('order_detail', pk=pk)

    wcr = getattr(order, 'workcompletionreport', None)
    invoice = getattr(order, 'invoice', None)
    transitions = next_statuses.get(order.status, [])
    boqs = order.boqs.all().order_by('-created_at') if hasattr(order, 'boqs') else []

    site_attendance = None
    can_site_attendance = is_engineer and schedule is not None
    if schedule and can_site_attendance:
        from productivity.models import ScheduleSiteAttendance
        site_attendance = ScheduleSiteAttendance.objects.filter(
            schedule=schedule, employee=request.user,
        ).first()

    from case_intelligence.constants import MOD_ORDER
    from case_intelligence.services import panel_context
    case_ctx = panel_context(
        order,
        module=MOD_ORDER,
        document_number=order.order_no or str(order.order_id),
        status=order.get_status_display(),
        stage=order.get_status_display(),
        assigned_to=str(order.assigned_to or '—'),
    )

    special_project = getattr(order, 'special_project', None)
    from special_projects.permissions import can_manage_special_projects, can_view_special_projects
    can_open_special_project = (
        can_manage_special_projects(request.user) and can_view_special_projects(request.user)
    )
    linked_pm = []
    try:
        from preventive_maintenance.permissions import can_view_pm
        if can_view_pm(request.user):
            linked_pm = list(order.pm_order_links.select_related('observation'))
            related_visit = list(order.related_pm_observations.all())
        else:
            related_visit = []
    except Exception:
        linked_pm = []
        related_visit = []

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'schedule': schedule,
        'transitions': transitions,
        'wcr': wcr,
        'invoice': invoice,
        'is_engineer': is_engineer,
        'boqs': boqs,
        'can_manage_schedule': can_manage_scheduling(request.user),
        'can_manage_billing': can_manage_billing(request.user),
        'site_attendance': site_attendance,
        'can_site_attendance': can_site_attendance,
        'special_project': special_project,
        'can_open_special_project': can_open_special_project,
        'linked_pm': linked_pm,
        'related_pm_visits': related_visit,
        **case_ctx,
    })
