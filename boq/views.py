from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from accounts.decorators import module_required
from accounts.permissions import MODULE_BOQ
from .models import BOQ
from company_settings.permissions import can_edit_document_signatory
from .forms import BOQForm, BOQLineItemFormSet


@module_required(MODULE_BOQ)
def boq_list(request):
    boqs = BOQ.objects.select_related('order', 'order__client', 'created_by').order_by('-created_at')
    status = request.GET.get('status')
    if status:
        boqs = boqs.filter(status=status)
    return render(request, 'boq/boq_list.html', {
        'boqs': boqs,
        'current_status': status,
    })


@module_required(MODULE_BOQ)
def create_boq(request):
    if request.method == 'POST':
        form = BOQForm(request.POST, request.FILES, user=request.user)
        formset = BOQLineItemFormSet(request.POST, prefix='lines')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                boq = form.save(commit=False)
                boq.created_by = request.user
                boq.save()
                formset.instance = boq
                formset.save()
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_EXECUTION_BOQ
            log_activity(
                request.user, ACT_EXECUTION_BOQ,
                related_document=boq.boq_number,
                related_model='BOQ',
                related_object_id=boq.pk,
            )
            from case_intelligence.integrations import boq_created
            boq_created(request.user, boq)
            messages.success(request, f'BOQ {boq.boq_number} created.')
            return redirect('boq_detail', pk=boq.pk)
        messages.error(request, 'Could not save BOQ. Please correct the line item errors below.')
    else:
        order_id = request.GET.get('order')
        form = BOQForm(initial={'order': order_id} if order_id else None, user=request.user)
        formset = BOQLineItemFormSet(prefix='lines')
    return render(request, 'boq/boq_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create BOQ',
        'is_editable': True,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
    })


@module_required(MODULE_BOQ)
def boq_detail(request, pk):
    boq = get_object_or_404(BOQ.objects.select_related('order', 'order__client'), pk=pk)
    return render(request, 'boq/boq_detail.html', {'boq': boq})


@module_required(MODULE_BOQ)
def edit_boq(request, pk):
    boq = get_object_or_404(BOQ, pk=pk)
    if not boq.is_editable:
        messages.error(request, 'Verified BOQ cannot be edited.')
        return redirect('boq_detail', pk=pk)

    if request.method == 'POST':
        form = BOQForm(request.POST, request.FILES, instance=boq, user=request.user)
        formset = BOQLineItemFormSet(request.POST, instance=boq, prefix='lines')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'BOQ updated.')
            return redirect('boq_detail', pk=pk)
        messages.error(request, 'Could not update BOQ. Please correct the line item errors below.')
    else:
        form = BOQForm(instance=boq, user=request.user)
        formset = BOQLineItemFormSet(instance=boq, prefix='lines')

    return render(request, 'boq/boq_form.html', {
        'form': form,
        'formset': formset,
        'title': f'Edit {boq.boq_number}',
        'boq': boq,
        'is_editable': True,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
    })


@module_required(MODULE_BOQ)
def verify_boq(request, pk):
    boq = get_object_or_404(
        BOQ.objects.select_related('order', 'order__client', 'created_by').prefetch_related('lines'),
        pk=pk,
    )
    if boq.status == 'VERIFIED':
        messages.info(request, 'BOQ is already verified.')
        return redirect('boq_detail', pk=pk)
    if not boq.lines.exists():
        messages.error(request, 'Add at least one line item before verifying.')
        return redirect('edit_boq', pk=pk)
    if request.method == 'POST':
        boq.status = 'VERIFIED'
        boq.verified_by = request.user
        boq.verified_at = timezone.now()
        boq.save()
        from productivity.activity_logger import log_activity
        from productivity.constants import ACT_EXECUTION_BOQ
        log_activity(
            request.user, ACT_EXECUTION_BOQ,
            related_document=boq.boq_number,
            related_model='BOQ',
            related_object_id=boq.pk,
            remarks='BOQ verified',
        )
        messages.success(request, f'BOQ {boq.boq_number} verified. It can now be used on invoices.')
        return redirect('boq_detail', pk=pk)
    return render(request, 'boq/boq_verify.html', {'boq': boq})
