"""Optimized stuck-case detection and enriched list rows."""

from datetime import datetime, timedelta

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from case_intelligence.categories import (
    CAT_DELAYED_ORDERS,
    CAT_DELAYED_SURVEYS,
    CAT_INVOICE_APPROVAL,
    CAT_PENDING_ENQUIRIES,
    CAT_PENDING_PAYMENTS,
    CAT_PENDING_WCR,
    CAT_QUOTATION_FOLLOWUP,
    CAT_STUCK_TOTAL,
    CATEGORY_LABELS,
)
from case_intelligence.constants import (
    HEALTH_GREEN,
    HEALTH_LABELS,
    HEALTH_RED,
    HEALTH_YELLOW,
    STUCK_ENQUIRY_INACTIVE,
    STUCK_INVOICE,
    STUCK_ORDER_SCHEDULE,
    STUCK_PAYMENT,
    STUCK_QUOTATION,
    STUCK_SURVEY_DELAYED,
    STUCK_WCR,
)
from case_intelligence.models import CaseActivityLog
from company_settings.case_intelligence import get_case_settings


def _user_name(user):
    if not user:
        return '—'
    return user.get_full_name() or user.username


def _last_activity_map(document_numbers):
    numbers = [n for n in document_numbers if n]
    if not numbers:
        return {}
    logs = (
        CaseActivityLog.objects.filter(document_number__in=numbers)
        .select_related('user')
        .order_by('document_number', '-activity_at')
    )
    result = {}
    for log in logs:
        if log.document_number not in result:
            result[log.document_number] = log
    return result


def _row(**kwargs):
    health = kwargs.pop('health', HEALTH_GREEN)
    return {
        **kwargs,
        'health': health,
        'health_label': HEALTH_LABELS.get(health, 'On Track'),
    }


def _health_for_days(days, flag=None):
    if flag:
        return HEALTH_RED
    if days is None:
        return HEALTH_GREEN
    if days >= 7:
        return HEALTH_RED
    if days >= 3:
        return HEALTH_YELLOW
    return HEALTH_GREEN


def _enrich_rows(rows):
    if not rows:
        return []
    activity_map = _last_activity_map([r['document_number'] for r in rows])
    enriched = []
    for base in rows:
        last = activity_map.get(base['document_number'])
        last_at = last.activity_at if last else base.get('last_activity_at')
        last_label = last.description if last else base.get('last_activity_label', '—')
        days = base.get('days_pending')
        if days is None and last_at:
            days = (timezone.now() - last_at).days
        enriched.append(_row(
            document_number=base['document_number'],
            document_type=base['document_type'],
            client=base['client'],
            status=base['status'],
            assigned_to=base.get('assigned_to', '—'),
            days_pending=days,
            last_activity_at=last_at,
            last_activity_label=last_label,
            next_action=base.get('next_action', '—'),
            flag=base.get('flag', ''),
            health=_health_for_days(days, base.get('flag')),
            url_name=base.get('url_name', ''),
            url_pk=base.get('url_pk'),
        ))
    return enriched


def list_pending_enquiries():
    from enquiries.models import Enquiry

    cfg = get_case_settings()
    today = timezone.now()
    inactive_cutoff = today - timedelta(days=cfg.enquiry_delay_days)
    closed = ('CONVERTED_TO_ORDER', 'WON', 'LOST', 'CLOSED')
    rows = []
    qs = Enquiry.objects.exclude(status__in=closed).select_related(
        'client', 'survey_engineer', 'assigned_project_manager',
    )
    for e in qs.iterator(chunk_size=300):
        days = (today.date() - e.enquiry_date).days if e.enquiry_date else 0
        flag = STUCK_ENQUIRY_INACTIVE if e.updated_at < inactive_cutoff else ''
        next_action = 'Survey assignment'
        if e.status == 'SURVEY_SCHEDULED':
            next_action = 'Survey completion'
        elif e.status == 'QUOTATION_SUBMITTED':
            next_action = 'Client approval'
        elif e.status == 'SURVEY_COMPLETED':
            next_action = 'Estimate BOQ / Quotation'
        rows.append({
            'document_number': e.enquiry_number,
            'document_type': 'Enquiry',
            'client': e.client.name,
            'status': e.get_status_display(),
            'assigned_to': _user_name(e.survey_engineer or e.assigned_project_manager),
            'days_pending': days,
            'last_activity_at': e.updated_at,
            'next_action': next_action,
            'flag': flag,
            'url_name': 'enquiry_detail',
            'url_pk': e.pk,
        })
    return _enrich_rows(rows)


def list_delayed_surveys():
    from enquiries.models import Enquiry

    cfg = get_case_settings()
    today = timezone.localdate()
    survey_cutoff = today - timedelta(days=cfg.survey_delay_days)
    rows = []
    for e in Enquiry.objects.filter(
        status='SURVEY_SCHEDULED', survey_date__lte=survey_cutoff,
    ).select_related('client', 'survey_engineer'):
        days = (today - e.survey_date).days if e.survey_date else 0
        rows.append({
            'document_number': e.enquiry_number,
            'document_type': 'Enquiry',
            'client': e.client.name,
            'status': e.get_status_display(),
            'assigned_to': _user_name(e.survey_engineer),
            'days_pending': days,
            'last_activity_at': e.updated_at,
            'next_action': 'Complete survey / submit WCR',
            'flag': STUCK_SURVEY_DELAYED,
            'url_name': 'enquiry_detail',
            'url_pk': e.pk,
        })
    return _enrich_rows(rows)


def list_quotation_followup():
    from quotations.models import Quotation

    cfg = get_case_settings()
    cutoff = timezone.now() - timedelta(days=cfg.quotation_followup_days)
    rows = []
    for q in Quotation.objects.filter(
        status__in=('SENT', 'UNDER_REVIEW'), updated_at__lt=cutoff,
    ).select_related('client', 'created_by'):
        days = (timezone.now() - q.updated_at).days
        rows.append({
            'document_number': q.quotation_number,
            'document_type': 'Quotation',
            'client': q.client.name,
            'status': q.get_status_display(),
            'assigned_to': _user_name(q.created_by),
            'days_pending': days,
            'last_activity_at': q.updated_at,
            'next_action': 'Client follow-up',
            'flag': STUCK_QUOTATION,
            'url_name': 'quotation_detail',
            'url_pk': q.pk,
        })
    return _enrich_rows(rows)


def list_delayed_orders():
    from orders.models import Order
    from scheduling.models import WorkSchedule

    cfg = get_case_settings()
    cutoff = timezone.now() - timedelta(days=cfg.order_delay_days)
    has_schedule = WorkSchedule.objects.filter(order_id=OuterRef('pk'))
    rows = []
    for o in Order.objects.filter(
        status__in=('NEW', 'ASSIGNED'), created_date__lt=cutoff,
    ).annotate(_has_sched=Exists(has_schedule)).filter(
        _has_sched=False,
    ).select_related('client', 'assigned_to'):
        days = (timezone.now() - o.created_date).days
        doc = o.order_no or str(o.order_id)
        rows.append({
            'document_number': doc,
            'document_type': 'Order',
            'client': o.client.name,
            'status': o.get_status_display(),
            'assigned_to': _user_name(o.assigned_to),
            'days_pending': days,
            'last_activity_at': o.created_date,
            'next_action': 'Create execution schedule',
            'flag': STUCK_ORDER_SCHEDULE,
            'url_name': 'order_detail',
            'url_pk': o.pk,
        })
    return _enrich_rows(rows)


def list_pending_wcr():
    from orders.models import Order
    from wcr.models import WorkCompletionReport

    cfg = get_case_settings()
    cutoff = timezone.now() - timedelta(days=cfg.wcr_delay_days)
    has_wcr = WorkCompletionReport.objects.filter(order_id=OuterRef('pk'))
    rows = []
    for o in Order.objects.filter(
        status='COMPLETED', created_date__lt=cutoff,
    ).annotate(_has_wcr=Exists(has_wcr)).filter(
        _has_wcr=False,
    ).select_related('client', 'assigned_to', 'work_schedule', 'work_schedule__lead_engineer'):
        days = (timezone.now() - o.created_date).days
        doc = o.order_no or str(o.order_id)
        lead = getattr(getattr(o, 'work_schedule', None), 'lead_engineer', None)
        rows.append({
            'document_number': doc,
            'document_type': 'Order',
            'client': o.client.name,
            'status': o.get_status_display(),
            'assigned_to': _user_name(lead or o.assigned_to),
            'days_pending': days,
            'last_activity_at': o.created_date,
            'next_action': 'Submit WCR',
            'flag': STUCK_WCR,
            'url_name': 'order_detail',
            'url_pk': o.pk,
        })
    return _enrich_rows(rows)


def list_invoice_approval_pending():
    from billing.models import Invoice

    cfg = get_case_settings()
    cutoff = timezone.now() - timedelta(days=cfg.invoice_approval_days)
    rows = []
    for inv in Invoice.objects.filter(approval_status='SUBMITTED').filter(
        Q(submitted_at__lt=cutoff) | Q(submitted_at__isnull=True),
    ).select_related('order', 'order__client'):
        ref = inv.submitted_at or timezone.now()
        days = (timezone.now() - ref).days
        rows.append({
            'document_number': inv.invoice_number,
            'document_type': 'Invoice',
            'client': inv.order.client.name,
            'status': inv.get_approval_status_display(),
            'assigned_to': 'Accounts / Director',
            'days_pending': days,
            'last_activity_at': ref,
            'next_action': 'Approve invoice',
            'flag': STUCK_INVOICE,
            'url_name': 'invoice_detail',
            'url_pk': inv.pk,
        })
    return _enrich_rows(rows)


def list_pending_payments():
    from billing.models import Invoice

    cfg = get_case_settings()
    today = timezone.localdate()
    pay_cutoff = today - timedelta(days=cfg.payment_followup_days)
    rows = []
    for inv in Invoice.objects.filter(
        payment_status='PENDING', approval_status='APPROVED', due_date__lte=pay_cutoff,
    ).select_related('order', 'order__client'):
        days = (today - inv.due_date).days if inv.due_date else 0
        rows.append({
            'document_number': inv.invoice_number,
            'document_type': 'Invoice',
            'client': inv.order.client.name,
            'status': inv.payment_status,
            'assigned_to': 'Accounts',
            'days_pending': days,
            'last_activity_at': inv.approved_at,
            'next_action': 'Payment follow-up',
            'flag': STUCK_PAYMENT,
            'url_name': 'invoice_detail',
            'url_pk': inv.pk,
        })
    return _enrich_rows(rows)


_CATEGORY_FETCHERS = {
    CAT_PENDING_ENQUIRIES: list_pending_enquiries,
    CAT_DELAYED_SURVEYS: list_delayed_surveys,
    CAT_QUOTATION_FOLLOWUP: list_quotation_followup,
    CAT_DELAYED_ORDERS: list_delayed_orders,
    CAT_PENDING_WCR: list_pending_wcr,
    CAT_INVOICE_APPROVAL: list_invoice_approval_pending,
    CAT_PENDING_PAYMENTS: list_pending_payments,
}


def get_cases_by_category(category, limit=200):
    if category == CAT_STUCK_TOTAL:
        seen = set()
        combined = []
        for fn in (
            list_delayed_surveys, list_quotation_followup, list_delayed_orders,
            list_pending_wcr, list_invoice_approval_pending, list_pending_payments,
        ):
            for row in fn():
                key = (row['document_type'], row['document_number'], row['flag'])
                if key not in seen:
                    seen.add(key)
                    combined.append(row)
        inactive = [r for r in list_pending_enquiries() if r['flag'] == STUCK_ENQUIRY_INACTIVE]
        for row in inactive:
            key = (row['document_type'], row['document_number'], row['flag'])
            if key not in seen:
                seen.add(key)
                combined.append(row)
        combined.sort(key=lambda r: r.get('days_pending') or 0, reverse=True)
        return combined[:limit]
    fn = _CATEGORY_FETCHERS.get(category)
    if not fn:
        return []
    return fn()[:limit]


def stuck_dashboard_counts_fast():
    from enquiries.models import Enquiry
    from quotations.models import Quotation
    from orders.models import Order
    from scheduling.models import WorkSchedule
    from wcr.models import WorkCompletionReport
    from billing.models import Invoice

    cfg = get_case_settings()
    today = timezone.localdate()
    now = timezone.now()
    survey_cutoff = today - timedelta(days=cfg.survey_delay_days)
    q_cutoff = now - timedelta(days=cfg.quotation_followup_days)
    o_cutoff = now - timedelta(days=cfg.order_delay_days)
    w_cutoff = now - timedelta(days=cfg.wcr_delay_days)
    inv_cutoff = now - timedelta(days=cfg.invoice_approval_days)
    pay_cutoff = today - timedelta(days=cfg.payment_followup_days)
    inactive_cutoff = now - timedelta(days=cfg.enquiry_delay_days)

    has_schedule = WorkSchedule.objects.filter(order_id=OuterRef('pk'))
    has_wcr = WorkCompletionReport.objects.filter(order_id=OuterRef('pk'))

    pending_enquiries = Enquiry.objects.exclude(
        status__in=('CONVERTED_TO_ORDER', 'WON', 'LOST', 'CLOSED'),
    ).count()
    delayed_surveys = Enquiry.objects.filter(
        status='SURVEY_SCHEDULED', survey_date__lte=survey_cutoff,
    ).count()
    quotation_followup = Quotation.objects.filter(
        status__in=('SENT', 'UNDER_REVIEW'), updated_at__lt=q_cutoff,
    ).count()
    delayed_orders = Order.objects.filter(
        status__in=('NEW', 'ASSIGNED'), created_date__lt=o_cutoff,
    ).annotate(_s=Exists(has_schedule)).filter(_s=False).count()
    pending_wcr = Order.objects.filter(
        status='COMPLETED', created_date__lt=w_cutoff,
    ).annotate(_w=Exists(has_wcr)).filter(_w=False).count()
    invoice_approval = Invoice.objects.filter(
        approval_status='SUBMITTED',
    ).filter(Q(submitted_at__lt=inv_cutoff) | Q(submitted_at__isnull=True)).count()
    pending_payments = Invoice.objects.filter(
        payment_status='PENDING', approval_status='APPROVED', due_date__lte=pay_cutoff,
    ).count()
    inactive_enquiries = Enquiry.objects.exclude(
        status__in=('CONVERTED_TO_ORDER', 'WON', 'LOST', 'CLOSED'),
    ).filter(updated_at__lt=inactive_cutoff).count()

    stuck_total = (
        inactive_enquiries + delayed_surveys + quotation_followup + delayed_orders
        + pending_wcr + invoice_approval + pending_payments
    )

    return {
        'pending_enquiries': pending_enquiries,
        'delayed_surveys': delayed_surveys,
        'quotation_followup': quotation_followup,
        'delayed_orders': delayed_orders,
        'pending_wcr': pending_wcr,
        'pending_invoice_approval': invoice_approval,
        'pending_payments': pending_payments,
        'stuck_total': stuck_total,
    }


def director_monitoring_summary():
    from enquiries.models import Enquiry
    from quotations.models import Quotation
    from orders.models import Order

    counts = stuck_dashboard_counts_fast()
    total_open = (
        Enquiry.objects.exclude(status__in=('CONVERTED_TO_ORDER', 'WON', 'LOST', 'CLOSED')).count()
        + Quotation.objects.exclude(status__in=('APPROVED', 'REJECTED', 'CONVERTED')).count()
        + Order.objects.exclude(status='CLOSED').count()
    )
    return {
        'total_open_cases': total_open,
        'cases_awaiting_action': counts['stuck_total'],
        'stuck_cases': counts['stuck_total'],
        'overdue_cases': counts['pending_payments'] + counts['delayed_surveys'] + counts['delayed_orders'],
        'counts': counts,
    }


def operations_monitoring_summary():
    from enquiries.models import Enquiry

    counts = stuck_dashboard_counts_fast()
    pending_surveys = Enquiry.objects.filter(status='SURVEY_SCHEDULED').count()
    return {
        'pending_surveys': pending_surveys,
        'pending_quotations': counts['quotation_followup'],
        'pending_orders': counts['delayed_orders'],
        'pending_wcr': counts['pending_wcr'],
        'delayed_cases': counts['stuck_total'],
        'counts': counts,
    }


def category_label(category):
    return CATEGORY_LABELS.get(category, category)
