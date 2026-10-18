"""Purchase rates, profit margin, and Material Master supply-rate updates."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import (
    MaterialRateCard,
    PurchaseMarginSettings,
    PurchaseRate,
    PurchaseRateLog,
    _money,
)
from .permissions import can_edit_purchase_margin
from . import services


def parse_decimal(value, default=None):
    if value is None:
        return default
    text = str(value).strip().replace(',', '').replace('₹', '').replace('%', '')
    text = text.replace('Rs.', '').replace('Rs', '').strip()
    if text == '':
        return default
    try:
        return Decimal(text)
    except InvalidOperation:
        return default


def normalize_code(code):
    return ' '.join(str(code or '').strip().split()).upper()[:30]


def default_margin_percent():
    return PurchaseMarginSettings.get_solo().default_margin_percent


def _log(user, row_data, outcome, detail, source, filename=''):
    PurchaseRateLog.objects.create(
        item_code=row_data.get('item_code', '')[:30],
        item_name=(row_data.get('item_name') or '')[:200],
        purchase_rate=row_data.get('purchase_rate'),
        supply_rate=row_data.get('supply_rate'),
        margin_percent=row_data.get('margin_percent'),
        outcome=outcome,
        detail=detail[:300],
        source=source or '',
        source_filename=(filename or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def find_purchase_rate(code):
    if not code:
        return None
    return PurchaseRate.objects.filter(item_code__iexact=code).first()


def find_material(code):
    if not code:
        return None
    return MaterialRateCard.objects.filter(item_code__iexact=code).first()


def code_for_item_name(name):
    cleaned = ' '.join(str(name or '').split())
    if not cleaned:
        return ''
    row = PurchaseRate.objects.filter(item_name__iexact=cleaned).first()
    if row:
        return row.item_code
    card = MaterialRateCard.objects.filter(item_name__iexact=cleaned).first()
    if card:
        return card.item_code
    return ''


def suggest_code(name):
    import re
    slug = re.sub(r'[^A-Z0-9]+', '-', str(name or '').upper()).strip('-')[:24]
    if not slug:
        slug = 'ITEM'
    candidate = slug
    suffix = 2
    while (
        PurchaseRate.objects.filter(item_code__iexact=candidate).exists()
        or MaterialRateCard.objects.filter(item_code__iexact=candidate).exists()
    ):
        candidate = f'{slug[:24]}-{suffix}'[:30]
        suffix += 1
    return candidate


def sync_material_master(row, user):
    """Write the supply rate onto the quotation Material Master."""
    card = find_material(row.item_code)
    is_new = card is None
    if is_new:
        card = MaterialRateCard(item_code=row.item_code, description='')
    card.item_name = row.item_name
    card.brand = row.brand
    card.unit = row.unit or 'Nos'
    card.rate = row.supply_rate
    card.gst_percent = row.gst_percent
    card.is_active = row.is_active
    services.save_rate_card_with_audit('MATERIAL', card, user, is_new=is_new)
    if row.material_id != card.pk:
        row.material = card
        row.save(update_fields=['material'])
    return card


def _margin_for_save(existing, posted_margin, user):
    if can_edit_purchase_margin(user) and posted_margin is not None:
        return posted_margin
    if existing is not None:
        return existing.margin_percent
    return default_margin_percent()


@transaction.atomic
def apply_purchase_rate(
    *,
    user,
    item_code='',
    item_name='',
    brand='',
    unit='Nos',
    gst_percent=None,
    purchase_rate=None,
    margin_percent=None,
    remarks='',
    is_active=True,
    source=PurchaseRate.SOURCE_MANUAL,
    source_filename='',
):
    """Capture a purchase rate for Rate Card approval. Material Master is not changed here."""
    name = ' '.join(str(item_name or '').split())
    code = normalize_code(item_code) or code_for_item_name(name)
    rate = parse_decimal(purchase_rate)
    gst = parse_decimal(gst_percent, Decimal('18'))
    posted_margin = parse_decimal(margin_percent)
    payload = {
        'item_code': code,
        'item_name': name,
        'purchase_rate': rate,
        'margin_percent': posted_margin,
    }

    if rate is None or rate <= 0:
        _log(user, payload, PurchaseRateLog.OUTCOME_SKIPPED, 'Purchase rate must be greater than zero.', source, source_filename)
        return {'outcome': PurchaseRateLog.OUTCOME_SKIPPED, 'detail': 'Purchase rate must be greater than zero.', 'item_code': code}
    if not name:
        _log(user, payload, PurchaseRateLog.OUTCOME_SKIPPED, 'Item name is required.', source, source_filename)
        return {'outcome': PurchaseRateLog.OUTCOME_SKIPPED, 'detail': 'Item name is required.', 'item_code': code}
    if not code:
        code = suggest_code(name)
        payload['item_code'] = code
    if gst is None or gst < 0 or gst > 100:
        gst = Decimal('18')
    if posted_margin is not None and (posted_margin < 0 or posted_margin > 300):
        posted_margin = None

    existing = find_purchase_rate(code)
    if existing and rate <= existing.purchase_rate:
        detail = (
            f'Kept purchase rate {existing.purchase_rate}. '
            f'New rate { _money(rate) } is not higher.'
        )
        _log(
            user,
            {**payload, 'purchase_rate': rate, 'supply_rate': existing.supply_rate, 'margin_percent': existing.margin_percent},
            PurchaseRateLog.OUTCOME_KEPT,
            detail,
            source,
            source_filename,
        )
        return {
            'outcome': PurchaseRateLog.OUTCOME_KEPT,
            'detail': detail,
            'item_code': existing.item_code,
            'purchase_rate': existing,
        }

    margin = _margin_for_save(existing, posted_margin, user)
    if margin is None or margin < 0 or margin > 300:
        margin = default_margin_percent()

    created = existing is None
    row = existing or PurchaseRate(item_code=code)
    row.item_code = existing.item_code if existing else code
    row.item_name = name
    row.brand = (brand or '')[:100]
    row.unit = (unit or 'Nos')[:20]
    row.gst_percent = gst
    row.purchase_rate = _money(rate)
    row.margin_percent = margin
    if remarks:
        row.remarks = str(remarks)[:300]
    row.is_active = bool(is_active)
    row.source = source
    row.source_filename = (source_filename or '')[:255]
    row.updated_by = user if getattr(user, 'is_authenticated', False) else None
    row.status = PurchaseRate.STATUS_PENDING
    row.approved_by = None
    row.approved_at = None
    row.save()

    outcome = PurchaseRateLog.OUTCOME_CREATED if created else PurchaseRateLog.OUTCOME_REPLACED
    detail = 'Captured for Rate Card approval. Material Master updates after approval.'
    _log(
        user,
        {
            'item_code': row.item_code,
            'item_name': row.item_name,
            'purchase_rate': row.purchase_rate,
            'supply_rate': row.supply_rate,
            'margin_percent': row.margin_percent,
        },
        outcome,
        detail,
        source,
        source_filename,
    )
    return {'outcome': outcome, 'detail': detail, 'item_code': row.item_code, 'purchase_rate': row}


def _mark_pending(row, user):
    row.status = PurchaseRate.STATUS_PENDING
    row.approved_by = None
    row.approved_at = None
    row.updated_by = user if getattr(user, 'is_authenticated', False) else None


@transaction.atomic
def save_rate_card(
    row,
    user,
    *,
    purchase_rate=None,
    margin_percent=None,
    gst_percent=None,
    brand=None,
    unit=None,
    remarks=None,
    is_active=None,
    approve=False,
):
    """Director edits the rate card. Material Master changes only when approve=True."""
    rate = parse_decimal(purchase_rate) if purchase_rate not in (None, '') else None
    margin = parse_decimal(margin_percent) if margin_percent not in (None, '') else None
    gst = parse_decimal(gst_percent) if gst_percent not in (None, '') else None
    if rate is not None and rate <= 0:
        return {'outcome': PurchaseRateLog.OUTCOME_SKIPPED, 'detail': 'Purchase rate must be greater than zero.'}
    if margin is not None and (margin < 0 or margin > 300):
        return {'outcome': PurchaseRateLog.OUTCOME_SKIPPED, 'detail': 'Enter a margin from 0 to 300.'}
    if gst is not None and (gst < 0 or gst > 100):
        return {'outcome': PurchaseRateLog.OUTCOME_SKIPPED, 'detail': 'Enter a GST percent from 0 to 100.'}

    changed = False
    if rate is not None and _money(rate) != row.purchase_rate:
        row.purchase_rate = _money(rate)
        changed = True
    if margin is not None and margin != row.margin_percent:
        row.margin_percent = margin
        changed = True
    if gst is not None and gst != row.gst_percent:
        row.gst_percent = gst
        changed = True
    if brand is not None and brand[:100] != row.brand:
        row.brand = brand[:100]
        changed = True
    if unit is not None and (unit or 'Nos')[:20] != row.unit:
        row.unit = (unit or 'Nos')[:20]
        changed = True
    if remarks is not None and remarks[:300] != row.remarks:
        row.remarks = remarks[:300]
        changed = True
    if is_active is not None and bool(is_active) != row.is_active:
        row.is_active = bool(is_active)
        changed = True

    if approve:
        row.updated_by = user if getattr(user, 'is_authenticated', False) else None
        row.status = PurchaseRate.STATUS_APPROVED
        row.approved_by = row.updated_by
        row.approved_at = timezone.now()
        row.save()
        sync_material_master(row, user)
        detail = f'Approved. Supply rate {row.supply_rate} written to Material Master.'
        outcome = PurchaseRateLog.OUTCOME_APPROVED
    else:
        if changed:
            _mark_pending(row, user)
        row.save()
        detail = 'Rate card saved. Approve it to update Material Master.'
        outcome = PurchaseRateLog.OUTCOME_REPLACED
    _log(
        user,
        {
            'item_code': row.item_code,
            'item_name': row.item_name,
            'purchase_rate': row.purchase_rate,
            'supply_rate': row.supply_rate,
            'margin_percent': row.margin_percent,
        },
        outcome,
        detail,
        row.source,
    )
    return {'outcome': outcome, 'detail': detail, 'purchase_rate': row}


@transaction.atomic
def save_default_margin(margin_percent, user, apply_to_all=False):
    margin = parse_decimal(margin_percent)
    if margin is None or margin < 0 or margin > 300:
        return {'updated': 0, 'detail': 'Enter a margin from 0 to 300.'}
    settings_row = PurchaseMarginSettings.get_solo()
    settings_row.default_margin_percent = margin
    settings_row.updated_by = user if getattr(user, 'is_authenticated', False) else None
    settings_row.save()
    updated = 0
    if apply_to_all:
        for row in PurchaseRate.objects.all():
            save_rate_card(row, user, margin_percent=margin, approve=False)
            updated += 1
    return {'updated': updated, 'margin': margin}
