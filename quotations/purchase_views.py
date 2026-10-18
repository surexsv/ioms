from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access_control import REASON_ROLE
from accounts.decorators import access_denied_response

from .models import PurchaseMarginSettings, PurchaseRate, PurchaseRateLog
from .permissions import can_prepare_rate_card, can_view_purchase_rates
from .purchase_extract import DocumentReadError, rows_from_upload
from .purchase_rates import apply_purchase_rate, save_default_margin, save_rate_card


def _guard_entry(request):
    if not can_view_purchase_rates(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    return None


def _guard_rate_card(request):
    if not can_prepare_rate_card(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    return None


def _summarize(results):
    counts = {
        PurchaseRateLog.OUTCOME_CREATED: 0,
        PurchaseRateLog.OUTCOME_REPLACED: 0,
        PurchaseRateLog.OUTCOME_KEPT: 0,
        PurchaseRateLog.OUTCOME_SKIPPED: 0,
    }
    for result in results:
        counts[result['outcome']] = counts.get(result['outcome'], 0) + 1
    parts = []
    if counts[PurchaseRateLog.OUTCOME_CREATED]:
        parts.append(f"{counts[PurchaseRateLog.OUTCOME_CREATED]} added")
    if counts[PurchaseRateLog.OUTCOME_REPLACED]:
        parts.append(f"{counts[PurchaseRateLog.OUTCOME_REPLACED]} updated")
    if counts[PurchaseRateLog.OUTCOME_KEPT]:
        parts.append(f"{counts[PurchaseRateLog.OUTCOME_KEPT]} kept because the new rate was not higher")
    if counts[PurchaseRateLog.OUTCOME_SKIPPED]:
        parts.append(f"{counts[PurchaseRateLog.OUTCOME_SKIPPED]} skipped")
    return ', '.join(parts) or 'No rows saved.'


def _filtered_rates(request):
    query = (request.GET.get('q') or '').strip()
    rates = PurchaseRate.objects.all()
    if query:
        rates = rates.filter(
            Q(item_code__icontains=query) | Q(item_name__icontains=query) | Q(brand__icontains=query)
        )
    return rates, query


@login_required
def purchase_rate_list(request):
    denied = _guard_entry(request)
    if denied:
        return denied

    captured_rows = []
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            result = apply_purchase_rate(
                user=request.user,
                item_code=request.POST.get('item_code'),
                item_name=request.POST.get('item_name'),
                brand=request.POST.get('brand'),
                unit=request.POST.get('unit') or 'Nos',
                gst_percent=request.POST.get('gst_percent') or '18',
                purchase_rate=request.POST.get('purchase_rate'),
                remarks=request.POST.get('remarks'),
                is_active=True,
                source=PurchaseRate.SOURCE_MANUAL,
            )
            if result['outcome'] in (PurchaseRateLog.OUTCOME_CREATED, PurchaseRateLog.OUTCOME_REPLACED):
                messages.success(request, f"{result['item_code']}: {result['detail']}")
            elif result['outcome'] == PurchaseRateLog.OUTCOME_KEPT:
                messages.warning(request, f"{result['item_code']}: {result['detail']}")
            else:
                messages.error(request, result['detail'])
            return redirect('purchase_rate_list')
        if action == 'upload':
            upload = request.FILES.get('document')
            if not upload:
                messages.error(request, 'Choose a PDF or a scanned bill.')
            else:
                try:
                    captured_rows = rows_from_upload(upload)
                    request.session['purchase_rate_capture_name'] = upload.name
                    messages.info(request, f'Read {len(captured_rows)} row(s) from {upload.name}. Check them, then save.')
                except DocumentReadError as exc:
                    messages.error(request, str(exc))
        elif action == 'save_captured':
            filename = request.session.pop('purchase_rate_capture_name', '')
            results = []
            codes = request.POST.getlist('captured_code')
            names = request.POST.getlist('captured_name')
            brands = request.POST.getlist('captured_brand')
            units = request.POST.getlist('captured_unit')
            rates = request.POST.getlist('captured_rate')
            gsts = request.POST.getlist('captured_gst')
            remarks = request.POST.getlist('captured_remarks')
            included = set(request.POST.getlist('captured_include'))
            for index, name in enumerate(names):
                if str(index) not in included:
                    continue
                results.append(apply_purchase_rate(
                    user=request.user,
                    item_code=codes[index] if index < len(codes) else '',
                    item_name=name,
                    brand=brands[index] if index < len(brands) else '',
                    unit=units[index] if index < len(units) else 'Nos',
                    gst_percent=gsts[index] if index < len(gsts) else '18',
                    purchase_rate=rates[index] if index < len(rates) else '',
                    remarks=remarks[index] if index < len(remarks) else '',
                    source=PurchaseRate.SOURCE_DOCUMENT,
                    source_filename=filename,
                ))
            messages.success(request, _summarize(results))
            return redirect('purchase_rate_list')

    rates, query = _filtered_rates(request)
    return render(request, 'quotations/purchase_rate_list.html', {
        'rates': rates[:500],
        'logs': PurchaseRateLog.objects.select_related('created_by')[:40],
        'captured_rows': captured_rows,
        'query': query,
    })


@login_required
def rate_card_list(request):
    denied = _guard_rate_card(request)
    if denied:
        return denied

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_margin':
            result = save_default_margin(
                request.POST.get('default_margin_percent'),
                request.user,
                apply_to_all=request.POST.get('apply_to_all') == '1',
            )
            if result.get('margin') is None:
                messages.error(request, result['detail'])
            elif result['updated']:
                messages.success(
                    request,
                    f"Profit margin is {result['margin']}%. {result['updated']} rate card row(s) now need approval.",
                )
            else:
                messages.success(request, f"Default profit margin is now {result['margin']}%.")
            return redirect('rate_card_list')
        if action in ('save_row', 'approve_row'):
            row = get_object_or_404(PurchaseRate, pk=request.POST.get('row_id'))
            result = save_rate_card(
                row,
                request.user,
                purchase_rate=request.POST.get('purchase_rate'),
                margin_percent=request.POST.get('margin_percent'),
                gst_percent=request.POST.get('gst_percent'),
                brand=request.POST.get('brand', ''),
                unit=request.POST.get('unit') or 'Nos',
                remarks=request.POST.get('remarks', ''),
                is_active=request.POST.get('is_active') == 'on',
                approve=action == 'approve_row',
            )
            if result['outcome'] == PurchaseRateLog.OUTCOME_SKIPPED:
                messages.error(request, f"{row.item_code}: {result['detail']}")
            elif action == 'approve_row':
                messages.success(request, f"{row.item_code}: {result['detail']}")
            else:
                messages.success(request, f"{row.item_code}: {result['detail']}")
            return redirect('rate_card_list')
        if action == 'approve_all':
            approved = 0
            for row in PurchaseRate.objects.filter(status=PurchaseRate.STATUS_PENDING):
                save_rate_card(row, request.user, approve=True)
                approved += 1
            messages.success(request, f'Approved {approved} rate card row(s) into Material Master.')
            return redirect('rate_card_list')

    rates, query = _filtered_rates(request)
    pending_count = PurchaseRate.objects.filter(status=PurchaseRate.STATUS_PENDING).count()
    return render(request, 'quotations/rate_card_list.html', {
        'rates': rates[:500],
        'margin_settings': PurchaseMarginSettings.get_solo(),
        'pending_count': pending_count,
        'query': query,
    })
