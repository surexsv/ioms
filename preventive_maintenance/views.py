from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access_control import REASON_UNAUTHORIZED
from accounts.decorators import access_denied_response, module_required
from clients.models import Client
from orders.models import Order

from .forms import (
    CreateOrderFromPMForm,
    LinkExistingOrderForm,
    PMObservationForm,
    SnapshotFormSet,
)
from .models import PMObservation, PMObservationHistory
from .permissions import (
    MODULE_PREVENTIVE_MAINTENANCE,
    can_approve_pm,
    can_close_pm,
    can_create_pm,
)
from .services import (
    MONITORING_LABELS,
    apply_gps_from_request,
    apply_list_filters,
    approve_observation,
    can_access_observation,
    can_create_pm_order,
    close_observation,
    create_order_from_observation,
    dashboard_stats,
    filter_mine,
    link_existing_order,
    linked_order_display,
    log_history,
    mark_reviewed,
    observations_for_user,
    save_snapshots,
)


def _deny(request):
    return access_denied_response(request, reason=REASON_UNAUTHORIZED)


@module_required(MODULE_PREVENTIVE_MAINTENANCE)
def pm_dashboard(request):
    qs = observations_for_user(request.user)
    stats = dashboard_stats(qs)
    recent = qs.order_by('-created_at')[:12]
    return render(request, 'preventive_maintenance/dashboard.html', {
        'stats': stats,
        'recent': recent,
        'can_create': can_create_pm(request.user),
        'can_approve': can_approve_pm(request.user),
    })


@module_required(MODULE_PREVENTIVE_MAINTENANCE)
def pm_observation_list(request):
    qs = observations_for_user(request.user)
    view = (request.GET.get('view') or '').strip()
    if view == 'mine':
        qs = filter_mine(qs, request.user)
    qs = apply_list_filters(qs, request.GET)
    return render(request, 'preventive_maintenance/observation_list.html', {
        'observations': qs,
        'view': view,
        'clients': Client.objects.order_by('name'),
        'type_choices': PMObservation.MAINTENANCE_TYPE_CHOICES,
        'priority_choices': PMObservation.PRIORITY_CHOICES,
        'source_choices': PMObservation.SOURCE_CHOICES,
        'status_choices': list(PMObservation.ADMIN_STATUS_CHOICES) + [
            ('ORDER_NOT_CREATED', 'Order Not Created'),
            ('ORDER_CREATED', 'Order Created'),
            ('SCHEDULED', 'Scheduled'),
            ('IN_EXECUTION', 'In Execution'),
            ('WCR_PENDING', 'WCR Pending'),
            ('VERIFICATION_PENDING', 'Verification Pending'),
            ('COMPLETED', 'Completed'),
            ('FUTURE_PLANNED', 'Future / Planned'),
            ('OVERDUE', 'Overdue'),
        ],
        'filters': request.GET,
        'can_create': can_create_pm(request.user),
        'monitoring_labels': MONITORING_LABELS,
    })


@module_required(MODULE_PREVENTIVE_MAINTENANCE)
def pm_observation_create(request):
    if not can_create_pm(request.user):
        return _deny(request)

    if request.method == 'POST':
        form = PMObservationForm(request.POST)
        formset = SnapshotFormSet(request.POST, request.FILES, prefix='snapshots')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                observation = form.save(commit=False)
                observation.created_by = request.user
                observation.admin_status = PMObservation.ADMIN_REPORTED
                apply_gps_from_request(observation, request, persist=False)
                observation.save()
                formset.instance = observation
                save_snapshots(observation, formset, request.user)
                log_history(
                    observation, PMObservationHistory.ACTION_CREATED, request.user,
                    new_value=observation.admin_status,
                )
                if observation.has_gps:
                    log_history(
                        observation, PMObservationHistory.ACTION_GPS_CAPTURED, request.user,
                        new_value=f'{observation.latitude},{observation.longitude}',
                    )
            try:
                from case_intelligence.constants import MOD_PM
                from case_intelligence.logger import log_case_event
                log_case_event(
                    request.user,
                    module=MOD_PM,
                    document_type='PM Observation',
                    document_number=observation.pm_number,
                    description='PM Observation Created',
                    new_status=observation.admin_status,
                    client=observation.client,
                    content_object=observation,
                )
            except Exception:
                pass
            messages.success(request, f'Observation {observation.pm_number} recorded.')
            return redirect('pm_observation_detail', pk=observation.pk)
    else:
        initial = {}
        related_order_id = request.GET.get('order')
        if related_order_id:
            try:
                related = Order.objects.select_related('client').get(pk=related_order_id)
                initial['related_order'] = related.pk
                initial['client'] = related.client_id
                initial['site_location'] = related.project_site_name or related.site_address
            except (Order.DoesNotExist, ValueError):
                pass
        form = PMObservationForm(initial=initial)
        formset = SnapshotFormSet(prefix='snapshots')

    return render(request, 'preventive_maintenance/observation_form.html', {
        'form': form,
        'formset': formset,
    })


@module_required(MODULE_PREVENTIVE_MAINTENANCE)
def pm_observation_detail(request, pk):
    observation = get_object_or_404(
        PMObservation.objects.select_related(
            'client', 'created_by', 'reviewed_by', 'approved_by', 'closed_by',
            'related_order', 'related_project',
        ).prefetch_related(
            'order_links__order__work_schedule',
            'order_links__order__workcompletionreport',
            'order_links__order__assigned_to',
            'snapshots',
            'history__actor',
        ),
        pk=pk,
    )
    if not can_access_observation(request.user, observation):
        return _deny(request)

    can_approve = can_approve_pm(request.user)
    can_close = can_close_pm(request.user)
    can_order = can_approve and can_create_pm_order(request.user)
    create_form = CreateOrderFromPMForm()
    link_form = LinkExistingOrderForm(client=observation.client)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'review':
            if not can_approve:
                return _deny(request)
            mark_reviewed(observation, request.user)
            messages.success(request, 'Observation marked under review.')
            return redirect('pm_observation_detail', pk=pk)
        if action == 'approve':
            if not can_approve:
                return _deny(request)
            approve_observation(observation, request.user)
            messages.success(request, 'Observation approved.')
            return redirect('pm_observation_detail', pk=pk)
        if action == 'close':
            if not can_close:
                return _deny(request)
            close_observation(observation, request.user, remarks=request.POST.get('remarks', ''))
            messages.success(request, 'Observation closed.')
            return redirect('pm_observation_detail', pk=pk)
        if action == 'create_order':
            if not can_order:
                return _deny(request)
            if observation.admin_status != PMObservation.ADMIN_APPROVED:
                messages.error(request, 'Approve the observation before creating an Order.')
                return redirect('pm_observation_detail', pk=pk)
            create_form = CreateOrderFromPMForm(request.POST)
            if create_form.is_valid():
                link = create_order_from_observation(
                    observation, request.user,
                    work_item=create_form.cleaned_data.get('work_item') or '',
                )
                messages.success(
                    request,
                    f'Existing IOMS Order {link.order.order_no} created from this observation.',
                )
                return redirect('order_detail', pk=link.order.pk)
        if action == 'link_order':
            if not can_order:
                return _deny(request)
            if observation.admin_status != PMObservation.ADMIN_APPROVED:
                messages.error(request, 'Approve the observation before linking an Order.')
                return redirect('pm_observation_detail', pk=pk)
            link_form = LinkExistingOrderForm(request.POST, client=observation.client)
            if link_form.is_valid():
                link, created = link_existing_order(
                    observation,
                    link_form.cleaned_data['order'],
                    request.user,
                    work_item=link_form.cleaned_data.get('work_item') or '',
                )
                if created:
                    messages.success(request, f'Linked existing Order {link.order.order_no}.')
                else:
                    messages.info(request, 'That Order is already linked.')
                return redirect('pm_observation_detail', pk=pk)

    links = [linked_order_display(link) for link in observation.order_links.all()]
    return render(request, 'preventive_maintenance/observation_detail.html', {
        'observation': observation,
        'links': links,
        'can_approve': can_approve,
        'can_close': can_close,
        'can_order': can_order,
        'create_form': create_form,
        'link_form': link_form,
        'monitoring_status': observation.monitoring_status,
        'monitoring_label': observation.monitoring_status_label(),
    })
