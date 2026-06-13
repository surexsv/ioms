from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET

from accounts.decorators import module_required, access_denied_response
from accounts.permissions import MODULE_WCR, MODULE_WCR_APPROVE, can_access
from company_settings.permissions import can_edit_document_signatory
from productivity.activity_logger import log_activity
from productivity.calculator import (
    build_participants_from_schedule,
    recalculate_monthly_snapshot,
    sync_wcr_participants,
)
from productivity.constants import ACT_WCR_SUBMITTED, ACT_WCR_VERIFIED
from orders.models import Order

from .models import WorkCompletionReport, WCR_TYPE_SURVEY
from .forms import WCRForm, WCRParticipantFormSet, SurveyWCRForm
from .survey_services import complete_survey_wcr, survey_wcr_exists_for_schedule


def _save_wcr_participants(request, wcr):
    """Parse team participant rows from POST."""
    participants = []
    indices = set()
    for key in request.POST:
        if key.startswith('participants-') and '-employee' in key:
            idx = key.split('-')[1]
            indices.add(idx)
    for idx in sorted(indices, key=lambda x: int(x) if x.isdigit() else 0):
        prefix = f'participants-{idx}-'
        if request.POST.get(f'{prefix}DELETE'):
            continue
        attended = request.POST.get(f'{prefix}attended') == 'on'
        if not attended:
            continue
        emp_id = request.POST.get(f'{prefix}employee')
        if not emp_id:
            continue
        from accounts.models import User
        try:
            employee = User.objects.get(pk=emp_id)
        except User.DoesNotExist:
            continue
        hours = request.POST.get(f'{prefix}hours_worked') or '0'
        man_days = request.POST.get(f'{prefix}man_days') or '0'
        participants.append({
            'employee': employee,
            'participant_role': request.POST.get(f'{prefix}participant_role', 'TECHNICIAN'),
            'attended': True,
            'hours_worked': hours,
            'man_days': man_days,
            'from_schedule': request.POST.get(f'{prefix}from_schedule') == '1',
        })
    # Deduplicate by employee — form may repeat the same person across rows
    deduped = []
    seen = set()
    for p in participants:
        eid = p['employee'].pk
        if eid not in seen:
            seen.add(eid)
            deduped.append(p)
    participants = deduped
    if participants:
        sync_wcr_participants(wcr, participants)
    elif wcr.schedule:
        sync_wcr_participants(wcr, build_participants_from_schedule(wcr.schedule, wcr))
    for part in wcr.team_participants.all():
        recalculate_monthly_snapshot(part.employee)


@module_required(MODULE_WCR)
def wcr_list(request):
    wcrs = WorkCompletionReport.objects.select_related(
        'order', 'order__client', 'enquiry', 'enquiry__client', 'submitted_by', 'schedule',
    ).prefetch_related('team_participants').order_by('-submitted_date')
    if request.user.role in ('ENGINEER', 'Technician'):
        wcrs = wcrs.filter(submitted_by=request.user)
    pending_only = request.GET.get('pending')
    if pending_only:
        wcrs = wcrs.filter(approved=False)
    return render(request, 'wcr/wcr_list.html', {
        'wcrs': wcrs,
        'pending_only': pending_only,
        'can_approve': can_access(request.user, MODULE_WCR_APPROVE),
    })


@module_required(MODULE_WCR)
def create_wcr(request):
    schedule_team = []
    selected_order = None
    if request.method == 'POST':
        form = WCRForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                wcr = form.save(commit=False)
                wcr.submitted_by = request.user
                order = wcr.order
                wcr.schedule = getattr(order, 'work_schedule', None)
                wcr.save()
                _save_wcr_participants(request, wcr)
            log_activity(
                request.user, ACT_WCR_SUBMITTED,
                related_document=wcr.wcr_number,
                related_model='WorkCompletionReport',
                related_object_id=wcr.pk,
            )
            from case_intelligence.integrations import wcr_submitted
            wcr_submitted(request.user, wcr)
            from productivity.field_constants import FA_WCR_SUBMITTED
            from productivity.gps_service import record_field_event
            record_field_event(
                request.user, FA_WCR_SUBMITTED,
                request=request,
                order=order,
                schedule=wcr.schedule,
                wcr=wcr,
                remarks=f'WCR {wcr.wcr_number} submitted',
            )
            messages.success(request, f'WCR {wcr.wcr_number} submitted with team productivity recorded.')
            return redirect('wcr_list')
    else:
        form = WCRForm(user=request.user)
        order_id = request.GET.get('order')
        if order_id:
            selected_order = Order.objects.filter(pk=order_id).first()
            if selected_order:
                form.initial['order'] = selected_order.pk
                schedule = getattr(selected_order, 'work_schedule', None)
                if schedule:
                    schedule_team = build_participants_from_schedule(schedule)

    return render(request, 'wcr/wcr_form.html', {
        'form': form,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
        'schedule_team': schedule_team,
        'selected_order': selected_order,
    })


@require_GET
@module_required(MODULE_WCR)
def schedule_team_json(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    schedule = getattr(order, 'work_schedule', None)
    if not schedule:
        return JsonResponse({'team': []})
    rows = build_participants_from_schedule(schedule)
    team = [
        {
            'employee_id': r['employee'].pk,
            'name': r['employee'].get_full_name() or r['employee'].username,
            'role': r['participant_role'],
            'hours_worked': str(r.get('hours_worked', 0)),
            'man_days': str(r.get('man_days', 0)),
        }
        for r in rows
    ]
    return JsonResponse({'team': team, 'schedule_number': schedule.schedule_number})


@module_required(MODULE_WCR_APPROVE)
def approve_wcr(request, pk):
    wcr = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        wcr.approved = True
        wcr.save()
        log_activity(
            request.user, ACT_WCR_VERIFIED,
            related_document=wcr.wcr_number,
            related_model='WorkCompletionReport',
            related_object_id=wcr.pk,
        )
        from productivity.field_constants import FA_WCR_APPROVED
        from productivity.gps_service import record_field_event
        record_field_event(
            request.user, FA_WCR_APPROVED,
            request=request,
            order=wcr.order,
            schedule=wcr.schedule,
            wcr=wcr,
            remarks=f'WCR {wcr.wcr_number} approved',
        )
        for part in wcr.team_participants.filter(attended=True):
            recalculate_monthly_snapshot(part.employee)
        if wcr.wcr_type == WCR_TYPE_SURVEY:
            complete_survey_wcr(wcr, request.user)
            from case_intelligence.integrations import survey_completed
            if wcr.enquiry_id:
                survey_completed(request.user, wcr.enquiry, remarks=wcr.wcr_number)
            messages.success(request, f'Survey WCR {wcr.wcr_number} approved. Enquiry updated.')
        elif wcr.order_id:
            messages.success(request, f'WCR for Order #{wcr.order.order_id} approved.')
        else:
            messages.success(request, f'WCR {wcr.wcr_number} approved.')
        return redirect('wcr_list')
    return render(request, 'wcr/wcr_approve.html', {'wcr': wcr})


@module_required(MODULE_WCR)
def create_survey_wcr(request, schedule_pk):
    from scheduling.models import WorkSchedule
    from scheduling.engine import user_on_schedule_team
    schedule = get_object_or_404(
        WorkSchedule.objects.select_related('enquiry', 'enquiry__client'),
        pk=schedule_pk,
    )
    if not schedule.enquiry_id:
        messages.error(request, 'This schedule is not a survey enquiry schedule.')
        return redirect('schedule_list')
    if not user_on_schedule_team(schedule, request.user) and not can_access(request.user, MODULE_WCR_APPROVE):
        return access_denied_response(request, module_key='wcr')
    if survey_wcr_exists_for_schedule(schedule):
        messages.info(request, 'Survey WCR already exists for this enquiry.')
        from accounts.navigation import redirect_target_after_schedule
        target = redirect_target_after_schedule(request.user, schedule)
        if len(target) == 2:
            return redirect(target[0], pk=target[1])
        return redirect(target[0])

    schedule_team = build_participants_from_schedule(schedule)
    if request.method == 'POST':
        form = SurveyWCRForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                wcr = form.save(commit=False)
                wcr.wcr_type = WCR_TYPE_SURVEY
                wcr.enquiry = schedule.enquiry
                wcr.schedule = schedule
                wcr.submitted_by = request.user
                wcr.save()
                _save_wcr_participants(request, wcr)
                schedule.status = WorkSchedule.STATUS_IN_PROGRESS
                schedule.save(update_fields=['status', 'updated_at'])
            log_activity(
                request.user, ACT_WCR_SUBMITTED,
                related_document=wcr.wcr_number,
                related_model='WorkCompletionReport',
                related_object_id=wcr.pk,
                remarks='Survey WCR',
            )
            from case_intelligence.integrations import wcr_submitted
            wcr_submitted(request.user, wcr, remarks='Survey WCR')
            from productivity.field_constants import FA_WCR_SUBMITTED
            from productivity.gps_service import record_field_event
            record_field_event(
                request.user, FA_WCR_SUBMITTED,
                request=request,
                enquiry=schedule.enquiry,
                schedule=schedule,
                wcr=wcr,
                remarks=f'Survey WCR {wcr.wcr_number}',
            )
            messages.success(request, f'Survey WCR {wcr.wcr_number} submitted.')
            from accounts.navigation import redirect_target_after_schedule
            target = redirect_target_after_schedule(request.user, schedule)
            if len(target) == 2:
                return redirect(target[0], pk=target[1])
            return redirect(target[0])
    else:
        form = SurveyWCRForm(user=request.user)

    from accounts.navigation import wcr_back_navigation
    return render(request, 'wcr/survey_wcr_form.html', {
        'form': form,
        'schedule': schedule,
        'enquiry': schedule.enquiry,
        'schedule_team': schedule_team,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
        'back_nav': wcr_back_navigation(request.user, schedule=schedule),
    })
