from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import access_denied_response, module_required
from accounts.permissions import MODULE_ERMS, MODULE_ERMS_APPROVE, MODULE_ERMS_VIEW_ALL

from .constants import EDITABLE_STATUSES, STATUS_DRAFT
from .forms import (
    EmployeeRequestForm,
    RequestActionForm,
    RequestAttachmentForm,
    RequestFilterForm,
    RequestSubmitForm,
)
from .models import EmployeeRequest, PortalNotification, RequestAttachment, RequestType
from .permissions import can_access_erms, can_approve_requests, can_view_all_requests, can_view_request
from .services import (
    approve_request,
    dashboard_summary,
    my_requests_qs,
    pending_approvals_qs,
    register_list_qs,
    reject_request,
    return_request,
    submit_request,
)


def _deny(request, module_key=MODULE_ERMS):
    return access_denied_response(request, module_key=module_key)


@module_required(MODULE_ERMS)
def erms_dashboard(request):
    if not can_access_erms(request.user):
        return _deny(request)
    summary = dashboard_summary(request.user)
    return render(request, 'employee_requests/dashboard.html', {
        'summary': summary,
        'show_manager_panel': can_approve_requests(request.user),
    })


@module_required(MODULE_ERMS)
def erms_my_requests(request):
    records = my_requests_qs(request.user)
    return render(request, 'employee_requests/my_requests.html', {'records': records})


@module_required(MODULE_ERMS_APPROVE)
def erms_pending_approvals(request):
    if not can_approve_requests(request.user):
        return _deny(request, MODULE_ERMS_APPROVE)
    records = pending_approvals_qs(request.user)
    return render(request, 'employee_requests/pending_approvals.html', {'records': records})


@module_required(MODULE_ERMS)
def erms_request_create(request):
    if request.method == 'POST':
        form = EmployeeRequestForm(request.POST, user=request.user)
        if form.is_valid():
            record = form.save(commit=False)
            record.requested_by = request.user
            if not record.department:
                record.department = getattr(request.user, 'department', '') or ''
            record.status = STATUS_DRAFT
            record.save()
            messages.success(request, 'Request saved as draft.')
            return redirect('erms_request_detail', pk=record.pk)
    else:
        form = EmployeeRequestForm(
            user=request.user,
            initial={'department': getattr(request.user, 'department', '')},
        )
    return render(request, 'employee_requests/request_form.html', {
        'form': form, 'title': 'New Request',
    })


@module_required(MODULE_ERMS)
def erms_request_edit(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    if record.requested_by_id != request.user.pk and not request.user.is_superuser:
        return _deny(request)
    if record.status not in EDITABLE_STATUSES:
        messages.error(request, 'This request cannot be edited.')
        return redirect('erms_request_detail', pk=pk)
    if request.method == 'POST':
        form = EmployeeRequestForm(request.POST, instance=record, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Request updated.')
            return redirect('erms_request_detail', pk=pk)
    else:
        form = EmployeeRequestForm(instance=record, user=request.user)
    return render(request, 'employee_requests/request_form.html', {
        'form': form, 'title': 'Edit Request', 'record': record,
    })


@module_required(MODULE_ERMS)
def erms_request_detail(request, pk):
    record = get_object_or_404(
        EmployeeRequest.objects.select_related(
            'request_type', 'requested_by', 'submitted_to',
        ).prefetch_related('attachments', 'approval_history__performed_by'),
        pk=pk,
    )
    if not can_view_request(request.user, record):
        return _deny(request)
    from .services import can_user_approve
    return render(request, 'employee_requests/request_detail.html', {
        'record': record,
        'can_edit': record.requested_by_id == request.user.pk and record.status in EDITABLE_STATUSES,
        'can_approve': can_user_approve(request.user, record),
        'submit_form': RequestSubmitForm(),
        'action_form': RequestActionForm(),
        'attachment_form': RequestAttachmentForm(),
    })


@module_required(MODULE_ERMS)
@require_POST
def erms_request_submit(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    if record.requested_by_id != request.user.pk:
        return _deny(request)
    form = RequestSubmitForm(request.POST)
    if form.is_valid():
        try:
            submit_request(record, request.user, form.cleaned_data.get('remarks', ''))
            messages.success(request, f'Request submitted — {record.request_number}.')
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
    return redirect('erms_request_detail', pk=pk)


@module_required(MODULE_ERMS_APPROVE)
@require_POST
def erms_request_approve(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    form = RequestActionForm(request.POST)
    if form.is_valid():
        try:
            approve_request(record, request.user, form.cleaned_data['remarks'])
            messages.success(request, 'Request approved.')
        except PermissionError as exc:
            messages.error(request, str(exc))
    return redirect('erms_request_detail', pk=pk)


@module_required(MODULE_ERMS_APPROVE)
@require_POST
def erms_request_reject(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    form = RequestActionForm(request.POST)
    if form.is_valid():
        try:
            reject_request(record, request.user, form.cleaned_data['remarks'])
            messages.success(request, 'Request rejected.')
        except PermissionError as exc:
            messages.error(request, str(exc))
    return redirect('erms_request_detail', pk=pk)


@module_required(MODULE_ERMS_APPROVE)
@require_POST
def erms_request_return(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    form = RequestActionForm(request.POST)
    if form.is_valid():
        try:
            return_request(record, request.user, form.cleaned_data['remarks'])
            messages.success(request, 'Request returned for correction.')
        except PermissionError as exc:
            messages.error(request, str(exc))
    return redirect('erms_request_detail', pk=pk)


@module_required(MODULE_ERMS)
@require_POST
def erms_attachment_upload(request, pk):
    record = get_object_or_404(EmployeeRequest, pk=pk)
    if record.requested_by_id != request.user.pk or record.status not in EDITABLE_STATUSES:
        return _deny(request)
    form = RequestAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        f = form.cleaned_data['file']
        RequestAttachment.objects.create(
            request=record,
            file=f,
            original_name=f.name,
            uploaded_by=request.user,
        )
        messages.success(request, 'Attachment uploaded.')
    else:
        messages.error(request, 'Invalid attachment.')
    return redirect('erms_request_detail', pk=pk)


@module_required(MODULE_ERMS)
def erms_notifications(request):
    notes = PortalNotification.objects.filter(user=request.user).select_related('related_request')[:50]
    return render(request, 'employee_requests/notifications.html', {'notifications': notes})


@module_required(MODULE_ERMS)
@require_POST
def erms_notifications_read(request):
    PortalNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'Notifications marked as read.')
    return redirect('erms_notifications')


@module_required(MODULE_ERMS)
def erms_reports_index(request):
    return render(request, 'employee_requests/reports_index.html', {
        'types': RequestType.objects.filter(is_active=True),
    })


@module_required(MODULE_ERMS)
def erms_report_register(request):
    form = RequestFilterForm(request.GET or None)
    filters = {}
    if form.is_valid():
        if form.cleaned_data.get('request_type'):
            filters['request_type'] = form.cleaned_data['request_type'].pk
        if form.cleaned_data.get('status'):
            filters['status'] = form.cleaned_data['status']
        if form.cleaned_data.get('department'):
            filters['department'] = form.cleaned_data['department']
        if form.cleaned_data.get('employee'):
            filters['employee'] = form.cleaned_data['employee'].pk
    records = register_list_qs(request.user, filters)[:500]
    return render(request, 'employee_requests/report_register.html', {
        'records': records, 'filter_form': form,
    })


@module_required(MODULE_ERMS)
def erms_report_type(request, codename):
    rt = get_object_or_404(RequestType, codename=codename.upper(), is_active=True)
    records = register_list_qs(request.user, {'request_type': rt.pk})[:500]
    return render(request, 'employee_requests/report_type.html', {
        'request_type': rt, 'records': records,
    })


@module_required(MODULE_ERMS_APPROVE)
def erms_report_pending(request):
    records = pending_approvals_qs(request.user)
    if can_view_all_requests(request.user):
        from .constants import PENDING_STATUSES
        records = EmployeeRequest.objects.filter(status__in=PENDING_STATUSES).select_related(
            'request_type', 'requested_by', 'submitted_to',
        )
    return render(request, 'employee_requests/report_pending.html', {'records': records})


@module_required(MODULE_ERMS)
def erms_report_history(request):
    from django.db.models import Q
    from .models import RequestApprovalHistory
    if can_view_all_requests(request.user):
        history = RequestApprovalHistory.objects.all()
    else:
        history = RequestApprovalHistory.objects.filter(
            Q(request__requested_by=request.user) | Q(request__submitted_to=request.user),
        )
    history = history.select_related(
        'request', 'performed_by', 'request__request_type',
    ).order_by('-created_at')[:500]
    return render(request, 'employee_requests/report_history.html', {'history': history})


@module_required(MODULE_ERMS)
def erms_report_department(request):
    from django.db.models import Count
    qs = register_list_qs(request.user)
    rows = qs.values('department').annotate(total=Count('id')).order_by('-total')
    return render(request, 'employee_requests/report_department.html', {'rows': rows})


@module_required(MODULE_ERMS)
def erms_report_employee(request):
    from django.db.models import Count
    qs = register_list_qs(request.user)
    rows = qs.values(
        'requested_by__username', 'requested_by__first_name', 'requested_by__last_name',
    ).annotate(total=Count('id')).order_by('-total')
    return render(request, 'employee_requests/report_employee.html', {'rows': rows})
