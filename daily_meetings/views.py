from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import module_required, access_denied_response
from accounts.permissions import MODULE_DAILY_MEETINGS, MODULE_DAILY_MEETINGS_MANAGE

from .forms import (
    ActionFilterForm, AgendaTemplateItemForm, DailyMeetingForm,
    ManagementMessageForm, MeetingActionItemForm, MeetingAttendanceForm,
    MeetingDiscussionForm, MeetingFilterForm, OpenItemRegisterForm, ReportMonthForm,
)
from .models import (
    AgendaTemplateItem, DailyMeeting, ManagementMessage,
    MeetingActionItem, MeetingAttendance, MeetingDiscussion, OpenItemRegister,
)
from .permissions import (
    can_access_daily_meetings, can_create_meeting, can_edit_meeting,
    can_manage_agenda_template, can_manage_meetings, can_manage_open_items,
    can_update_actions, can_view_action, can_view_all_meetings, field_team_action_only,
)
from .pdf import build_mom_pdf
from .services import (
    create_daily_meeting, dashboard_summary, effectiveness_report,
    meeting_attendance_stats, meeting_register, mom_context,
    refresh_overdue_actions, seed_agenda_template, seed_open_items,
    sync_meeting_attendance,
)


def _deny(request):
    return access_denied_response(request, module_key='daily_meetings')


@module_required(MODULE_DAILY_MEETINGS)
def dom_dashboard(request):
    if not can_access_daily_meetings(request.user):
        return _deny(request)
    if field_team_action_only(request.user):
        return redirect('dom_action_tracker')
    summary = dashboard_summary()
    recent = DailyMeeting.objects.select_related('conducted_by').order_by('-meeting_date')[:8]
    return render(request, 'daily_meetings/dashboard.html', {
        'summary': summary,
        'recent_meetings': recent,
        'can_create_meeting': can_create_meeting(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS)
def meeting_list(request):
    if field_team_action_only(request.user):
        return redirect('dom_action_tracker')
    qs = DailyMeeting.objects.select_related('conducted_by', 'created_by').order_by('-meeting_date')
    form = MeetingFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('date_from'):
            qs = qs.filter(meeting_date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data.get('date_to'):
            qs = qs.filter(meeting_date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data.get('status'):
            qs = qs.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('meeting_type'):
            qs = qs.filter(meeting_type=form.cleaned_data['meeting_type'])
    return render(request, 'daily_meetings/meeting_list.html', {
        'meetings': qs[:100],
        'filter_form': form,
        'can_create': can_create_meeting(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def meeting_create(request):
    if not can_create_meeting(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = DailyMeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_by = request.user
            meeting.save()
            from .services import apply_agenda_template, attach_open_items_to_meeting
            apply_agenda_template(meeting)
            attach_open_items_to_meeting(meeting)
            sync_meeting_attendance(meeting)
            messages.success(request, f'Meeting {meeting.meeting_number} created.')
            return redirect('dom_meeting_detail', pk=meeting.pk)
    else:
        settings = __import__('daily_meetings.services', fromlist=['get_settings']).get_settings()
        form = DailyMeetingForm(initial={
            'meeting_date': timezone.localdate(),
            'meeting_time': settings.meeting_start_time,
            'conducted_by': request.user,
            'status': DailyMeeting.STATUS_DRAFT,
        })
    return render(request, 'daily_meetings/meeting_form.html', {
        'form': form, 'title': 'Create Daily Meeting',
    })


@module_required(MODULE_DAILY_MEETINGS)
def meeting_today(request):
    if not can_manage_meetings(request.user):
        return _deny(request)
    meeting, created = create_daily_meeting(request.user)
    if created:
        messages.success(request, f"Today's meeting {meeting.meeting_number} created.")
    else:
        messages.info(request, f"Today's meeting already exists: {meeting.meeting_number}.")
    return redirect('dom_meeting_detail', pk=meeting.pk)


@module_required(MODULE_DAILY_MEETINGS)
def meeting_detail(request, pk):
    meeting = get_object_or_404(
        DailyMeeting.objects.select_related('conducted_by', 'created_by'),
        pk=pk,
    )
    if field_team_action_only(request.user):
        return redirect('dom_action_tracker')
    if not can_view_all_meetings(request.user) and not can_manage_meetings(request.user):
        return _deny(request)
    att_stats = meeting_attendance_stats(meeting)
    return render(request, 'daily_meetings/meeting_detail.html', {
        'meeting': meeting,
        'att_stats': att_stats,
        'can_edit': can_edit_meeting(request.user, meeting),
        'can_sync_attendance': can_manage_meetings(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def meeting_edit(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_edit_meeting(request.user, meeting):
        return _deny(request)
    if request.method == 'POST':
        form = DailyMeetingForm(request.POST, instance=meeting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meeting updated.')
            return redirect('dom_meeting_detail', pk=pk)
    else:
        form = DailyMeetingForm(instance=meeting)
    return render(request, 'daily_meetings/meeting_form.html', {
        'form': form, 'title': 'Edit Meeting', 'meeting': meeting,
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def meeting_sync_attendance(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_manage_meetings(request.user):
        return _deny(request)
    count = sync_meeting_attendance(meeting)
    messages.success(request, f'Attendance synced for {count} employee(s) from Attendance module.')
    return redirect('dom_meeting_detail', pk=pk)


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def meeting_complete(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_manage_meetings(request.user):
        return _deny(request)
    meeting.status = DailyMeeting.STATUS_COMPLETED
    meeting.save(update_fields=['status', 'updated_at'])
    messages.success(request, 'Meeting marked as completed.')
    return redirect('dom_meeting_detail', pk=pk)


@module_required(MODULE_DAILY_MEETINGS)
def meeting_attendance_edit(request, pk, att_pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    att = get_object_or_404(MeetingAttendance, pk=att_pk, meeting=meeting)
    if not can_manage_meetings(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = MeetingAttendanceForm(request.POST, instance=att)
        if form.is_valid():
            form.save()
            messages.success(request, 'Attendance updated (manual override).')
            return redirect('dom_meeting_detail', pk=pk)
    else:
        form = MeetingAttendanceForm(instance=att)
    return render(request, 'daily_meetings/attendance_edit.html', {
        'form': form, 'meeting': meeting, 'attendance': att,
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def discussion_add(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_manage_meetings(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = MeetingDiscussionForm(request.POST)
        if form.is_valid():
            disc = form.save(commit=False)
            disc.meeting = meeting
            disc.save()
            messages.success(request, 'Discussion recorded.')
            return redirect('dom_meeting_detail', pk=pk)
    else:
        form = MeetingDiscussionForm()
    return render(request, 'daily_meetings/discussion_form.html', {
        'form': form, 'meeting': meeting, 'title': 'Add Discussion',
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def message_add(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_manage_meetings(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = ManagementMessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.meeting = meeting
            msg.created_by = request.user
            msg.save()
            messages.success(request, 'Management message added.')
            return redirect('dom_meeting_detail', pk=pk)
    else:
        form = ManagementMessageForm(initial={'message_date': meeting.meeting_date})
    return render(request, 'daily_meetings/message_form.html', {
        'form': form, 'meeting': meeting,
    })


@module_required(MODULE_DAILY_MEETINGS)
def action_add(request, pk=None):
    meeting = None
    if pk:
        meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_manage_meetings(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = MeetingActionItemForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.meeting = meeting
            action.created_by = request.user
            action.save()
            messages.success(request, f'Action {action.action_number} created.')
            if meeting:
                return redirect('dom_meeting_detail', pk=meeting.pk)
            return redirect('dom_action_tracker')
    else:
        form = MeetingActionItemForm()
    return render(request, 'daily_meetings/action_form.html', {
        'form': form, 'meeting': meeting, 'title': 'Add Action Item',
    })


@module_required(MODULE_DAILY_MEETINGS)
def action_edit(request, pk):
    action = get_object_or_404(MeetingActionItem, pk=pk)
    if not can_update_actions(request.user) and not can_view_action(request.user, action):
        return _deny(request)
    if request.method == 'POST':
        form = MeetingActionItemForm(request.POST, instance=action)
        if form.is_valid():
            form.save()
            messages.success(request, 'Action item updated.')
            return redirect('dom_action_tracker')
    else:
        form = MeetingActionItemForm(instance=action)
    return render(request, 'daily_meetings/action_form.html', {
        'form': form, 'meeting': action.meeting, 'action': action, 'title': 'Update Action',
    })


@module_required(MODULE_DAILY_MEETINGS)
def action_tracker(request):
    refresh_overdue_actions()
    qs = MeetingActionItem.objects.select_related('assigned_to', 'meeting').order_by('-created_at')
    if field_team_action_only(request.user):
        qs = qs.filter(assigned_to=request.user)
    elif not can_view_all_meetings(request.user):
        qs = qs.filter(assigned_to=request.user)
    form = ActionFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data.get('status'):
            qs = qs.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('assigned_to'):
            qs = qs.filter(assigned_to=form.cleaned_data['assigned_to'])
        if form.cleaned_data.get('priority'):
            qs = qs.filter(priority=form.cleaned_data['priority'])
    return render(request, 'daily_meetings/action_tracker.html', {
        'actions': qs[:200],
        'filter_form': form,
        'can_add': can_manage_meetings(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS)
def open_items_list(request):
    if field_team_action_only(request.user):
        return _deny(request)
    items = OpenItemRegister.objects.select_related('owner').order_by('status', 'title')
    return render(request, 'daily_meetings/open_items.html', {
        'items': items,
        'can_manage': can_manage_open_items(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def open_item_create(request):
    if not can_manage_open_items(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = OpenItemRegisterForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()
            messages.success(request, 'Open item registered.')
            return redirect('dom_open_items')
    else:
        form = OpenItemRegisterForm()
    return render(request, 'daily_meetings/open_item_form.html', {
        'form': form, 'title': 'Add Open Item',
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def open_item_edit(request, pk):
    item = get_object_or_404(OpenItemRegister, pk=pk)
    if not can_manage_open_items(request.user):
        return _deny(request)
    if request.method == 'POST':
        form = OpenItemRegisterForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Open item updated.')
            return redirect('dom_open_items')
    else:
        form = OpenItemRegisterForm(instance=item)
    return render(request, 'daily_meetings/open_item_form.html', {
        'form': form, 'title': 'Edit Open Item', 'item': item,
    })


@module_required(MODULE_DAILY_MEETINGS)
def meeting_calendar(request):
    if field_team_action_only(request.user):
        return redirect('dom_action_tracker')
    year = int(request.GET.get('year', timezone.localdate().year))
    month = int(request.GET.get('month', timezone.localdate().month))
    meetings = DailyMeeting.objects.filter(
        meeting_date__year=year, meeting_date__month=month,
    ).order_by('meeting_date')
    by_date = {}
    for m in meetings:
        by_date.setdefault(m.meeting_date, []).append(m)
    calendar_rows = sorted(by_date.items(), key=lambda x: x[0])
    return render(request, 'daily_meetings/calendar.html', {
        'year': year, 'month': month, 'calendar_rows': calendar_rows,
    })


@module_required(MODULE_DAILY_MEETINGS)
def mom_print(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_view_all_meetings(request.user) and not can_manage_meetings(request.user):
        return _deny(request)
    ctx = mom_context(meeting)
    return render(request, 'daily_meetings/mom_print.html', ctx)


@module_required(MODULE_DAILY_MEETINGS)
def mom_pdf(request, pk):
    meeting = get_object_or_404(DailyMeeting, pk=pk)
    if not can_view_all_meetings(request.user) and not can_manage_meetings(request.user):
        return _deny(request)
    ctx = mom_context(meeting)
    buffer = build_mom_pdf(ctx)
    filename = f'MOM_{meeting.meeting_number}.pdf'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def agenda_template_list(request):
    if not can_manage_agenda_template(request.user) and not can_manage_meetings(request.user):
        return _deny(request)
    items = AgendaTemplateItem.objects.order_by('sort_order')
    if not items.exists():
        seed_agenda_template()
        items = AgendaTemplateItem.objects.order_by('sort_order')
    return render(request, 'daily_meetings/agenda_template.html', {
        'items': items,
        'can_edit': can_manage_agenda_template(request.user),
    })


@module_required(MODULE_DAILY_MEETINGS_MANAGE)
def agenda_template_edit(request, pk):
    if not can_manage_agenda_template(request.user):
        return _deny(request)
    item = get_object_or_404(AgendaTemplateItem, pk=pk)
    if request.method == 'POST':
        form = AgendaTemplateItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agenda item updated.')
            return redirect('dom_agenda_template')
    else:
        form = AgendaTemplateItemForm(instance=item)
    return render(request, 'daily_meetings/agenda_template_form.html', {
        'form': form, 'item': item,
    })


@module_required(MODULE_DAILY_MEETINGS)
def reports_index(request):
    if field_team_action_only(request.user):
        return redirect('dom_action_tracker')
    return render(request, 'daily_meetings/reports_index.html')


@module_required(MODULE_DAILY_MEETINGS)
def report_register(request):
    form = ReportMonthForm(request.GET or None)
    year, month = timezone.localdate().year, timezone.localdate().month
    if form.is_valid():
        year, month = form.cleaned_data['year'], form.cleaned_data['month']
    data = meeting_register(year, month)
    data['form'] = form
    return render(request, 'daily_meetings/report_register.html', data)


@module_required(MODULE_DAILY_MEETINGS)
def report_attendance(request):
    report_date = timezone.localdate()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    meeting = DailyMeeting.objects.filter(meeting_date=report_date).first()
    att_stats = meeting_attendance_stats(meeting) if meeting else {}
    attendees = meeting.attendees.select_related('employee').all() if meeting else []
    return render(request, 'daily_meetings/report_attendance.html', {
        'date': report_date, 'meeting': meeting, 'attendees': attendees, 'att_stats': att_stats,
    })


@module_required(MODULE_DAILY_MEETINGS)
def report_late_attendance(request):
    report_date = timezone.localdate()
    if request.GET.get('date'):
        try:
            report_date = date.fromisoformat(request.GET['date'])
        except ValueError:
            pass
    meeting = DailyMeeting.objects.filter(meeting_date=report_date).first()
    late = []
    if meeting:
        late = meeting.attendees.filter(status=MeetingAttendance.STATUS_LATE).select_related('employee')
    return render(request, 'daily_meetings/report_late.html', {
        'date': report_date, 'meeting': meeting, 'late_attendees': late,
    })


@module_required(MODULE_DAILY_MEETINGS)
def report_actions(request):
    refresh_overdue_actions()
    actions = MeetingActionItem.objects.select_related('assigned_to', 'meeting').order_by('-created_at')[:300]
    return render(request, 'daily_meetings/report_actions.html', {'actions': actions})


@module_required(MODULE_DAILY_MEETINGS)
def report_open_items(request):
    items = OpenItemRegister.objects.select_related('owner').order_by('status', 'title')
    return render(request, 'daily_meetings/report_open_items.html', {'items': items})


@module_required(MODULE_DAILY_MEETINGS)
def report_effectiveness(request):
    year = int(request.GET.get('year', timezone.localdate().year))
    data = effectiveness_report(year)
    return render(request, 'daily_meetings/report_effectiveness.html', data)


@module_required(MODULE_DAILY_MEETINGS)
def report_messages(request):
    messages_qs = ManagementMessage.objects.select_related('meeting', 'created_by').order_by('-message_date')[:200]
    return render(request, 'daily_meetings/report_messages.html', {'messages': messages_qs})
