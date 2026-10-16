from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User

from .models import TaskHistory, TeamTask, reminder_date
from .permissions import can_act_on_task, can_view_all_tasks


class TaskWorkflowError(Exception):
    pass


def assignable_users():
    return User.objects.filter(
        is_active=True,
        is_active_employee=True,
        approval_status=User.APPROVAL_APPROVED,
    ).order_by('first_name', 'last_name', 'username')


def tasks_for_user(user):
    qs = TeamTask.objects.select_related('assignee', 'created_by', 'related_order')
    if can_view_all_tasks(user):
        return qs
    return qs.filter(Q(assignee=user) | Q(created_by=user)).distinct()


def _person(user):
    if not user:
        return '—'
    name = user.get_full_name().strip()
    return name or user.username


def _log(task, action, actor, remarks='', from_status='', to_status='', from_user=None, to_user=None):
    return TaskHistory.objects.create(
        task=task,
        action=action,
        actor=actor,
        remarks=remarks or '',
        from_status=from_status or '',
        to_status=to_status or '',
        from_assignee=from_user,
        to_assignee=to_user,
    )


def _require_open(task):
    if task.status == TeamTask.STATUS_CLOSED:
        raise TaskWorkflowError('This task is already closed.')


def _require_actor(user, task):
    _require_open(task)
    if not can_act_on_task(user, task):
        raise TaskWorkflowError('You cannot change this task.')


def _set_reminder(task, base_date):
    if base_date < timezone.localdate():
        base_date = timezone.localdate()
    task.next_reminder_on = reminder_date(base_date, task.remind_after_days)


def create_task(
    *,
    user,
    title,
    description,
    assignee,
    priority=TeamTask.PRIORITY_MEDIUM,
    scheduled_on=None,
    due_on=None,
    remind_after_days=3,
    related_order=None,
    remarks='',
):
    if due_on and scheduled_on and due_on < scheduled_on:
        raise TaskWorkflowError('Due date cannot be before the scheduled date.')
    today = timezone.localdate()
    status = TeamTask.STATUS_OPEN
    if scheduled_on and scheduled_on > today:
        status = TeamTask.STATUS_SCHEDULED
    for _attempt in range(3):
        try:
            with transaction.atomic():
                task = TeamTask(
                    title=title.strip(),
                    description=description.strip(),
                    priority=priority,
                    status=status,
                    assignee=assignee,
                    created_by=user,
                    scheduled_on=scheduled_on,
                    due_on=due_on,
                    remind_after_days=remind_after_days or 3,
                    latest_remarks=remarks or '',
                    related_order=related_order,
                )
                _set_reminder(task, scheduled_on or today)
                task.save()
                _log(
                    task,
                    TaskHistory.ACTION_CREATED,
                    user,
                    remarks=remarks,
                    to_status=task.status,
                    to_user=assignee,
                )
                if scheduled_on:
                    _log(
                        task,
                        TaskHistory.ACTION_SCHEDULED,
                        user,
                        remarks=_schedule_remark(task),
                        from_status=TeamTask.STATUS_OPEN,
                        to_status=task.status,
                    )
                return task
        except IntegrityError:
            continue
    raise TaskWorkflowError('Could not allocate a task number. Please try again.')


def _schedule_remark(task):
    parts = []
    if task.scheduled_on:
        parts.append(f'Start {task.scheduled_on:%d-%m-%Y}')
    if task.due_on:
        parts.append(f'Due {task.due_on:%d-%m-%Y}')
    parts.append(f'Remind after {task.remind_after_days} day(s)')
    return '. '.join(parts)


def schedule_task(task, user, *, scheduled_on, due_on, remind_after_days, remarks=''):
    _require_actor(user, task)
    if not scheduled_on and not due_on:
        raise TaskWorkflowError('Enter a scheduled date or a due date.')
    if due_on and scheduled_on and due_on < scheduled_on:
        raise TaskWorkflowError('Due date cannot be before the scheduled date.')
    old_status = task.status
    task.scheduled_on = scheduled_on
    task.due_on = due_on
    if remind_after_days:
        task.remind_after_days = remind_after_days
    today = timezone.localdate()
    if task.status != TeamTask.STATUS_ON_HOLD:
        if scheduled_on and scheduled_on > today:
            task.status = TeamTask.STATUS_SCHEDULED
        elif task.status == TeamTask.STATUS_SCHEDULED:
            task.status = TeamTask.STATUS_OPEN
    _set_reminder(task, scheduled_on or today)
    if remarks:
        task.latest_remarks = remarks
    task.save()
    _log(
        task,
        TaskHistory.ACTION_SCHEDULED,
        user,
        remarks=remarks or _schedule_remark(task),
        from_status=old_status,
        to_status=task.status,
    )
    return task


def start_task(task, user, remarks=''):
    _require_actor(user, task)
    if task.status not in (TeamTask.STATUS_OPEN, TeamTask.STATUS_SCHEDULED):
        raise TaskWorkflowError('Only an open or scheduled task can be started.')
    old = task.status
    task.status = TeamTask.STATUS_IN_PROGRESS
    if remarks:
        task.latest_remarks = remarks
    task.save()
    _log(
        task,
        TaskHistory.ACTION_STARTED,
        user,
        remarks=remarks,
        from_status=old,
        to_status=task.status,
    )
    return task


def remap_task(task, user, *, new_assignee, remarks):
    _require_actor(user, task)
    remarks = (remarks or '').strip()
    if not remarks:
        raise TaskWorkflowError('Enter remarks explaining why this task is being forwarded.')
    if new_assignee.pk == task.assignee_id:
        raise TaskWorkflowError('Choose a different person to forward this task to.')
    old_user = task.assignee
    old_status = task.status
    task.assignee = new_assignee
    if task.status == TeamTask.STATUS_ON_HOLD:
        task.status = TeamTask.STATUS_IN_PROGRESS
        task.held_at = None
    task.latest_remarks = remarks
    _set_reminder(task, timezone.localdate())
    task.save()
    _log(
        task,
        TaskHistory.ACTION_REMAPPED,
        user,
        remarks=remarks,
        from_status=old_status,
        to_status=task.status,
        from_user=old_user,
        to_user=new_assignee,
    )
    return task


def hold_task(task, user, *, remarks, remind_after_days=None):
    _require_actor(user, task)
    remarks = (remarks or '').strip()
    if not remarks:
        raise TaskWorkflowError('Enter remarks explaining why this task is on hold.')
    if task.status == TeamTask.STATUS_ON_HOLD:
        raise TaskWorkflowError('This task is already on hold.')
    old = task.status
    task.status = TeamTask.STATUS_ON_HOLD
    task.hold_remarks = remarks
    task.latest_remarks = remarks
    task.held_at = timezone.now()
    if remind_after_days:
        task.remind_after_days = remind_after_days
    _set_reminder(task, timezone.localdate())
    task.save()
    _log(
        task,
        TaskHistory.ACTION_HELD,
        user,
        remarks=remarks,
        from_status=old,
        to_status=task.status,
    )
    return task


def resume_task(task, user, remarks=''):
    _require_actor(user, task)
    if task.status != TeamTask.STATUS_ON_HOLD:
        raise TaskWorkflowError('Only a task on hold can be resumed.')
    task.status = TeamTask.STATUS_IN_PROGRESS
    task.held_at = None
    if remarks:
        task.latest_remarks = remarks.strip()
    _set_reminder(task, timezone.localdate())
    task.save()
    _log(
        task,
        TaskHistory.ACTION_RESUMED,
        user,
        remarks=remarks,
        from_status=TeamTask.STATUS_ON_HOLD,
        to_status=task.status,
    )
    return task


def add_note(task, user, remarks):
    _require_actor(user, task)
    remarks = (remarks or '').strip()
    if not remarks:
        raise TaskWorkflowError('Enter an update before saving.')
    task.latest_remarks = remarks
    task.save(update_fields=['latest_remarks', 'updated_at'])
    _log(
        task,
        TaskHistory.ACTION_NOTE,
        user,
        remarks=remarks,
        from_status=task.status,
        to_status=task.status,
    )
    return task


def close_task(task, user, *, remarks):
    _require_actor(user, task)
    remarks = (remarks or '').strip()
    if not remarks:
        raise TaskWorkflowError('Enter closing remarks.')
    old = task.status
    task.status = TeamTask.STATUS_CLOSED
    task.close_remarks = remarks
    task.latest_remarks = remarks
    task.closed_at = timezone.now()
    task.next_reminder_on = None
    task.save()
    _log(
        task,
        TaskHistory.ACTION_CLOSED,
        user,
        remarks=remarks,
        from_status=old,
        to_status=task.status,
        to_user=task.assignee,
    )
    return task


def record_due_reminders(today=None):
    """Write one reminder history row per open task that has reached its reminder date."""
    today = today or timezone.localdate()
    due_ids = list(
        TeamTask.objects.filter(next_reminder_on__lte=today)
        .exclude(status=TeamTask.STATUS_CLOSED)
        .values_list('pk', flat=True)
    )
    recorded = 0
    for pk in due_ids:
        with transaction.atomic():
            try:
                task = TeamTask.objects.get(pk=pk)
            except TeamTask.DoesNotExist:
                continue
            if task.status == TeamTask.STATUS_CLOSED or not task.next_reminder_on:
                continue
            if task.next_reminder_on > today:
                continue
            already = task.history.filter(
                action=TaskHistory.ACTION_REMINDED,
                created_at__date=today,
            ).exists()
            if already:
                continue
            note = (
                f'Reminder: this task is still {task.get_status_display().lower()} '
                f'after {task.remind_after_days} day(s).'
            )
            _log(
                task,
                TaskHistory.ACTION_REMINDED,
                None,
                remarks=note,
                from_status=task.status,
                to_status=task.status,
                to_user=task.assignee,
            )
            task.next_reminder_on = today + timedelta(days=task.remind_after_days or 1)
            task.save(update_fields=['next_reminder_on', 'updated_at'])
            recorded += 1
    return recorded


def long_pending_queryset(qs):
    """Tasks still workable after their own reminder window."""
    today = timezone.localdate()
    pending_ids = []
    rows = (
        qs.filter(status__in=TeamTask.WORKABLE_STATUSES)
        .values('pk', 'created_at', 'remind_after_days')
    )
    for row in rows:
        opened = timezone.localtime(row['created_at']).date()
        if (today - opened).days >= (row['remind_after_days'] or 1):
            pending_ids.append(row['pk'])
    return qs.filter(pk__in=pending_ids)


def dashboard_stats(qs):
    today = timezone.localdate()
    active = qs.exclude(status=TeamTask.STATUS_CLOSED)
    return {
        'open': qs.filter(status=TeamTask.STATUS_OPEN).count(),
        'scheduled': qs.filter(status=TeamTask.STATUS_SCHEDULED).count(),
        'in_progress': qs.filter(status=TeamTask.STATUS_IN_PROGRESS).count(),
        'on_hold': qs.filter(status=TeamTask.STATUS_ON_HOLD).count(),
        'closed': qs.filter(status=TeamTask.STATUS_CLOSED).count(),
        'overdue': active.filter(due_on__lt=today).count(),
        'long_pending': long_pending_queryset(qs).count(),
        'reminded_today': qs.filter(
            history__action=TaskHistory.ACTION_REMINDED,
            history__created_at__date=today,
        ).distinct().count(),
        'mine': qs.count(),
    }


def attention_tasks(qs):
    today = timezone.localdate()
    reminded_ids = qs.filter(
        history__action=TaskHistory.ACTION_REMINDED,
        history__created_at__date=today,
    ).values('pk')
    long_ids = long_pending_queryset(qs).values('pk')
    return qs.filter(
        Q(pk__in=reminded_ids)
        | Q(pk__in=long_ids)
        | Q(status=TeamTask.STATUS_ON_HOLD)
        | (Q(due_on__lt=today) & ~Q(status=TeamTask.STATUS_CLOSED))
    ).distinct().order_by('due_on', '-updated_at')[:20]


def apply_list_filters(qs, params, user):
    status = (params.get('status') or '').strip()
    priority = (params.get('priority') or '').strip()
    bucket = (params.get('bucket') or '').strip()
    query = (params.get('q') or '').strip()
    mine = (params.get('mine') or '').strip()
    today = timezone.localdate()
    if status in dict(TeamTask.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if priority in dict(TeamTask.PRIORITY_CHOICES):
        qs = qs.filter(priority=priority)
    if mine == '1':
        qs = qs.filter(Q(assignee=user) | Q(created_by=user))
    if query:
        qs = qs.filter(
            Q(task_number__icontains=query)
            | Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(latest_remarks__icontains=query)
        )
    if bucket == 'overdue':
        qs = qs.filter(due_on__lt=today).exclude(status=TeamTask.STATUS_CLOSED)
    elif bucket == 'hold':
        qs = qs.filter(status=TeamTask.STATUS_ON_HOLD)
    elif bucket == 'long':
        qs = long_pending_queryset(qs)
    elif bucket == 'reminded':
        qs = qs.filter(
            history__action=TaskHistory.ACTION_REMINDED,
            history__created_at__date=today,
        ).distinct()
    return qs


def history_for_user(user):
    visible = tasks_for_user(user)
    return (
        TaskHistory.objects.filter(task__in=visible)
        .select_related('task', 'actor', 'from_assignee', 'to_assignee')
        .order_by('-created_at', '-id')
    )


def open_task_count_for_user(user):
    return TeamTask.objects.filter(assignee=user).exclude(
        status=TeamTask.STATUS_CLOSED,
    ).count()
