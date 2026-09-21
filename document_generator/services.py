from django.db import transaction
from django.utils import timezone

from .constants import (
    DOC_BOQ,
    DOC_ENQUIRY,
    DOC_ESTIMATE_BOQ,
    DOC_INVOICE,
    DOC_ORDER,
    DOC_PURCHASE_ORDER,
    DOC_QUOTATION,
    DOC_REQUEST,
    DOC_SCHEDULE,
    DOC_PM,
    DOC_SPECIAL_PROJECT,
    DOC_WCR,
    DOCUMENT_TYPE_LABELS,
    PREFIX_FIELD_MAP,
)
from .models import DocumentCounter, DocumentNumberSettings, GeneratedDocumentNumber


class DocumentNumberError(Exception):
    pass


def get_year_series(year=None):
    """Rolling fiscal-style year series: 2026 -> 2627, 2027 -> 2728."""
    if year is None:
        year = timezone.now().year
    return f'{year % 100:02d}{(year + 1) % 100:02d}'


def build_document_number(settings, document_type, serial, year_series=None):
    if year_series is None:
        year_series = get_year_series()
    doc_prefix = settings.prefix_for(document_type)
    serial_str = str(serial).zfill(settings.serial_length)
    return f'{settings.company_prefix}{doc_prefix}{year_series}{serial_str}'


def preview_next_number(document_type, year_series=None):
    settings = DocumentNumberSettings.get_solo()
    if year_series is None:
        year_series = get_year_series()
    counter = DocumentCounter.objects.filter(
        document_type=document_type,
        year_series=year_series,
    ).first()
    next_serial = (counter.last_serial + 1) if counter else 1
    return build_document_number(settings, document_type, next_serial, year_series)


def _number_exists(document_number):
    from billing.models import Invoice
    from boq.models import BOQ
    from orders.models import Order
    from quotations.models import Quotation
    from wcr.models import WorkCompletionReport

    if GeneratedDocumentNumber.objects.filter(document_number=document_number).exists():
        return True
    if Order.objects.filter(order_no=document_number).exists():
        return True
    if Quotation.objects.filter(quotation_number=document_number).exists():
        return True
    if BOQ.objects.filter(boq_number=document_number).exists():
        return True
    if Invoice.objects.filter(invoice_number=document_number).exists():
        return True
    if WorkCompletionReport.objects.filter(wcr_number=document_number).exists():
        return True
    try:
        from scheduling.models import WorkSchedule
        if WorkSchedule.objects.filter(schedule_number=document_number).exists():
            return True
    except Exception:
        pass
    try:
        from enquiries.models import Enquiry
        if Enquiry.objects.filter(enquiry_number=document_number).exists():
            return True
    except Exception:
        pass
    try:
        from estimate_boq.models import EstimateBOQ
        if EstimateBOQ.objects.filter(estimate_boq_number=document_number).exists():
            return True
    except Exception:
        pass
    try:
        from employee_requests.models import EmployeeRequest
        if EmployeeRequest.objects.filter(request_number=document_number).exists():
            return True
    except Exception:
        pass
    try:
        from special_projects.models import SpecialProject
        if SpecialProject.objects.filter(project_number=document_number).exists():
            return True
    except Exception:
        pass
    try:
        from preventive_maintenance.models import PMObservation
        if PMObservation.objects.filter(pm_number=document_number).exists():
            return True
    except Exception:
        pass
    return False


@transaction.atomic
def generate_document_number(document_type, user=None, year_series=None):
    settings = DocumentNumberSettings.get_solo()
    if year_series is None:
        year_series = get_year_series()

    counter = (
        DocumentCounter.objects
        .select_for_update()
        .filter(document_type=document_type, year_series=year_series)
        .first()
    )
    if not counter:
        counter = DocumentCounter.objects.create(
            document_type=document_type,
            year_series=year_series,
            last_serial=0,
        )

    for _ in range(100):
        counter.last_serial += 1
        number = build_document_number(settings, document_type, counter.last_serial, year_series)
        if not _number_exists(number):
            counter.last_number = number
            counter.save(update_fields=['last_serial', 'last_number', 'updated_at'])
            GeneratedDocumentNumber.objects.create(
                document_type=document_type,
                document_number=number,
                year_series=year_series,
                serial=counter.last_serial,
                generated_by=user,
            )
            return number
    raise DocumentNumberError(f'Unable to allocate unique number for {document_type}')


def parse_document_number(number, document_type, settings=None):
    """Extract (year_series, serial) from a formatted document number."""
    if not number or settings is None:
        settings = DocumentNumberSettings.get_solo()
    company = settings.company_prefix
    if not number.startswith(company):
        return None
    rest = number[len(company):]
    doc_prefix = settings.prefix_for(document_type) or ''
    if document_type == DOC_INVOICE:
        # Current series: ITSPL26270001 (blank prefix)
        # Legacy series: ITSPLINV26270001
        if doc_prefix and rest.startswith(doc_prefix):
            rest = rest[len(doc_prefix):]
        elif not doc_prefix and rest.startswith('INV') and len(rest) > 7 and rest[3:7].isdigit():
            rest = rest[3:]
    else:
        if not rest.startswith(doc_prefix):
            return None
        rest = rest[len(doc_prefix):]
    serial_len = settings.serial_length
    if len(rest) < 4 + serial_len:
        return None
    year_series = rest[:4]
    serial_part = rest[4:4 + serial_len]
    if not year_series.isdigit() or not serial_part.isdigit():
        return None
    return year_series, int(serial_part)


def _collect_existing_numbers(document_type):
    from billing.models import Invoice
    from boq.models import BOQ
    from orders.models import Order
    from quotations.models import Quotation
    from wcr.models import WorkCompletionReport

    field_map = {
        DOC_ORDER: Order.objects.exclude(order_no='').values_list('order_no', flat=True),
        DOC_QUOTATION: Quotation.objects.exclude(quotation_number='').values_list('quotation_number', flat=True),
        DOC_WCR: WorkCompletionReport.objects.exclude(
            wcr_number__isnull=True,
        ).exclude(wcr_number='').values_list('wcr_number', flat=True),
        DOC_BOQ: BOQ.objects.exclude(boq_number='').values_list('boq_number', flat=True),
        DOC_INVOICE: Invoice.objects.values_list('invoice_number', flat=True),
        DOC_PURCHASE_ORDER: [],
    }
    try:
        from enquiries.models import Enquiry
        field_map[DOC_ENQUIRY] = Enquiry.objects.exclude(
            enquiry_number='',
        ).values_list('enquiry_number', flat=True)
    except Exception:
        field_map[DOC_ENQUIRY] = []
    try:
        from estimate_boq.models import EstimateBOQ
        field_map[DOC_ESTIMATE_BOQ] = EstimateBOQ.objects.exclude(
            estimate_boq_number='',
        ).values_list('estimate_boq_number', flat=True)
    except Exception:
        field_map[DOC_ESTIMATE_BOQ] = []
    try:
        from employee_requests.models import EmployeeRequest
        field_map[DOC_REQUEST] = EmployeeRequest.objects.exclude(
            request_number='',
        ).values_list('request_number', flat=True)
    except Exception:
        field_map[DOC_REQUEST] = []
    try:
        from special_projects.models import SpecialProject
        field_map[DOC_SPECIAL_PROJECT] = SpecialProject.objects.exclude(
            project_number='',
        ).values_list('project_number', flat=True)
    except Exception:
        field_map[DOC_SPECIAL_PROJECT] = []
    try:
        from preventive_maintenance.models import PMObservation
        field_map[DOC_PM] = PMObservation.objects.exclude(
            pm_number='',
        ).values_list('pm_number', flat=True)
    except Exception:
        field_map[DOC_PM] = []
    return list(field_map.get(document_type, []))


def seed_counters_from_existing():
    """Initialize counters from existing ITSPL-format numbers without changing records."""
    settings = DocumentNumberSettings.get_solo()
    current_series = get_year_series()
    summary = {}

    for document_type, _label in (
        (DOC_ORDER, 'Order'),
        (DOC_QUOTATION, 'Quotation'),
        (DOC_WCR, 'WCR'),
        (DOC_BOQ, 'BOQ'),
        (DOC_INVOICE, 'Invoice'),
        (DOC_PURCHASE_ORDER, 'Purchase Order'),
        (DOC_ENQUIRY, 'Enquiry'),
        (DOC_ESTIMATE_BOQ, 'Estimate BOQ'),
        (DOC_REQUEST, 'Employee Request'),
        (DOC_SPECIAL_PROJECT, 'Special Project'),
        (DOC_PM, 'PM Observation'),
    ):
        max_by_series = {}
        for number in _collect_existing_numbers(document_type):
            parsed = parse_document_number(number, document_type, settings)
            if not parsed:
                if document_type == DOC_INVOICE and number.startswith(settings.company_prefix):
                    rest = number[len(settings.company_prefix):]
                    if len(rest) >= 8 and rest[:4].isdigit() and rest[4:8].isdigit():
                        parsed = (rest[:4], int(rest[4:8]))
            if parsed:
                year_series, serial = parsed
                max_by_series[year_series] = max(max_by_series.get(year_series, 0), serial)

        for year_series, max_serial in max_by_series.items():
            counter, created = DocumentCounter.objects.get_or_create(
                document_type=document_type,
                year_series=year_series,
                defaults={'last_serial': max_serial, 'last_number': ''},
            )
            if not created and counter.last_serial < max_serial:
                counter.last_serial = max_serial
            if counter.last_serial > 0:
                counter.last_number = build_document_number(
                    settings, document_type, counter.last_serial, year_series,
                )
            counter.save()
        summary[document_type] = max_by_series.get(current_series, 0)

    return summary


def control_panel_rows():
    settings = DocumentNumberSettings.get_solo()
    year_series = get_year_series()
    rows = []
    for document_type, label in DOCUMENT_TYPE_LABELS.items():
        counter = DocumentCounter.objects.filter(
            document_type=document_type,
            year_series=year_series,
        ).first()
        last_number = counter.last_number if counter and counter.last_number else '—'
        next_number = preview_next_number(document_type, year_series)
        rows.append({
            'document_type': document_type,
            'label': label,
            'year_series': year_series,
            'last_number': last_number,
            'last_serial': counter.last_serial if counter else 0,
            'next_number': next_number,
        })
    return rows


@transaction.atomic
def reset_counter(document_type, year_series=None, user=None):
    if year_series is None:
        year_series = get_year_series()
    counter, _ = DocumentCounter.objects.get_or_create(
        document_type=document_type,
        year_series=year_series,
        defaults={'last_serial': 0},
    )
    counter.last_serial = 0
    counter.last_number = ''
    counter.save(update_fields=['last_serial', 'last_number', 'updated_at'])
    return counter
