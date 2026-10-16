from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access_control import REASON_UNAUTHORIZED
from accounts.decorators import access_denied_response, module_required

from .forms import (
    CloseForm,
    HoldForm,
    NoteForm,
    RemapForm,
    ResumeForm,
    ScheduleForm,
    TaskCreateForm,
    initial_schedule,
)
from .models import TeamTask
from .permissions import MODULE_TASK_MANAGER, can_act_on_task, can_view_all_tasks, can_view_task
from .services import (
    TaskWorkflowError,
    add_note,
    apply_list_filters,
    attention_tasks,
    close_task,
    create_task,
    dashboard_stats,
    history_for_user,
    hold_task,
    record_due_reminders,
    remap_task,
    resume_task,
    schedule_task,
    start_task,
    tasks_for_user,
)


def _deny(request):
    return access_denied_response(request, reason=REASON_UNAUTHORIZED)


def _task_or_deny(request, pk):
    task = get_object_or_404(
        TeamTask.objects.select_related('assignee', 'created_by', 'related_order'),
        pk=pk,
    )
    if not can_view_task(request.user, task):
        return task, _deny(request)
    return task, None


@module_required(MODULE_TASK_MANAGER)
def task_dashboard(request):
    record_due_reminders()
    qs = tasks_for_user(request.user)
    return render(request, 'task_manager/dashboard.html', {
        'stats': dashboard_stats(qs),
        'attention': attention_tasks(qs),
        'recent': qs.order_by('-updated_at')[:12],
        'can_view_all': can_view_all_tasks(request.user),
    })


@module_required(MODULE_TASK_MANAGER)
def task_list(request):
    record_due_reminders()
    qs = apply_list_filters(tasks_for_user(request.user), request.GET, request.user)
    return render(request, 'task_manager/task_list.html', {
        'tasks': qs[:200],
        'filters': request.GET,
        'status_choices': TeamTask.STATUS_CHOICES,
        'priority_choices': TeamTask.PRIORITY_CHOICES,
        'can_view_all': can_view_all_tasks(request.user),
    })


@module_required(MODULE_TASK_MANAGER)
def task_create(request):
    if request.method == 'POST':
        form = TaskCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                task = create_task(
                    user=request.user,
                    title=data['title'],
                    description=data['description'],
                    assignee=data['assignee'],
                    priority=data['priority'],
                    scheduled_on=data.get('scheduled_on'),
                    due_on=data.get('due_on'),
                    remind_after_days=data['remind_after_days'],
                    related_order=data.get('related_order'),
                    remarks=data.get('remarks') or '',
                )
            except TaskWorkflowError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f'Task {task.task_number} created.')
                return redirect('task_detail', pk=task.pk)
    else:
        form = TaskCreateForm(initial={
            'assignee': request.user.pk,
            'priority': TeamTask.PRIORITY_MEDIUM,
            'remind_after_days': 3,
        })
    return render(request, 'task_manager/task_form.html', {'form': form})


@module_required(MODULE_TASK_MANAGER)
def task_detail(request, pk):
    record_due_reminders()
    task, denied = _task_or_deny(request, pk)
    if denied:
        return denied
    task = TeamTask.objects.select_related(
        'assignee', 'created_by', 'related_order',
    ).prefetch_related('history__actor', 'history__from_assignee', 'history__to_assignee').get(pk=task.pk)

    can_act = can_act_on_task(request.user, task)
    schedule_form = ScheduleForm(initial=initial_schedule(task), prefix='schedule')
    remap_form = RemapForm(task=task, prefix='remap')
    hold_form = HoldForm(
        initial={'remind_after_days': task.remind_after_days},
        prefix='hold',
    )
    close_form = CloseForm(prefix='close')
    note_form = NoteForm(prefix='note')
    resume_form = ResumeForm(prefix='resume')

    if request.method == 'POST':
        if not can_act:
            messages.error(request, 'This task is closed and cannot be changed.')
            return redirect('task_detail', pk=task.pk)
        action = request.POST.get('action')
        try:
            if action == 'schedule':
                schedule_form = ScheduleForm(request.POST, prefix='schedule')
                if schedule_form.is_valid():
                    data = schedule_form.cleaned_data
                    schedule_task(
                        task, request.user,
                        scheduled_on=data.get('scheduled_on'),
                        due_on=data.get('due_on'),
                        remind_after_days=data.get('remind_after_days'),
                        remarks=data.get('remarks') or '',
                    )
                    messages.success(request, 'Schedule saved.')
                    return redirect('task_detail', pk=task.pk)
            elif action == 'start':
                start_task(task, request.user)
                messages.success(request, 'Task started.')
                return redirect('task_detail', pk=task.pk)
            elif action == 'remap':
                remap_form = RemapForm(request.POST, task=task, prefix='remap')
                if remap_form.is_valid():
                    remap_task(
                        task, request.user,
                        new_assignee=remap_form.cleaned_data['assignee'],
                        remarks=remap_form.cleaned_data['remarks'],
                    )
                    messages.success(request, 'Task forwarded.')
                    return redirect('task_detail', pk=task.pk)
            elif action == 'hold':
                hold_form = HoldForm(request.POST, prefix='hold')
                if hold_form.is_valid():
                    hold_task(
                        task, request.user,
                        remarks=hold_form.cleaned_data['remarks'],
                        remind_after_days=hold_form.cleaned_data['remind_after_days'],
                    )
                    messages.success(request, 'Task placed on hold.')
                    return redirect('task_detail', pk=task.pk)
            elif action == 'resume':
                resume_form = ResumeForm(request.POST, prefix='resume')
                if resume_form.is_valid():
                    resume_task(task, request.user, remarks=resume_form.cleaned_data.get('remarks') or '')
                    messages.success(request, 'Task resumed.')
                    return redirect('task_detail', pk=task.pk)
            elif action == 'note':
                note_form = NoteForm(request.POST, prefix='note')
                if note_form.is_valid():
                    add_note(task, request.user, note_form.cleaned_data['remarks'])
                    messages.success(request, 'Update added to the history.')
                    return redirect('task_detail', pk=task.pk)
            elif action == 'close':
                close_form = CloseForm(request.POST, prefix='close')
                if close_form.is_valid():
                    close_task(task, request.user, remarks=close_form.cleaned_data['remarks'])
                    messages.success(request, 'Task closed.')
                    return redirect('task_detail', pk=task.pk)
            else:
                messages.error(request, 'Unknown action.')
        except TaskWorkflowError as exc:
            messages.error(request, str(exc))

    return render(request, 'task_manager/task_detail.html', {
        'task': task,
        'history': task.history.all(),
        'can_act': can_act,
        'schedule_form': schedule_form,
        'remap_form': remap_form,
        'hold_form': hold_form,
        'close_form': close_form,
        'note_form': note_form,
        'resume_form': resume_form,
    })


@module_required(MODULE_TASK_MANAGER)
def task_history(request):
    record_due_reminders()
    events = history_for_user(request.user)
    query = (request.GET.get('q') or '').strip()
    action = (request.GET.get('action') or '').strip()
    if query:
        from django.db.models import Q
        events = events.filter(
            Q(task__task_number__icontains=query)
            | Q(task__title__icontains=query)
            | Q(remarks__icontains=query)
        )
    if action:
        events = events.filter(action=action)
    return render(request, 'task_manager/task_history.html', {
        'events': events[:300],
        'filters': request.GET,
        'action_choices': history_action_choices(),
    })


def history_action_choices():
    from .models import TaskHistory
    return TaskHistory.ACTION_CHOICES
