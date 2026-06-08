from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.decorators import module_required, access_denied_response
from accounts.permissions import MODULE_WCR, MODULE_WCR_APPROVE, can_access
from .models import WorkCompletionReport
from company_settings.permissions import can_edit_document_signatory
from .forms import WCRForm


@module_required(MODULE_WCR)
def wcr_list(request):
    wcrs = WorkCompletionReport.objects.select_related(
        'order', 'order__client', 'submitted_by',
    ).order_by('-submitted_date')
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
    if request.method == 'POST':
        form = WCRForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            wcr = form.save(commit=False)
            wcr.submitted_by = request.user
            wcr.save()
            messages.success(request, f'WCR submitted for Order #{wcr.order.order_id}.')
            return redirect('wcr_list')
    else:
        form = WCRForm(user=request.user)
    return render(request, 'wcr/wcr_form.html', {
        'form': form,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
    })


@module_required(MODULE_WCR_APPROVE)
def approve_wcr(request, pk):
    wcr = get_object_or_404(WorkCompletionReport, pk=pk)
    if request.method == 'POST':
        wcr.approved = True
        wcr.save()
        messages.success(request, f'WCR for Order #{wcr.order.order_id} approved.')
        return redirect('wcr_list')
    return render(request, 'wcr/wcr_approve.html', {'wcr': wcr})
