from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.permissions import MODULE_ORDERS_CREATE, can_access
from accounts.roles import (
    FIELD_ROLES,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
)
from orders.models import Order

from .models import PMObservation, PMObservationHistory, PMObservationOrder, PMObservationSnapshot

MONITOR_REPORTED = 'REPORTED'
MONITOR_UNDER_REVIEW = 'UNDER_REVIEW'
MONITOR_APPROVED = 'APPROVED'
MONITOR_ORDER_NOT_CREATED = 'ORDER_NOT_CREATED'
MONITOR_ORDER_CREATED = 'ORDER_CREATED'
MONITOR_SCHEDULED = 'SCHEDULED'
MONITOR_IN_EXECUTION = 'IN_EXECUTION'
MONITOR_WCR_PENDING = 'WCR_PENDING'
MONITOR_VERIFICATION_PENDING = 'VERIFICATION_PENDING'
MONITOR_COMPLETED = 'COMPLETED'
MONITOR_CLOSED = 'CLOSED'
MONITOR_FUTURE = 'FUTURE_PLANNED'

MONITORING_LABELS = {
    MONITOR_REPORTED: 'Reported',
    MONITOR_UNDER_REVIEW: 'Under Review',
    MONITOR_APPROVED: 'Approved',
    MONITOR_ORDER_NOT_CREATED: 'Order Not Created',
    MONITOR_ORDER_CREATED: 'Order Created',
    MONITOR_SCHEDULED: 'Scheduled',
    MONITOR_IN_EXECUTION: 'In Execution',
    MONITOR_WCR_PENDING: 'WCR Pending',
    MONITOR_VERIFICATION_PENDING: 'Verification Pending',
    MONITOR_COMPLETED: 'Completed',
    MONITOR_CLOSED: 'Closed',
    MONITOR_FUTURE: 'Future / Planned',
}

ORDER_STATUS_RANK = {
    'NEW': 10,
    'SCHEDULED': 20,
    'IN_PROGRESS': 30,
    'COMPLETED': 40,
    'WCR_SUBMITTED': 50,
    'APPROVED': 60,
    'BILLED': 70,
    'PAYMENT_PENDING': 80,
    'CLOSED': 90,
}


def log_history(observation, action, actor, previous_value='', new_value='', remarks=''):
    return PMObservationHistory.objects.create(
        observation=observation,
        action=action,
        actor=actor,
        previous_value=previous_value or '',
        new_value=new_value or '',
        remarks=remarks or '',
    )


def _log_case(user, observation, description, previous_status='', new_status='', remarks=''):
    try:
        from case_intelligence.constants import MOD_PM
        from case_intelligence.logger import log_case_event
    except Exception:
        return
    log_case_event(
        user,
        module=MOD_PM,
        document_type='PM Observation',
        document_number=observation.pm_number or str(observation.pk),
        description=description,
        previous_status=previous_status,
        new_status=new_status or observation.admin_status,
        client=observation.client,
        content_object=observation,
        remarks=remarks,
    )


def apply_gps_from_request(observation, request, persist=True):
    from productivity.gps_service import extract_gps_from_request, reverse_geocode

    lat, lng = extract_gps_from_request(request)
    accuracy = None
    raw_acc = request.POST.get('gps_accuracy') or request.GET.get('gps_accuracy')
    if raw_acc:
        try:
            from decimal import Decimal
            accuracy = Decimal(str(raw_acc))
        except Exception:
            accuracy = None
    if lat is None or lng is None:
        return False
    observation.latitude = lat
    observation.longitude = lng
    observation.gps_accuracy = accuracy
    observation.gps_captured_at = timezone.now()
    if not observation.gps_address:
        observation.gps_address = reverse_geocode(lat, lng) or ''
    if persist and observation.pk:
        observation.save(update_fields=[
            'latitude', 'longitude', 'gps_accuracy', 'gps_address', 'gps_captured_at', 'updated_at',
        ])
    return True


def stamp_snapshot_gps(snapshot, observation):
    if snapshot.latitude is None:
        snapshot.latitude = observation.latitude
    if snapshot.longitude is None:
        snapshot.longitude = observation.longitude


def derive_monitoring_status(observation):
    if observation.admin_status == PMObservation.ADMIN_CLOSED:
        return MONITOR_CLOSED

    links = list(observation.order_links.select_related('order'))
    if not links:
        if observation.maintenance_type == PMObservation.TYPE_FUTURE:
            return MONITOR_FUTURE
        if observation.admin_status == PMObservation.ADMIN_APPROVED:
            return MONITOR_ORDER_NOT_CREATED
        if observation.admin_status == PMObservation.ADMIN_UNDER_REVIEW:
            return MONITOR_UNDER_REVIEW
        return MONITOR_REPORTED

    least = min(
        links,
        key=lambda link: ORDER_STATUS_RANK.get(link.order.status, 0),
    )
    status = least.order.status
    mapping = {
        'NEW': MONITOR_ORDER_CREATED,
        'SCHEDULED': MONITOR_SCHEDULED,
        'IN_PROGRESS': MONITOR_IN_EXECUTION,
        'COMPLETED': MONITOR_WCR_PENDING,
        'WCR_SUBMITTED': MONITOR_VERIFICATION_PENDING,
        'APPROVED': MONITOR_COMPLETED,
        'BILLED': MONITOR_COMPLETED,
        'PAYMENT_PENDING': MONITOR_COMPLETED,
        'CLOSED': MONITOR_CLOSED,
    }
    return mapping.get(status, MONITOR_ORDER_CREATED)


def observations_for_user(user):
    qs = PMObservation.objects.select_related(
        'client', 'created_by', 'related_order', 'related_project',
    ).prefetch_related(
        'order_links__order__work_schedule',
        'order_links__order__workcompletionreport',
        'order_links__order__assigned_to',
        'snapshots',
    )
    if user.is_superuser:
        return qs
    role = user_role(user)
    if role in (ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR):
        return qs
    if role in FIELD_ROLES:
        return qs.filter(
            Q(created_by=user)
            | Q(order_links__order__assigned_to=user)
            | Q(order_links__order__work_schedule__assigned_engineers=user)
            | Q(order_links__order__work_schedule__technicians=user)
            | Q(order_links__order__work_schedule__lead_engineer=user)
        ).distinct()
    return qs.none()


def can_access_observation(user, observation):
    if user.is_superuser:
        return True
    return observations_for_user(user).filter(pk=observation.pk).exists()


def apply_list_filters(qs, params):
    view = (params.get('view') or '').strip()
    client = (params.get('client') or '').strip()
    location = (params.get('location') or '').strip()
    system = (params.get('system') or '').strip()
    equipment = (params.get('equipment') or '').strip()
    mtype = (params.get('maintenance_type') or '').strip()
    priority = (params.get('priority') or '').strip()
    source = (params.get('source') or '').strip()
    linked_order = (params.get('linked_order') or '').strip()
    assigned = (params.get('assigned') or '').strip()
    date_from = (params.get('date_from') or '').strip()
    date_to = (params.get('date_to') or '').strip()
    status = (params.get('status') or '').strip()

    if client:
        qs = qs.filter(client_id=client)
    if location:
        qs = qs.filter(site_location__icontains=location)
    if system:
        qs = qs.filter(system_service__icontains=system)
    if equipment:
        qs = qs.filter(equipment_asset__icontains=equipment)
    if mtype:
        qs = qs.filter(maintenance_type=mtype)
    if priority:
        qs = qs.filter(priority=priority)
    if source:
        qs = qs.filter(source=source)
    if linked_order:
        qs = qs.filter(
            Q(order_links__order__order_no__icontains=linked_order)
            | Q(related_order__order_no__icontains=linked_order)
        ).distinct()
    if assigned:
        qs = qs.filter(
            Q(created_by__username__icontains=assigned)
            | Q(order_links__order__assigned_to__username__icontains=assigned)
        ).distinct()
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    today = timezone.localdate()
    if view == 'mine':
        return qs
    if view == 'pending_review':
        qs = qs.filter(admin_status__in=[
            PMObservation.ADMIN_REPORTED, PMObservation.ADMIN_UNDER_REVIEW,
        ])
    elif view == 'high':
        qs = qs.filter(priority=PMObservation.PRIORITY_HIGH)
    elif view == 'critical':
        qs = qs.filter(priority=PMObservation.PRIORITY_CRITICAL)
    elif view == 'order_not_created':
        qs = qs.filter(admin_status=PMObservation.ADMIN_APPROVED, order_links__isnull=True)
    elif view == 'future':
        qs = qs.filter(maintenance_type=PMObservation.TYPE_FUTURE).exclude(
            admin_status=PMObservation.ADMIN_CLOSED,
        )
    elif view == 'closed':
        qs = qs.filter(admin_status=PMObservation.ADMIN_CLOSED)
    elif view == 'overdue':
        qs = qs.filter(
            suggested_due_date__lt=today,
        ).exclude(admin_status=PMObservation.ADMIN_CLOSED)
    elif view == 'scheduled':
        qs = qs.filter(order_links__order__status='SCHEDULED').distinct()
    elif view == 'in_progress':
        qs = qs.filter(order_links__order__status='IN_PROGRESS').distinct()
    elif view == 'wcr_pending':
        qs = qs.filter(order_links__order__status='COMPLETED').distinct()
    elif view == 'verification_pending':
        qs = qs.filter(order_links__order__status='WCR_SUBMITTED').distinct()

    if status:
        if status == 'OVERDUE':
            qs = qs.filter(
                suggested_due_date__lt=today,
            ).exclude(admin_status=PMObservation.ADMIN_CLOSED)
        elif status in (
            PMObservation.ADMIN_REPORTED,
            PMObservation.ADMIN_UNDER_REVIEW,
            PMObservation.ADMIN_APPROVED,
            PMObservation.ADMIN_CLOSED,
        ):
            qs = qs.filter(admin_status=status)
        elif status == MONITOR_ORDER_NOT_CREATED:
            qs = qs.filter(admin_status=PMObservation.ADMIN_APPROVED, order_links__isnull=True)
        elif status == MONITOR_FUTURE:
            qs = qs.filter(maintenance_type=PMObservation.TYPE_FUTURE)
        elif status == MONITOR_SCHEDULED:
            qs = qs.filter(order_links__order__status='SCHEDULED').distinct()
        elif status == MONITOR_IN_EXECUTION:
            qs = qs.filter(order_links__order__status='IN_PROGRESS').distinct()
        elif status == MONITOR_WCR_PENDING:
            qs = qs.filter(order_links__order__status='COMPLETED').distinct()
        elif status == MONITOR_VERIFICATION_PENDING:
            qs = qs.filter(order_links__order__status='WCR_SUBMITTED').distinct()
        elif status == MONITOR_COMPLETED:
            qs = qs.filter(order_links__order__status__in=['APPROVED', 'BILLED', 'PAYMENT_PENDING']).distinct()
        elif status == MONITOR_ORDER_CREATED:
            qs = qs.filter(order_links__order__status='NEW').distinct()
    return qs


def filter_mine(qs, user):
    return qs.filter(created_by=user)


def dashboard_stats(qs):
    today = timezone.localdate()
    base = qs
    return {
        'new_observations': base.filter(admin_status=PMObservation.ADMIN_REPORTED).count(),
        'pending_review': base.filter(admin_status__in=[
            PMObservation.ADMIN_REPORTED, PMObservation.ADMIN_UNDER_REVIEW,
        ]).count(),
        'order_not_created': base.filter(
            admin_status=PMObservation.ADMIN_APPROVED, order_links__isnull=True,
        ).count(),
        'scheduled': base.filter(order_links__order__status='SCHEDULED').distinct().count(),
        'in_progress': base.filter(order_links__order__status='IN_PROGRESS').distinct().count(),
        'wcr_pending': base.filter(order_links__order__status='COMPLETED').distinct().count(),
        'verification_pending': base.filter(order_links__order__status='WCR_SUBMITTED').distinct().count(),
        'overdue': base.filter(
            suggested_due_date__lt=today,
        ).exclude(admin_status=PMObservation.ADMIN_CLOSED).count(),
        'closed': base.filter(admin_status=PMObservation.ADMIN_CLOSED).count(),
    }


def mark_reviewed(observation, user):
    previous = observation.admin_status
    observation.admin_status = PMObservation.ADMIN_UNDER_REVIEW
    observation.reviewed_by = user
    observation.reviewed_at = timezone.now()
    observation.save(update_fields=['admin_status', 'reviewed_by', 'reviewed_at', 'updated_at'])
    log_history(observation, PMObservationHistory.ACTION_REVIEWED, user, previous, observation.admin_status)
    _log_case(user, observation, 'PM Reviewed', previous, observation.admin_status)
    return observation


def approve_observation(observation, user):
    previous = observation.admin_status
    observation.admin_status = PMObservation.ADMIN_APPROVED
    observation.approved_by = user
    observation.approved_at = timezone.now()
    if not observation.reviewed_by_id:
        observation.reviewed_by = user
        observation.reviewed_at = observation.approved_at
    observation.save(update_fields=[
        'admin_status', 'approved_by', 'approved_at',
        'reviewed_by', 'reviewed_at', 'updated_at',
    ])
    log_history(observation, PMObservationHistory.ACTION_APPROVED, user, previous, observation.admin_status)
    _log_case(user, observation, 'PM Approved', previous, observation.admin_status)
    return observation


def close_observation(observation, user, remarks=''):
    previous = observation.admin_status
    observation.admin_status = PMObservation.ADMIN_CLOSED
    observation.closed_by = user
    observation.closed_at = timezone.now()
    observation.save(update_fields=['admin_status', 'closed_by', 'closed_at', 'updated_at'])
    log_history(
        observation, PMObservationHistory.ACTION_CLOSED, user,
        previous, observation.admin_status, remarks=remarks,
    )
    _log_case(user, observation, 'PM Closed', previous, observation.admin_status, remarks=remarks)
    return observation


def _order_description(observation, work_item=''):
    parts = [
        observation.observation.strip(),
    ]
    if observation.recommended_work:
        parts.append(f'Recommended work: {observation.recommended_work.strip()}')
    if work_item:
        parts.append(f'Work item: {work_item.strip()}')
    if observation.equipment_asset:
        parts.append(f'Equipment: {observation.equipment_asset}')
    if observation.system_service:
        parts.append(f'System / Service: {observation.system_service}')
    return '\n\n'.join(p for p in parts if p)


def _order_priority(observation):
    mapping = {
        PMObservation.PRIORITY_CRITICAL: 'Critical',
        PMObservation.PRIORITY_HIGH: 'High',
        PMObservation.PRIORITY_MEDIUM: 'Medium',
        PMObservation.PRIORITY_LOW: 'Low',
        PMObservation.PRIORITY_INFO: 'Informational',
    }
    return mapping.get(observation.priority, 'Normal')


def can_create_pm_order(user):
    return can_access(user, MODULE_ORDERS_CREATE)


@transaction.atomic
def create_order_from_observation(observation, user, work_item=''):
    site = observation.site_location or observation.client.address
    remarks = (
        f'Source: PREVENTIVE_MAINTENANCE\n'
        f'PM Reference: {observation.pm_number}'
    )
    order = Order.objects.create(
        client=observation.client,
        project_site_name=observation.site_location,
        site_address=site,
        order_type='PREVENTIVE_MAINTENANCE',
        source='INTERNAL',
        description=_order_description(observation, work_item),
        priority=_order_priority(observation),
        expected_completion_date=observation.suggested_due_date,
        remarks=remarks,
        status='NEW',
        created_by=user,
    )
    link = PMObservationOrder.objects.create(
        observation=observation,
        order=order,
        work_item=work_item or '',
        created_by=user,
    )
    log_history(
        observation, PMObservationHistory.ACTION_ORDER_CREATED, user,
        new_value=order.order_no, remarks=work_item,
    )
    _log_case(
        user, observation, 'PM Order Created',
        observation.admin_status, observation.admin_status,
        remarks=order.order_no,
    )
    try:
        from case_intelligence.integrations import order_created
        order_created(user, order, remarks=f'From {observation.pm_number}')
    except Exception:
        pass
    return link


@transaction.atomic
def link_existing_order(observation, order, user, work_item=''):
    link, created = PMObservationOrder.objects.get_or_create(
        observation=observation,
        order=order,
        defaults={'work_item': work_item or '', 'created_by': user},
    )
    if created:
        log_history(
            observation, PMObservationHistory.ACTION_ORDER_LINKED, user,
            new_value=order.order_no, remarks=work_item,
        )
        _log_case(
            user, observation, 'PM Order Linked',
            observation.admin_status, observation.admin_status,
            remarks=order.order_no,
        )
    return link, created


def linked_order_display(link):
    order = link.order
    schedule = order.work_schedule if hasattr(order, 'work_schedule') else None
    wcr = order.workcompletionreport if hasattr(order, 'workcompletionreport') else None
    assigned = ''
    if schedule:
        assigned = schedule.team_member_names() if hasattr(schedule, 'team_member_names') else ''
        if not assigned and schedule.lead_engineer:
            assigned = str(schedule.lead_engineer)
    if not assigned and order.assigned_to:
        assigned = str(order.assigned_to)
    wcr_status = '—'
    if wcr:
        wcr_status = 'Approved' if wcr.approved else 'Pending'
    return {
        'link': link,
        'order': order,
        'schedule': schedule,
        'wcr': wcr,
        'assigned': assigned or '—',
        'wcr_status': wcr_status,
        'order_status': order.get_status_display(),
        'schedule_status': schedule.get_status_display() if schedule else '—',
    }


def save_snapshots(observation, formset, user):
    snapshots = formset.save(commit=False)
    created = []
    for snapshot in snapshots:
        if not snapshot.file:
            continue
        snapshot.observation = observation
        snapshot.uploaded_by = user
        stamp_snapshot_gps(snapshot, observation)
        snapshot.save()
        created.append(snapshot)
    for obj in formset.deleted_objects:
        obj.delete()
    if created:
        log_history(
            observation, PMObservationHistory.ACTION_SNAPSHOT, user,
            new_value=str(len(created)),
        )
    return created
