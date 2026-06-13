from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access_control import REASON_UNAUTHORIZED
from accounts.decorators import access_denied_response, module_required
from accounts.permissions import (
    MODULE_ENQUIRIES,
    MODULE_ENQUIRIES_MANAGE,
    MODULE_SITE_PROGRESS,
    can_manage_enquiries,
)
from accounts.roles import (
    user_role,
    ROLE_DIRECTOR,
    ROLE_ENGINEER,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_TECHNICIAN,
)
from .forms import EnquiryForm, SiteProgressUpdateForm
from .models import Enquiry, SiteProgressUpdate
from .services import convert_enquiry_to_order


def _enquiries_for_user(user):
    qs = Enquiry.objects.select_related(
        'client', 'assigned_project_manager', 'assigned_supervisor',
    ).order_by('-enquiry_date')
    role = user_role(user)
    if user.is_superuser or role in (ROLE_DIRECTOR, ROLE_OPERATIONS):
        return qs
    if role == ROLE_PROJECT_MANAGER:
        return qs.filter(
            Q(assigned_project_manager=user) | Q(assigned_to=user) | Q(created_by=user),
        )
    if role == ROLE_SUPERVISOR:
        return qs.filter(
            Q(assigned_supervisor=user) | Q(assigned_to=user),
        )
    if role in (ROLE_ENGINEER, ROLE_TECHNICIAN):
        return qs.filter(survey_engineer=user)
    return qs.none()


def _can_access_enquiry(user, enquiry):
    return _enquiries_for_user(user).filter(pk=enquiry.pk).exists()


@module_required(MODULE_ENQUIRIES)
def enquiry_list(request):
    enquiries = _enquiries_for_user(request.user)
    status = request.GET.get('status')
    if status:
        enquiries = enquiries.filter(status=status)
    return render(request, 'enquiries/enquiry_list.html', {
        'enquiries': enquiries,
        'status_filter': status,
        'status_choices': Enquiry.STATUS_CHOICES,
        'can_manage': can_manage_enquiries(request.user),
    })


@module_required(MODULE_ENQUIRIES_MANAGE)
def create_enquiry(request):
    if request.method == 'POST':
        form = EnquiryForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.created_by = request.user
            if enquiry.status == Enquiry.STATUS_NEW and enquiry.assigned_project_manager:
                enquiry.status = Enquiry.STATUS_ASSIGNED
            enquiry.save()
            from company_settings.field_ops import is_auto_survey_schedule_enabled
            if is_auto_survey_schedule_enabled() and enquiry.survey_engineer_id:
                from scheduling.survey_schedule import ensure_survey_schedule
                ensure_survey_schedule(enquiry, created_by=request.user)
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_ENQUIRY_PROCESSED
            log_activity(
                request.user, ACT_ENQUIRY_PROCESSED,
                related_document=enquiry.enquiry_number,
                related_model='Enquiry',
                related_object_id=enquiry.pk,
            )
            from case_intelligence.integrations import enquiry_created
            enquiry_created(request.user, enquiry)
            messages.success(request, f'Enquiry {enquiry.enquiry_number} created.')
            return redirect('enquiry_detail', pk=enquiry.pk)
    else:
        form = EnquiryForm(initial={'status': Enquiry.STATUS_NEW})
    return render(request, 'enquiries/enquiry_form.html', {
        'form': form,
        'page_title': 'Create Enquiry',
    })


@module_required(MODULE_ENQUIRIES)
def enquiry_detail(request, pk):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related(
            'client', 'assigned_project_manager', 'assigned_supervisor',
            'survey_engineer', 'converted_order',
        ),
        pk=pk,
    )
    if not _can_access_enquiry(request.user, enquiry):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)

    estimate_boqs = enquiry.estimate_boqs.all().order_by('-created_at')
    quotations = enquiry.quotations.all().order_by('-created_at')
    site_updates = enquiry.site_updates.all()[:10]
    survey_schedule = getattr(enquiry, 'field_schedule', None)
    survey_wcr = getattr(enquiry, 'survey_wcr', None)
    site_attendance = None
    if survey_schedule:
        from productivity.models import ScheduleSiteAttendance
        site_attendance = ScheduleSiteAttendance.objects.filter(
            schedule=survey_schedule, employee=request.user,
        ).first()

    from case_intelligence.constants import MOD_ENQUIRY
    from case_intelligence.services import panel_context, _pending_for_enquiry, _next_for_enquiry
    case_ctx = panel_context(
        enquiry,
        module=MOD_ENQUIRY,
        document_number=enquiry.enquiry_number,
        status=enquiry.get_status_display(),
        stage=enquiry.get_status_display(),
        assigned_to=str(enquiry.survey_engineer or enquiry.assigned_project_manager or '—'),
        pending_action=_pending_for_enquiry(enquiry),
        next_action=_next_for_enquiry(enquiry),
    )

    return render(request, 'enquiries/enquiry_detail.html', {
        'enquiry': enquiry,
        'estimate_boqs': estimate_boqs,
        'quotations': quotations,
        'site_updates': site_updates,
        'survey_schedule': survey_schedule,
        'survey_wcr': survey_wcr,
        'site_attendance': site_attendance,
        'can_manage': can_manage_enquiries(request.user),
        'can_convert': enquiry.can_convert_to_order and can_manage_enquiries(request.user),
        'can_create_estimate': can_manage_enquiries(request.user),
        'can_create_quotation': can_manage_enquiries(request.user),
        **case_ctx,
    })


@module_required(MODULE_ENQUIRIES_MANAGE)
def edit_enquiry(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    if not _can_access_enquiry(request.user, enquiry):
        return access_denied_response(request, reason=REASON_UNAUTHORIZED)
    if request.method == 'POST':
        form = EnquiryForm(request.POST, instance=enquiry)
        if form.is_valid():
            old_status = enquiry.status
            enquiry = form.save()
            if enquiry.status != old_status:
                from productivity.gps_service import record_survey_status_gps
                record_survey_status_gps(request.user, enquiry, old_status, enquiry.status, request)
                from case_intelligence.integrations import enquiry_status_changed
                enquiry_status_changed(request.user, enquiry, old_status)
            from company_settings.field_ops import is_auto_survey_schedule_enabled
            if is_auto_survey_schedule_enabled() and enquiry.survey_engineer_id:
                from scheduling.survey_schedule import ensure_survey_schedule
                schedule, _ = ensure_survey_schedule(enquiry, created_by=request.user)
                if schedule:
                    messages.info(request, f'Survey schedule {schedule.schedule_number} updated.')
            messages.success(request, 'Enquiry updated.')
            return redirect('enquiry_detail', pk=pk)
    else:
        form = EnquiryForm(instance=enquiry)
    return render(request, 'enquiries/enquiry_form.html', {
        'form': form,
        'enquiry': enquiry,
        'page_title': f'Edit {enquiry.enquiry_number}',
    })


@module_required(MODULE_ENQUIRIES_MANAGE)
def convert_enquiry_order(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk)
    if request.method == 'POST':
        try:
            order = convert_enquiry_to_order(enquiry, request.user)
            from case_intelligence.integrations import order_converted_from_enquiry
            order_converted_from_enquiry(request.user, order, enquiry)
            messages.success(request, f'Order {order.order_no} created from enquiry.')
            return redirect('order_detail', pk=order.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect('enquiry_detail', pk=pk)


@module_required(MODULE_SITE_PROGRESS)
def site_progress_create(request):
    if request.method == 'POST':
        form = SiteProgressUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            update = form.save(commit=False)
            update.supervisor = request.user
            update.save()
            messages.success(request, 'Site progress update saved.')
            if update.enquiry_id:
                return redirect('enquiry_detail', pk=update.enquiry_id)
            if update.order_id:
                return redirect('order_detail', pk=update.order_id)
            return redirect('supervisor_dashboard')
    else:
        initial = {}
        if request.GET.get('enquiry'):
            initial['enquiry'] = request.GET.get('enquiry')
        if request.GET.get('order'):
            initial['order'] = request.GET.get('order')
        form = SiteProgressUpdateForm(initial=initial)
    return render(request, 'enquiries/site_progress_form.html', {'form': form})
