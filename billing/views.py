from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.views.decorators.http import require_GET
from .models import Invoice, InvoiceLineItem
from .forms import InvoiceForm, InvoiceLineItemFormSet
from .pdf import build_invoice_pdf
from accounts.decorators import module_required
from accounts.permissions import MODULE_BILLING
from boq.models import BOQ
from company_settings.permissions import can_edit_document_signatory


@module_required(MODULE_BILLING)
def invoice_list(request):
    invoices = Invoice.objects.select_related('order', 'order__client', 'boq').order_by('-invoice_date')
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(payment_status=status)
    return render(request, 'billing/invoice_list.html', {
        'invoices': invoices,
        'current_status': status,
    })


@module_required(MODULE_BILLING)
def create_invoice(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST, request.FILES, user=request.user)
        formset = InvoiceLineItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                mode = form.cleaned_data.get('invoice_number_mode', 'AUTO')
                if mode == 'AUTO':
                    from document_generator.services import generate_document_number
                    from document_generator.constants import DOC_INVOICE
                    invoice.invoice_number = generate_document_number(DOC_INVOICE, user=request.user)
                    invoice.number_mode = Invoice.NUMBER_MODE_AUTO
                else:
                    invoice.invoice_number = form.cleaned_data['invoice_number']
                    invoice.number_mode = Invoice.NUMBER_MODE_MANUAL
                invoice.amount = Decimal('0')
                invoice.gst = Decimal('0')
                invoice.total = Decimal('0')
                invoice.save()
                formset.instance = invoice
                lines = formset.save()
                invoice.recalculate_totals()
                invoice.save()
            messages.success(request, f'Invoice {invoice.invoice_number} created.')
            return redirect('invoice_list')
    else:
        form = InvoiceForm(user=request.user)
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
        from document_generator.services import preview_next_number
        from document_generator.constants import DOC_INVOICE
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
    })


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
@module_required(MODULE_BILLING)
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


@module_required(MODULE_BILLING)
def mark_paid(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.payment_status = 'RECEIVED'
        invoice.save()
        messages.success(request, f'Payment recorded for {invoice.invoice_number}.')
        return redirect('invoice_list')
    return render(request, 'billing/mark_paid.html', {'invoice': invoice})


@module_required(MODULE_BILLING)
def invoice_pdf(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('order', 'order__client', 'boq').prefetch_related('line_items'),
        pk=pk,
    )
    pdf_buffer = build_invoice_pdf(invoice)
    filename = f"Invoice_{invoice.invoice_number}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
