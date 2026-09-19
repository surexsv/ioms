"""Invoice Excel/CSV import views."""

from functools import wraps
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import access_denied_response
from billing.import_service import (
    ImportFileError,
    batch_totals,
    build_template_workbook,
    confirm_import_batch,
    creatable_items,
    parse_and_validate,
)
from billing.models import InvoiceImportBatch, InvoiceImportItem
from billing.pdf import build_invoice_pdf
from billing.permissions import can_create_invoice, can_view_invoices
from billing.views import billing_view_required
from config.company import COMPANY

try:
    from billing.permissions import can_import_invoices
except ImportError:
    can_import_invoices = can_create_invoice

try:
    from billing.permissions import can_view_invoice_imports
except ImportError:
    can_view_invoice_imports = can_view_invoices


def _permission_required(check):
    def decorator(view_func):
        @billing_view_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                return access_denied_response(
                    request,
                    reason='unauthorized',
                    module_key='manage_billing',
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


can_import_invoices_required = _permission_required(can_import_invoices)
can_view_invoice_imports_required = _permission_required(can_view_invoice_imports)


def _batch_or_404(pk):
    return get_object_or_404(
        InvoiceImportBatch.objects.select_related('uploaded_by').prefetch_related('items__client'),
        pk=pk,
    )


@can_import_invoices_required
def invoice_import_upload(request):
    if request.method == 'POST':
        uploaded = request.FILES.get('file')
        title = (request.POST.get('title') or '').strip()
        filename = getattr(uploaded, 'name', '') if uploaded else ''
        try:
            batch = parse_and_validate(uploaded, filename, request.user, title=title)
        except ImportFileError as exc:
            messages.error(request, str(exc))
            return render(request, 'billing/invoice_import_upload.html', {
                'gst_rate_percent': COMPANY['gst_rate_percent'],
                'title_value': title,
            })
        messages.success(
            request,
            f'File validated: {batch.invoice_count} invoice(s) from {batch.total_rows} row(s). Review before confirming.',
        )
        return redirect('invoice_import_preview', pk=batch.pk)

    return render(request, 'billing/invoice_import_upload.html', {
        'gst_rate_percent': COMPANY['gst_rate_percent'],
        'title_value': '',
    })


@can_import_invoices_required
def invoice_import_template(request):
    workbook = build_template_workbook()
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="invoice_import_template.xlsx"'
    return response


@can_view_invoice_imports_required
def invoice_import_history(request):
    batches = InvoiceImportBatch.objects.select_related('uploaded_by')
    return render(request, 'billing/invoice_import_history.html', {
        'batches': batches,
        'can_import': can_import_invoices(request.user),
    })


@can_view_invoice_imports_required
def invoice_import_preview(request, pk):
    batch = _batch_or_404(pk)
    items = list(batch.items.select_related('client', 'created_invoice'))
    creatable = creatable_items(batch)
    can_confirm = (
        batch.status == InvoiceImportBatch.STATUS_VALIDATED
        and creatable.exists()
        and can_import_invoices(request.user)
    )
    return render(request, 'billing/invoice_import_preview.html', {
        'batch': batch,
        'items': items,
        'totals': batch_totals(batch),
        'creatable_totals': batch_totals(batch, statuses=[
            InvoiceImportItem.STATUS_VALID,
            InvoiceImportItem.STATUS_WARNING,
        ]),
        'can_confirm': can_confirm,
        'can_import': can_import_invoices(request.user),
        'can_download_pdfs': (
            batch.status == InvoiceImportBatch.STATUS_CONFIRMED
            and batch.created_invoices.exists()
        ),
        'gst_rate_percent': COMPANY['gst_rate_percent'],
    })


@can_view_invoice_imports_required
def invoice_import_item(request, pk, item_id):
    batch = _batch_or_404(pk)
    item = get_object_or_404(
        InvoiceImportItem.objects.select_related('client', 'created_invoice'),
        pk=item_id,
        batch=batch,
    )
    payload = item.payload or {}
    return render(request, 'billing/invoice_import_item.html', {
        'batch': batch,
        'item': item,
        'payload': payload,
        'lines': payload.get('lines') or [],
        'can_import': can_import_invoices(request.user),
    })


@can_import_invoices_required
@require_POST
def invoice_import_confirm(request, pk):
    batch = get_object_or_404(InvoiceImportBatch, pk=pk)
    result = confirm_import_batch(batch, request.user)
    if result['ok']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])
    return redirect('invoice_import_preview', pk=batch.pk)


@can_view_invoice_imports_required
def invoice_import_pdfs(request, pk):
    batch = get_object_or_404(
        InvoiceImportBatch.objects.prefetch_related('created_invoices__line_items', 'created_invoices__client'),
        pk=pk,
    )
    invoices = list(batch.created_invoices.all())
    if not invoices:
        messages.error(request, 'No imported invoices are available as PDF for this batch.')
        return redirect('invoice_import_preview', pk=batch.pk)

    buffer = BytesIO()
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as archive:
        for invoice in invoices:
            pdf_buffer = build_invoice_pdf(invoice)
            archive.writestr(f'Invoice_{invoice.invoice_number}.pdf', pdf_buffer.getvalue())
    buffer.seek(0)
    filename = f'import_batch_{batch.pk}_invoices.pdf.zip'
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
