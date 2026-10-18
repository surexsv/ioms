from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access_control import REASON_ROLE
from accounts.decorators import access_denied_response

from .models import PurchaseMarginSettings, PurchaseRate, PurchaseRateLog, _money
from .permissions import can_edit_purchase_margin, can_view_purchase_rates
from .purchase_extract import DocumentReadError, rows_from_upload
from .purchase_rates import (
    apply_purchase_rate,
    default_margin_percent,
    save_default_margin,
    seed_purchase_rates_from_material_master,
    update_margin,
)


def _guard(request):
    if not can_view_purchase_rates(request.user):
        return access_denied_response(request, reason=REASON_ROLE)
    return None


def _preview_supply(rows):
    margin = default_margin_percent()
    for row in rows:
        rate = row.get('purchase_rate') or 0
        row['margin_percent'] = margin
        row['margin_amount'] = _money(rate * margin / 100)
        row['supply_rate'] = _money(rate + row['margin_amount'])
    return rows


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


@login_required
def purchase_rate_list(request):
    denied = _guard(request)
    if denied:
        return denied

    captured_rows = []
    can_edit_margin = can_edit_purchase_margin(request.user)
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
                margin_percent=request.POST.get('margin_percent'),
                remarks=request.POST.get('remarks'),
                is_active=request.POST.get('is_active') == 'on',
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
                messages.error(request, 'Choose a PDF, photo, or spreadsheet.')
            else:
                try:
                    captured_rows = _preview_supply(rows_from_upload(upload))
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
        elif action == 'save_margin':
            if not can_edit_margin:
                return access_denied_response(request, reason=REASON_ROLE)
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
                    f"Profit margin is {result['margin']}%. Updated {result['updated']} material rate(s).",
                )
            else:
                messages.success(request, f"Default profit margin is now {result['margin']}%.")
            return redirect('purchase_rate_list')
        elif action == 'update_margin':
            if not can_edit_margin:
                return access_denied_response(request, reason=REASON_ROLE)
            row = get_object_or_404(PurchaseRate, pk=request.POST.get('row_id'))
            result = update_margin(row, request.POST.get('margin_percent'), request.user)
            if result['outcome'] == PurchaseRateLog.OUTCOME_SKIPPED:
                messages.error(request, result['detail'])
            else:
                messages.success(request, f"{row.item_code}: {result['detail']}")
            return redirect('purchase_rate_list')
        elif action == 'seed_material_master':
            if not can_edit_margin:
                return access_denied_response(request, reason=REASON_ROLE)
            result = seed_purchase_rates_from_material_master(request.user)
            messages.success(
                request,
                f"Created {result['created']} purchase rate(s) at {result['margin']}% margin. "
                f"Skipped {result['skipped']} item(s) that already have a purchase rate.",
            )
            return redirect('purchase_rate_list')

    query = (request.GET.get('q') or '').strip()
    rates = PurchaseRate.objects.select_related('material')
    if query:
        rates = rates.filter(
            Q(item_code__icontains=query) | Q(item_name__icontains=query) | Q(brand__icontains=query)
        )
    settings_row = PurchaseMarginSettings.get_solo()
    return render(request, 'quotations/purchase_rate_list.html', {
        'rates': rates[:500],
        'logs': PurchaseRateLog.objects.select_related('created_by')[:40],
        'margin_settings': settings_row,
        'can_edit_margin': can_edit_margin,
        'captured_rows': captured_rows,
        'query': query,
    })
