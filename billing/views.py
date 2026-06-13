from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import access_denied_response
from billing.approval import (
    ACTION_CREATED,
    ACTION_EDITED,
    INVOICE_LOCKED_MESSAGE,
    LOCKED_STATUSES,
    STATUS_DRAFT,
    approve_invoice,
    log_approval_action,
    reject_invoice,
    start_review,
    submit_invoice,
    unlock_invoice,
)
from billing.gst import (
    gst_type_label,
    resolve_client_gst_type,
    resolve_client_state_display,
)
from billing.permissions import (
    can_approve_invoice,
    can_create_invoice,
    can_download_invoice_pdf,
    can_edit_invoice,
    can_submit_invoice,
    can_override_invoice_gst,
    can_unlock_invoice,
    can_view_invoices,
)
from boq.models import BOQ
from company_settings.permissions import can_edit_document_signatory

from .forms import (
    InvoiceApproveForm,
    InvoiceForm,
    InvoiceLineItemFormSet,
    InvoiceRejectForm,
)
from .models import Invoice, InvoiceGstAuditLog
from .pdf import build_invoice_pdf


def billing_view_required(view_func):
    @login_required(login_url='login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not can_view_invoices(request.user):
            return access_denied_response(request, reason='unauthorized', module_key='billing')
        return view_func(request, *args, **kwargs)
    return wrapper


def _invoice_queryset():
    return Invoice.objects.select_related(
        'order', 'order__client', 'boq',
        'created_by', 'submitted_by', 'approved_by', 'rejected_by',
    )


def _save_invoice_from_form(request, form, formset, invoice=None):
    """Shared create/edit save logic — returns invoice or None."""
    with transaction.atomic():
        is_new = invoice is None
        inv = form.save(commit=False)
        previous_status = '' if is_new else inv.approval_status
        if is_new:
            mode = form.cleaned_data.get('invoice_number_mode', 'AUTO')
            if mode == 'AUTO':
                from document_generator.constants import DOC_INVOICE
                from document_generator.services import generate_document_number
                inv.invoice_number = generate_document_number(DOC_INVOICE, user=request.user)
                inv.number_mode = Invoice.NUMBER_MODE_AUTO
            else:
                inv.invoice_number = form.cleaned_data['invoice_number']
                inv.number_mode = Invoice.NUMBER_MODE_MANUAL
            inv.created_by = request.user
            inv.approval_status = STATUS_DRAFT

        client = form.cleaned_data['order'].client
        client_gst_type = resolve_client_gst_type(client)
        selected_gst_type = form.cleaned_data['gst_type']
        can_override_gst = can_override_invoice_gst(request.user)
        if selected_gst_type != client_gst_type and not can_override_gst:
            selected_gst_type = client_gst_type
        inv.gst_type = selected_gst_type

        if is_new:
            inv.amount = Decimal('0')
            inv.gst = Decimal('0')
            inv.cgst_amount = Decimal('0')
            inv.sgst_amount = Decimal('0')
            inv.igst_amount = Decimal('0')
            inv.total = Decimal('0')

        if not is_new and inv.approval_status == 'REJECTED':
            inv.approval_status = STATUS_DRAFT

        inv.save()
        formset.instance = inv
        formset.save()
        inv.recalculate_totals(gst_type=selected_gst_type)
        inv.save()

        if is_new:
            log_approval_action(
                inv, ACTION_CREATED, request.user,
                new_status=STATUS_DRAFT,
            )
        else:
            log_approval_action(
                inv, ACTION_EDITED, request.user,
                previous_status=previous_status,
                new_status=inv.approval_status,
            )

        if selected_gst_type != client_gst_type and can_override_gst:
            InvoiceGstAuditLog.objects.create(
                invoice=inv,
                changed_by=request.user,
                client_gst_type=client_gst_type,
                previous_gst_type=client_gst_type,
                new_gst_type=selected_gst_type,
                note='GST type manually overridden on invoice save.',
            )
    return inv


@billing_view_required
def invoice_list(request):
    invoices = _invoice_queryset().order_by('-invoice_date')
    payment_status = request.GET.get('status')
    approval_status = request.GET.get('approval')
    if payment_status:
        invoices = invoices.filter(payment_status=payment_status)
    if approval_status:
        invoices = invoices.filter(approval_status=approval_status)
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'current_status': payment_status,
        'current_approval': approval_status,
        'can_create_invoice': can_create_invoice(request.user),
        'can_approve_invoice': can_approve_invoice(request.user),
    })


@billing_view_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        _invoice_queryset().prefetch_related('line_items', 'approval_audit_logs'),
        pk=pk,
    )
    if can_approve_invoice(request.user, invoice) and invoice.approval_status == 'SUBMITTED':
        start_review(invoice, request.user)

    is_locked = invoice.approval_status in LOCKED_STATUSES
    from case_intelligence.constants import MOD_INVOICE
    from case_intelligence.services import panel_context
    case_ctx = panel_context(
        invoice,
        module=MOD_INVOICE,
        document_number=invoice.invoice_number,
        status=invoice.get_approval_status_display(),
        stage=invoice.payment_status,
        pending_action='Approval' if invoice.approval_status == 'SUBMITTED' else (
            'Payment' if invoice.payment_status == 'PENDING' else '—'
        ),
        next_action='Accounts action',
    )
    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'audit_logs': invoice.approval_audit_logs.select_related('performed_by'),
        'can_edit': can_edit_invoice(request.user, invoice),
        'can_submit': can_submit_invoice(request.user, invoice),
        'can_approve': can_approve_invoice(request.user, invoice),
        'can_unlock': can_unlock_invoice(request.user, invoice),
        'is_locked': is_locked,
        'locked_message': INVOICE_LOCKED_MESSAGE,
        'can_pdf': can_download_invoice_pdf(request.user, invoice)[0],
        'approve_form': InvoiceApproveForm(),
        'reject_form': InvoiceRejectForm(),
        **case_ctx,
    })


@billing_view_required
def create_invoice(request):
    if not can_create_invoice(request.user):
        return access_denied_response(request, reason='unauthorized', module_key='billing')

    can_override_gst = can_override_invoice_gst(request.user)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES, user=request.user, can_override_gst=can_override_gst)
        formset = InvoiceLineItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            invoice = _save_invoice_from_form(request, form, formset)
            from productivity.activity_logger import log_activity
            from productivity.constants import ACT_INVOICE_CREATED
            log_activity(
                request.user, ACT_INVOICE_CREATED,
                related_document=invoice.invoice_number,
                related_model='Invoice',
                related_object_id=invoice.pk,
            )
            from case_intelligence.integrations import invoice_generated
            invoice_generated(request.user, invoice)
            messages.success(
                request,
                f'Draft invoice {invoice.invoice_number} created. Submit for approval when ready.',
            )
            return redirect('invoice_detail', pk=invoice.pk)
        messages.error(request, 'Please correct the errors below before saving.')
    else:
        form = InvoiceForm(user=request.user, can_override_gst=can_override_gst)
        boq_id = request.GET.get('boq')
        order_id = request.GET.get('order')
        initial_lines = []
        if boq_id:
            boq = BOQ.objects.filter(pk=boq_id, status='VERIFIED').first()
            if boq:
                form.initial.update({'order': boq.order_id, 'boq': boq.pk})
                initial_lines = _lines_from_boq(boq)
        elif order_id:
            boq = BOQ.objects.filter(order_id=order_id, status='VERIFIED').first()
            form.initial['order'] = order_id
            if boq:
                form.initial['boq'] = boq.pk
                initial_lines = _lines_from_boq(boq)
        formset = InvoiceLineItemFormSet(initial=initial_lines, prefix='items')

    preview_number = ''
    try:
        from document_generator.constants import DOC_INVOICE
        from document_generator.services import preview_next_number
        preview_number = preview_next_number(DOC_INVOICE)
    except Exception:
        pass

    return render(request, 'billing/invoice_form.html', {
        'form': form,
        'formset': formset,
        'auto_load_boq': request.GET.get('boq'),
        'preview_invoice_number': preview_number,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
        'can_override_gst': can_override_gst,
        'gst_rate_percent': 18,
        'is_edit': False,
    })


@billing_view_required
def edit_invoice(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.approval_status in LOCKED_STATUSES:
        messages.error(request, INVOICE_LOCKED_MESSAGE)
        return redirect('invoice_detail', pk=pk)
    if not can_edit_invoice(request.user, invoice):
        messages.error(request, 'This invoice cannot be edited in its current status.')
        return redirect('invoice_detail', pk=pk)

    can_override_gst = can_override_invoice_gst(request.user)
    if request.method == 'POST':
        form = InvoiceForm(
            request.POST, request.FILES,
            instance=invoice, user=request.user, can_override_gst=can_override_gst,
        )
        formset = InvoiceLineItemFormSet(request.POST, instance=invoice, prefix='items')
        if form.is_valid() and formset.is_valid():
            _save_invoice_from_form(request, form, formset, invoice=invoice)
            messages.success(request, f'Invoice {invoice.invoice_number} updated.')
            return redirect('invoice_detail', pk=invoice.pk)
        messages.error(request, 'Please correct the errors below before saving.')
    else:
        form = InvoiceForm(instance=invoice, user=request.user, can_override_gst=can_override_gst)
        form.fields['invoice_number_mode'].initial = invoice.number_mode
        form.fields['invoice_number'].initial = invoice.invoice_number
        formset = InvoiceLineItemFormSet(instance=invoice, prefix='items')

    return render(request, 'billing/invoice_form.html', {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'can_edit_signatory': can_edit_document_signatory(request.user),
        'signatory_instance': form.instance,
        'can_override_gst': can_override_gst,
        'gst_rate_percent': 18,
        'is_edit': True,
    })


@billing_view_required
@require_POST
def unlock_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not can_unlock_invoice(request.user, invoice):
        messages.error(request, INVOICE_LOCKED_MESSAGE)
        return redirect('invoice_detail', pk=pk)
    unlock_invoice(invoice, request.user)
    messages.warning(
        request,
        f'Invoice {invoice.invoice_number} unlocked for editing. Status reset to Draft.',
    )
    return redirect('edit_invoice', pk=invoice.pk)


@billing_view_required
@require_POST
def submit_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not can_submit_invoice(request.user, invoice):
        messages.error(request, 'You cannot submit this invoice for approval.')
        return redirect('invoice_detail', pk=pk)
    submit_invoice(invoice, request.user)
    from productivity.activity_logger import log_activity
    from productivity.constants import ACT_INVOICE_VERIFIED
    log_activity(
        request.user, ACT_INVOICE_VERIFIED,
        related_document=invoice.invoice_number,
        related_model='Invoice',
        related_object_id=invoice.pk,
    )
    from case_intelligence.logger import log_case_event
    from case_intelligence.constants import MOD_INVOICE
    log_case_event(
        request.user,
        module=MOD_INVOICE,
        document_type='Invoice',
        document_number=invoice.invoice_number,
        description='Invoice Submitted For Approval',
        previous_status='DRAFT',
        new_status=invoice.approval_status,
        client=invoice.order.client,
        content_object=invoice,
    )
    messages.success(request, f'Invoice {invoice.invoice_number} submitted for approval.')
    return redirect('invoice_detail', pk=pk)


@billing_view_required
@require_POST
def approve_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not can_approve_invoice(request.user, invoice):
        messages.error(request, 'You are not authorized to approve this invoice.')
        return redirect('invoice_detail', pk=pk)
    form = InvoiceApproveForm(request.POST)
    if form.is_valid():
        approve_invoice(invoice, request.user, form.cleaned_data.get('approval_remarks', ''))
        from productivity.activity_logger import log_activity
        from productivity.constants import ACT_INVOICE_APPROVED
        log_activity(
            request.user, ACT_INVOICE_APPROVED,
            related_document=invoice.invoice_number,
            related_model='Invoice',
            related_object_id=invoice.pk,
        )
        from case_intelligence.integrations import invoice_approved
        invoice_approved(request.user, invoice)
        messages.success(request, f'Invoice {invoice.invoice_number} approved. PDF is now available.')
    else:
        messages.error(request, 'Could not approve invoice. Please try again.')
    return redirect('invoice_detail', pk=pk)


@billing_view_required
@require_POST
def reject_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not can_approve_invoice(request.user, invoice):
        messages.error(request, 'You are not authorized to reject this invoice.')
        return redirect('invoice_detail', pk=pk)
    form = InvoiceRejectForm(request.POST)
    if form.is_valid():
        reject_invoice(
            invoice,
            request.user,
            form.cleaned_data['rejection_reason'],
            form.cleaned_data.get('approval_remarks', ''),
        )
        messages.warning(request, f'Invoice {invoice.invoice_number} rejected.')
    else:
        messages.error(request, 'Rejection reason is required.')
    return redirect('invoice_detail', pk=pk)


def _lines_from_boq(boq):
    return [
        {
            'sl_no': line.sl_no,
            'description': line.description,
            'hsn_sac': line.hsn_sac,
            'unit': line.unit,
            'qty': line.qty,
            'rate': Decimal('0'),
            'remarks': '',
            'from_boq': True,
        }
        for line in boq.lines.all()
    ]


@require_GET
@billing_view_required
def boq_lines_json(request, boq_id):
    boq = get_object_or_404(BOQ, pk=boq_id, status='VERIFIED')
    lines = [
        {
            'sl_no': line.sl_no,
            'description': line.description,
            'hsn_sac': line.hsn_sac,
            'unit': line.unit,
            'qty': str(line.qty),
            'rate': '0',
            'remarks': '',
        }
        for line in boq.lines.all()
    ]
    return JsonResponse({'lines': lines, 'order_id': boq.order_id})


@require_GET
@billing_view_required
def order_gst_json(request, order_id):
    from orders.models import Order
    order = get_object_or_404(Order.objects.select_related('client'), pk=order_id)
    client = order.client
    gst_type = resolve_client_gst_type(client)
    state_name, state_code = resolve_client_state_display(client)
    return JsonResponse({
        'gst_type': gst_type,
        'gst_type_label': gst_type_label(gst_type),
        'client_name': client.name,
        'client_state': state_name,
        'client_state_code': state_code,
        'client_gst_number': client.gst_number or '',
    })


@billing_view_required
def mark_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not invoice.is_pdf_available:
        messages.error(request, 'Only approved invoices can be marked as paid.')
        return redirect('invoice_detail', pk=pk)
    if request.method == 'POST':
        invoice.payment_status = 'RECEIVED'
        invoice.save()
        from case_intelligence.integrations import payment_received
        payment_received(request.user, invoice)
        messages.success(request, f'Payment recorded for {invoice.invoice_number}.')
        return redirect('invoice_list')
    return render(request, 'billing/mark_paid.html', {'invoice': invoice})


@billing_view_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('order', 'order__client', 'boq').prefetch_related('line_items'),
        pk=pk,
    )
    allowed, msg = can_download_invoice_pdf(request.user, invoice)
    if not allowed:
        messages.error(request, msg)
        return redirect('invoice_detail', pk=pk)

    pdf_buffer = build_invoice_pdf(invoice)
    filename = f"Invoice_{invoice.invoice_number}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
