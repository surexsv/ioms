from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import module_required
from orders.models import Order

from .forms import (
    LabourFormSet,
    MaterialFormSet,
    MediaFormSet,
    ProjectDailyLogForm,
    ServiceFormSet,
    SpecialProjectForm,
    expense_formset_for_user,
)
from .models import DailyExpenseLine, ProjectDailyLog, SpecialProject
from .permissions import (
    MODULE_SPECIAL_PROJECTS,
    can_manage_special_projects,
    can_submit_daily_log,
)


def _projects_for_user(user):
    qs = SpecialProject.objects.select_related(
        'order', 'order__client', 'project_manager',
    )
    if user.is_superuser or can_manage_special_projects(user):
        return qs
    return qs.filter(
        Q(project_manager=user) | Q(daily_logs__assigned_employees=user)
    ).distinct()


def _require_project_access(request, project):
    if request.user.is_superuser:
        return True
    if _projects_for_user(request.user).filter(pk=project.pk).exists():
        return True
    return False


@module_required(MODULE_SPECIAL_PROJECTS)
def project_list(request):
    projects = _projects_for_user(request.user).order_by('-updated_at')
    status = request.GET.get('status', '').strip()
    if status:
        projects = projects.filter(status=status)
    return render(request, 'special_projects/project_list.html', {
        'projects': projects,
        'status_filter': status,
        'can_manage': can_manage_special_projects(request.user),
        'status_choices': SpecialProject.STATUS_CHOICES,
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def open_from_order(request, order_id):
    """Open (or reopen) an Order as a Special Project."""
    if not can_manage_special_projects(request.user):
        messages.error(request, 'You do not have permission to open Special Projects.')
        return redirect('order_detail', pk=order_id)

    order = get_object_or_404(Order.objects.select_related('client'), pk=order_id)
    existing = getattr(order, 'special_project', None)
    if existing:
        messages.info(request, f'This order is already linked to {existing.project_number}.')
        return redirect('special_project_detail', pk=existing.pk)

    if request.method == 'POST':
        form = SpecialProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.order = order
            project.created_by = request.user
            if not project.project_manager_id and order.assigned_project_manager_id:
                project.project_manager = order.assigned_project_manager
            if not project.planned_start_date:
                project.planned_start_date = order.order_date or timezone.localdate()
            if not project.actual_start_date and project.status == SpecialProject.STATUS_IN_PROGRESS:
                project.actual_start_date = timezone.localdate()
            if project.status == SpecialProject.STATUS_PLANNING:
                project.status = SpecialProject.STATUS_IN_PROGRESS
                project.actual_start_date = project.actual_start_date or timezone.localdate()
            project.save()
            messages.success(
                request,
                f'Special Project {project.project_number} opened for order {order.order_no}.',
            )
            return redirect('special_project_detail', pk=project.pk)
    else:
        form = SpecialProjectForm(initial={
            'name': order.display_site_name or order.client.name,
            'project_manager': order.assigned_project_manager_id,
            'planned_start_date': order.order_date,
            'planned_end_date': order.expected_completion_date or order.target_date,
            'status': SpecialProject.STATUS_IN_PROGRESS,
        })

    return render(request, 'special_projects/open_from_order.html', {
        'order': order,
        'form': form,
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def project_detail(request, pk):
    project = get_object_or_404(
        SpecialProject.objects.select_related('order', 'order__client', 'project_manager'),
        pk=pk,
    )
    if not _projects_for_user(request.user).filter(pk=project.pk).exists() and not request.user.is_superuser:
        if not can_manage_special_projects(request.user):
            messages.error(request, 'You are not assigned to this Special Project.')
            return redirect('special_project_list')

    logs = project.daily_logs.prefetch_related(
        'labour_lines', 'material_lines', 'service_lines', 'expenses', 'media_files',
    )[:30]
    total_expense = project.total_expenses()
    approved_expense = DailyExpenseLine.objects.filter(
        daily_log__project=project,
        approval_status=DailyExpenseLine.APPROVAL_APPROVED,
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    wcr = getattr(project.order, 'workcompletionreport', None)
    if wcr is None:
        from wcr.models import WorkCompletionReport
        wcr = WorkCompletionReport.objects.filter(order=project.order).first()

    return render(request, 'special_projects/project_detail.html', {
        'project': project,
        'logs': logs,
        'total_expense': total_expense,
        'approved_expense': approved_expense,
        'budget_variance': project.budget - total_expense,
        'can_manage': can_manage_special_projects(request.user),
        'can_log': can_submit_daily_log(request.user),
        'wcr': wcr,
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def project_edit(request, pk):
    project = get_object_or_404(SpecialProject, pk=pk)
    if not can_manage_special_projects(request.user):
        messages.error(request, 'Only managers can edit Special Project header.')
        return redirect('special_project_detail', pk=pk)

    if request.method == 'POST':
        form = SpecialProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Special Project updated.')
            return redirect('special_project_detail', pk=pk)
    else:
        form = SpecialProjectForm(instance=project)

    return render(request, 'special_projects/project_form.html', {
        'form': form,
        'project': project,
        'title': f'Edit {project.project_number}',
    })


def _save_daily_log(request, project, instance=None):
    form = ProjectDailyLogForm(request.POST, instance=instance)
    labour_fs = LabourFormSet(request.POST, instance=instance, prefix='labour')
    material_fs = MaterialFormSet(request.POST, instance=instance, prefix='material')
    service_fs = ServiceFormSet(request.POST, instance=instance, prefix='service')
    expense_fs = expense_formset_for_user(
        request.user, request.POST, request.FILES, instance=instance, prefix='expense',
    )
    media_fs = MediaFormSet(request.POST, request.FILES, instance=instance, prefix='media')

    formsets = [labour_fs, material_fs, service_fs, expense_fs, media_fs]
    if form.is_valid() and all(fs.is_valid() for fs in formsets):
        try:
            log = form.save(commit=False)
            log.project = project
            if instance is None:
                log.created_by = request.user
            log.save()
            form.save_m2m()
            for fs in formsets:
                fs.instance = log
                fs.save()
        except IntegrityError:
            form.add_error('log_date', 'A daily log already exists for this project and date.')
            return instance, form, formsets, False
        if log.daily_progress_pct > project.overall_progress_pct:
            project.overall_progress_pct = log.daily_progress_pct
            project.save(update_fields=['overall_progress_pct', 'updated_at'])
        return log, form, formsets, True
    return instance, form, formsets, False


@module_required(MODULE_SPECIAL_PROJECTS)
def daily_log_create(request, project_pk):
    project = get_object_or_404(SpecialProject, pk=project_pk)
    if not can_submit_daily_log(request.user):
        messages.error(request, 'You cannot submit daily logs.')
        return redirect('special_project_detail', pk=project.pk)
    if not _require_project_access(request, project):
        messages.error(request, 'Access denied for this project.')
        return redirect('special_project_list')

    if request.method == 'POST':
        log, form, formsets, ok = _save_daily_log(request, project)
        if ok:
            messages.success(request, f'Daily log for {log.log_date} saved.')
            return redirect('special_project_daily_log_detail', pk=log.pk)
        labour_fs, material_fs, service_fs, expense_fs, media_fs = formsets
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ProjectDailyLogForm(initial={
            'log_date': timezone.localdate(),
            'site_location': project.order.site_address[:255] if project.order.site_address else '',
        })
        labour_fs = LabourFormSet(prefix='labour')
        material_fs = MaterialFormSet(prefix='material')
        service_fs = ServiceFormSet(prefix='service')
        expense_fs = expense_formset_for_user(request.user, prefix='expense')
        media_fs = MediaFormSet(prefix='media')

    return render(request, 'special_projects/daily_log_form.html', {
        'project': project,
        'form': form,
        'labour_fs': labour_fs,
        'material_fs': material_fs,
        'service_fs': service_fs,
        'expense_fs': expense_fs,
        'media_fs': media_fs,
        'title': 'Add Daily Log',
        'is_edit': False,
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def daily_log_edit(request, pk):
    log = get_object_or_404(
        ProjectDailyLog.objects.select_related('project', 'project__order'),
        pk=pk,
    )
    if not can_submit_daily_log(request.user):
        messages.error(request, 'You cannot edit daily logs.')
        return redirect('special_project_detail', pk=log.project_id)
    if not _require_project_access(request, log.project):
        messages.error(request, 'Access denied for this project.')
        return redirect('special_project_list')

    if request.method == 'POST':
        saved, form, formsets, ok = _save_daily_log(request, log.project, instance=log)
        if ok:
            messages.success(request, 'Daily log updated.')
            return redirect('special_project_daily_log_detail', pk=saved.pk)
        labour_fs, material_fs, service_fs, expense_fs, media_fs = formsets
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ProjectDailyLogForm(instance=log)
        labour_fs = LabourFormSet(instance=log, prefix='labour')
        material_fs = MaterialFormSet(instance=log, prefix='material')
        service_fs = ServiceFormSet(instance=log, prefix='service')
        expense_fs = expense_formset_for_user(request.user, instance=log, prefix='expense')
        media_fs = MediaFormSet(instance=log, prefix='media')

    return render(request, 'special_projects/daily_log_form.html', {
        'project': log.project,
        'form': form,
        'labour_fs': labour_fs,
        'material_fs': material_fs,
        'service_fs': service_fs,
        'expense_fs': expense_fs,
        'media_fs': media_fs,
        'title': f'Edit Daily Log — {log.log_date}',
        'is_edit': True,
        'log': log,
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def daily_log_detail(request, pk):
    log = get_object_or_404(
        ProjectDailyLog.objects.select_related(
            'project', 'project__order', 'project__order__client', 'mentor', 'created_by',
        ).prefetch_related(
            'assigned_employees',
            'labour_lines__employee',
            'material_lines',
            'service_lines',
            'expenses',
            'media_files',
        ),
        pk=pk,
    )
    if not _require_project_access(request, log.project):
        messages.error(request, 'Access denied for this project.')
        return redirect('special_project_list')
    return render(request, 'special_projects/daily_log_detail.html', {
        'log': log,
        'project': log.project,
        'can_log': can_submit_daily_log(request.user) and _require_project_access(request, log.project),
        'day_expense': log.day_expense_total(),
    })


@module_required(MODULE_SPECIAL_PROJECTS)
def mark_project_completed(request, pk):
    project = get_object_or_404(SpecialProject, pk=pk)
    if not can_manage_special_projects(request.user):
        messages.error(request, 'Only managers can mark the project completed.')
        return redirect('special_project_detail', pk=pk)
    if request.method == 'POST':
        project.status = SpecialProject.STATUS_COMPLETED
        project.actual_end_date = project.actual_end_date or timezone.localdate()
        if project.overall_progress_pct < 100:
            project.overall_progress_pct = Decimal('100.00')
        project.save()
        # Align order for WCR path when still in field execution
        order = project.order
        if order.status in ('NEW', 'SCHEDULED', 'IN_PROGRESS'):
            order.status = 'COMPLETED'
            order.save(update_fields=['status'])
        messages.success(
            request,
            f'{project.project_number} marked completed. You can now submit WCR from the Orders/WCR module.',
        )
        return redirect('special_project_detail', pk=pk)
    return redirect('special_project_detail', pk=pk)
