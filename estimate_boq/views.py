from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import module_required
from accounts.permissions import MODULE_ESTIMATE_BOQ, MODULE_ORDERS_CREATE, can_access
from enquiries.models import Enquiry
from .forms import EstimateBOQForm, EstimateBOQLineFormSet
from .models import EstimateBOQ


@module_required(MODULE_ESTIMATE_BOQ)
def estimate_boq_list(request):
    qs = EstimateBOQ.objects.select_related('enquiry', 'enquiry__client').order_by('-created_at')
    return render(request, 'estimate_boq/estimate_boq_list.html', {'estimate_boqs': qs})


@module_required(MODULE_ESTIMATE_BOQ)
def create_estimate_boq(request):
    if request.GET.get('enquiry') or request.POST.get('enquiry'):
        messages.info(
            request,
            'Estimate BOQ from enquiries is retired. Create an order first, then prepare BOQ from the order workflow.',
        )
        return redirect('order_list')

    enquiry = None

    if request.method == 'POST':
        form = EstimateBOQForm(request.POST)
        formset = EstimateBOQLineFormSet(request.POST, prefix='lines')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                eboq = form.save(commit=False)
                if enquiry and not eboq.enquiry_id:
                    eboq.enquiry = enquiry
                eboq.created_by = request.user
                eboq.save()
                formset.instance = eboq
                formset.save()
                eboq.recalculate()
                if eboq.enquiry_id and eboq.enquiry.status == Enquiry.STATUS_SURVEY_COMPLETED:
                    eboq.enquiry.status = Enquiry.STATUS_QUOTATION_PREPARATION
                    eboq.enquiry.save(update_fields=['status', 'updated_at'])
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_ESTIMATE_BOQ
            log_activity(
                request.user, ACT_ESTIMATE_BOQ,
                related_document=eboq.estimate_boq_number,
                related_model='EstimateBOQ',
                related_object_id=eboq.pk,
            )
            from case_intelligence.integrations import estimate_boq_created
            estimate_boq_created(request.user, eboq)
            messages.success(request, f'Estimate BOQ {eboq.estimate_boq_number} created.')
            return redirect('estimate_boq_detail', pk=eboq.pk)
        messages.error(request, 'Could not save Estimate BOQ. Please correct the line item errors below.')
    else:
        initial = {'enquiry': enquiry} if enquiry else {}
        form = EstimateBOQForm(initial=initial)
        if enquiry:
            form.fields['enquiry'].disabled = True
        formset = EstimateBOQLineFormSet(prefix='lines')

    return render(request, 'estimate_boq/estimate_boq_form.html', {
        'form': form,
        'formset': formset,
        'enquiry': enquiry,
    })


@module_required(MODULE_ESTIMATE_BOQ)
def estimate_boq_detail(request, pk):
    eboq = get_object_or_404(
        EstimateBOQ.objects.select_related('enquiry', 'enquiry__client'),
        pk=pk,
    )
    return render(request, 'estimate_boq/estimate_boq_detail.html', {
        'estimate_boq': eboq,
        'can_edit': eboq.status == EstimateBOQ.STATUS_DRAFT and can_access(request.user, MODULE_ORDERS_CREATE),
    })


@module_required(MODULE_ESTIMATE_BOQ)
def edit_estimate_boq(request, pk):
    eboq = get_object_or_404(EstimateBOQ, pk=pk)
    if eboq.status != EstimateBOQ.STATUS_DRAFT:
        messages.error(request, 'Only draft estimate BOQs can be edited.')
        return redirect('estimate_boq_detail', pk=pk)

    if request.method == 'POST':
        form = EstimateBOQForm(request.POST, instance=eboq)
        formset = EstimateBOQLineFormSet(request.POST, instance=eboq, prefix='lines')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                eboq.recalculate()
            messages.success(request, 'Estimate BOQ updated.')
            return redirect('estimate_boq_detail', pk=pk)
        messages.error(request, 'Could not update Estimate BOQ. Please correct the line item errors below.')
    else:
        form = EstimateBOQForm(instance=eboq)
        formset = EstimateBOQLineFormSet(instance=eboq, prefix='lines')

    return render(request, 'estimate_boq/estimate_boq_form.html', {
        'form': form,
        'formset': formset,
        'estimate_boq': eboq,
        'enquiry': eboq.enquiry,
    })
