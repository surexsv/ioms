"""Case intelligence engine — timeline, summary, search, stuck detection, health."""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum
from django.utils import timezone

from case_intelligence.constants import (
    HEALTH_GREEN,
    HEALTH_LABELS,
    HEALTH_RED,
    HEALTH_YELLOW,
    MOD_ENQUIRY,
    MOD_INVOICE,
    MOD_ORDER,
    MOD_PAYMENT,
    MOD_QUOTATION,
    MOD_SCHEDULE,
    MOD_WCR,
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


def get_timeline(content_object, limit=50):
    if not content_object:
        return CaseActivityLog.objects.none()
    ct = ContentType.objects.get_for_model(content_object)
    return CaseActivityLog.objects.filter(
        content_type=ct,
        object_id=content_object.pk,
    ).select_related('user', 'client').order_by('-activity_at')[:limit]


def get_timeline_by_number(document_number, limit=50):
    return CaseActivityLog.objects.filter(
        document_number=document_number,
    ).select_related('user', 'client').order_by('-activity_at')[:limit]


def _days_since(dt):
    if not dt:
        return None
    return (timezone.now() - dt).days


def get_case_summary(content_object, *, module, document_number, status='', stage='',
                     assigned_to='', pending_action='', next_action=''):
    timeline = get_timeline(content_object, limit=1)
    last = timeline.first() if content_object else None
    if not last and document_number:
        last = CaseActivityLog.objects.filter(document_number=document_number).order_by('-activity_at').first()
    created = None
    if content_object and hasattr(content_object, 'created_at'):
        created = content_object.created_at
    elif content_object and hasattr(content_object, 'enquiry_date'):
        from datetime import datetime
        created = timezone.make_aware(datetime.combine(content_object.enquiry_date, datetime.min.time()))
    age_days = _days_since(created) if created else None
    last_activity_days = _days_since(last.activity_at) if last else None
    return {
        'current_status': status,
        'current_stage': stage or status,
        'assigned_person': assigned_to,
        'last_updated': last.activity_at if last else created,
        'pending_action': pending_action,
        'next_action': next_action,
        'case_age_days': age_days,
        'days_since_last_activity': last_activity_days,
        'document_number': document_number,
        'module': module,
    }


def health_from_days(days, yellow_at=3, red_at=7):
    if days is None:
        return HEALTH_GREEN
    if days >= red_at:
        return HEALTH_RED
    if days >= yellow_at:
        return HEALTH_YELLOW
    return HEALTH_GREEN


def get_health(content_object, document_number='', stuck_flag=None, days_inactive=None):
    if stuck_flag:
        return HEALTH_RED
    if days_inactive is not None:
        return health_from_days(days_inactive)
    if content_object:
        last = get_timeline(content_object, limit=1).first()
        if last:
            return health_from_days(_days_since(last.activity_at))
    if document_number:
        last = CaseActivityLog.objects.filter(document_number=document_number).order_by('-activity_at').first()
        if last:
            return health_from_days(_days_since(last.activity_at))
    return HEALTH_GREEN


def global_search(query, user, limit=25):
    """Universal search across document numbers, clients, contacts, locations."""
    from case_intelligence.permissions import (
        can_view_all_cases,
        can_view_financial_cases,
        can_view_operational_cases,
        is_back_office,
        is_field_role,
    )
    if not query or len(query.strip()) < 2:
        return []
    q = query.strip()
    results = []
    cfg = get_case_settings()
    today = timezone.localdate()

    def add(doc_type, doc_number, client_name, status, stage, assigned, url_name, url_pk, module):
        results.append({
            'document_type': doc_type,
            'document_number': doc_number,
            'client': client_name,
            'status': status,
            'stage': stage,
            'assigned': assigned,
            'last_activity': _last_activity_label(doc_number),
            'url_name': url_name,
            'url_pk': url_pk,
            'module': module,
            'health': get_health(None, doc_number),
        })

    # Enquiries
    if can_view_all_cases(user) or can_view_operational_cases(user) or is_back_office(user):
        from enquiries.models import Enquiry
        eqs = Enquiry.objects.select_related('client', 'assigned_project_manager', 'survey_engineer').filter(
            Q(enquiry_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(contact_person__icontains=q)
            | Q(mobile__icontains=q)
            | Q(location__icontains=q)
        )
        if is_field_role(user):
            eqs = eqs.filter(survey_engineer=user)
        for e in eqs[:limit]:
            add('Enquiry', e.enquiry_number, e.client.name, e.get_status_display(),
                e.get_status_display(), _user_name(e.survey_engineer or e.assigned_to),
                'enquiry_detail', e.pk, MOD_ENQUIRY)

    # Quotations
    if can_view_all_cases(user) or can_view_operational_cases(user):
        from quotations.models import Quotation
        qs = Quotation.objects.select_related('client', 'enquiry').filter(
            Q(quotation_number__icontains=q) | Q(client__name__icontains=q)
        )[:limit]
        for qt in qs:
            add('Quotation', qt.quotation_number, qt.client.name, qt.get_status_display(),
                qt.get_status_display(), '', 'quotation_detail', qt.pk, MOD_QUOTATION)

    # Orders
    from orders.models import Order
    oq = Order.objects.select_related('client', 'assigned_to').filter(
        Q(order_no__icontains=q) | Q(client__name__icontains=q)
    )
    if is_field_role(user):
        oq = oq.filter(assigned_to=user)
    for o in oq[:limit]:
        add('Order', o.order_no or str(o.order_id), o.client.name, o.get_status_display(),
            o.get_status_display(), _user_name(o.assigned_to), 'order_detail', o.pk, MOD_ORDER)

    # Schedules
    from scheduling.engine import schedules_for_user
    for s in schedules_for_user(user).filter(
        Q(schedule_number__icontains=q) | Q(reference_number__icontains=q)
    )[:limit]:
        client = ''
        if s.order_id:
            client = s.order.client.name
        elif s.enquiry_id:
            client = s.enquiry.client.name
        add('Schedule', s.schedule_number, client, s.get_status_display(),
            s.get_schedule_category_display(), _user_name(s.lead_engineer),
            'schedule_edit', s.pk, MOD_SCHEDULE)

    # WCR
    from wcr.models import WorkCompletionReport
    wq = WorkCompletionReport.objects.select_related('order', 'order__client', 'enquiry', 'enquiry__client', 'submitted_by')
    if is_field_role(user):
        wq = wq.filter(submitted_by=user)
    wq = wq.filter(Q(wcr_number__icontains=q))[:limit]
    for w in wq:
        if w.enquiry_id:
            add('Survey WCR', w.wcr_number, w.enquiry.client.name,
                'Approved' if w.approved else 'Pending', 'Survey WCR',
                _user_name(w.submitted_by), 'wcr_list', None, MOD_WCR)
        else:
            add('WCR', w.wcr_number, w.order.client.name if w.order_id else '',
                'Approved' if w.approved else 'Pending', 'Execution WCR',
                _user_name(w.submitted_by), 'wcr_list', None, MOD_WCR)

    # Invoices / payments
    if can_view_all_cases(user) or can_view_financial_cases(user):
        from billing.models import Invoice
        iq = Invoice.objects.select_related('order', 'order__client', 'client').filter(
            Q(invoice_number__icontains=q) | Q(order__client__name__icontains=q) | Q(client__name__icontains=q)
        )[:limit]
        for inv in iq:
            client_name = inv.billing_client.name if inv.billing_client else ''
            add('Invoice', inv.invoice_number, client_name,
                inv.get_approval_status_display(), inv.payment_status,
                '', 'invoice_detail', inv.pk, MOD_INVOICE)

    # Deduplicate by document_number
    seen = set()
    unique = []
    for r in results:
        key = (r['document_type'], r['document_number'])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:limit]


def _last_activity_label(document_number):
    last = CaseActivityLog.objects.filter(document_number=document_number).order_by('-activity_at').first()
    if last:
        return last.description
    return '—'


def _user_name(user):
    if not user:
        return '—'
    return user.get_full_name() or user.username


def resolve_case_tracker(document_number):
    """Resolve any document number to tracker context."""
    from enquiries.models import Enquiry
    from quotations.models import Quotation
    from orders.models import Order
    from scheduling.models import WorkSchedule
    from wcr.models import WorkCompletionReport
    from billing.models import Invoice

    doc = document_number.strip()
    for model, field, mod, dtype in (
        (Enquiry, 'enquiry_number', MOD_ENQUIRY, 'Enquiry'),
        (Quotation, 'quotation_number', MOD_QUOTATION, 'Quotation'),
        (Order, 'order_no', MOD_ORDER, 'Order'),
        (WorkSchedule, 'schedule_number', MOD_SCHEDULE, 'Schedule'),
        (WorkCompletionReport, 'wcr_number', MOD_WCR, 'WCR'),
        (Invoice, 'invoice_number', MOD_INVOICE, 'Invoice'),
    ):
        obj = model.objects.filter(**{field: doc}).first()
        if not obj and model is Order:
            obj = Order.objects.filter(order_id=doc).first() if doc.isdigit() else None
        if obj:
            return build_tracker_context(obj, mod, dtype, doc)
    return None


def build_tracker_context(obj, module, document_type, document_number):
    timeline = list(get_timeline(obj, limit=30))
    summary = _summary_for_object(obj, module, document_number)
    stuck = _stuck_for_object(obj, module)
    health = HEALTH_RED if stuck else get_health(obj, document_number)
    return {
        'object': obj,
        'module': module,
        'document_type': document_type,
        'document_number': document_number,
        'timeline': timeline,
        'summary': summary,
        'stuck_flag': stuck,
        'health': health,
        'health_label': HEALTH_LABELS.get(health, 'On Track'),
    }


def _summary_for_object(obj, module, document_number):
    if module == MOD_ENQUIRY:
        return get_case_summary(
            obj, module=module, document_number=document_number,
            status=obj.get_status_display(), stage=obj.get_status_display(),
            assigned_to=_user_name(obj.survey_engineer or obj.assigned_project_manager),
            pending_action=_pending_for_enquiry(obj),
            next_action=_next_for_enquiry(obj),
        )
    if module == MOD_ORDER:
        return get_case_summary(
            obj, module=module, document_number=document_number,
            status=obj.get_status_display(), stage=obj.get_status_display(),
            assigned_to=_user_name(obj.assigned_to),
            pending_action='Schedule / WCR / Invoice' if obj.status != 'CLOSED' else '—',
            next_action='Field execution' if obj.status in ('NEW', 'IN_PROGRESS') else '—',
        )
    if module == MOD_QUOTATION:
        return get_case_summary(
            obj, module=module, document_number=document_number,
            status=obj.get_status_display(), stage=obj.get_status_display(),
            pending_action='Client approval' if obj.status == 'SUBMITTED' else '—',
            next_action='Convert to order' if obj.status == 'APPROVED' else '—',
        )
    if module == MOD_INVOICE:
        return get_case_summary(
            obj, module=module, document_number=document_number,
            status=obj.get_approval_status_display(),
            stage=obj.payment_status,
            pending_action='Approval' if obj.approval_status == 'SUBMITTED' else (
                'Payment' if obj.payment_status == 'PENDING' else '—'
            ),
            next_action='Accounts action',
        )
    return get_case_summary(obj, module=module, document_number=document_number, status=str(obj))


def _pending_for_enquiry(enquiry):
    if enquiry.status in ('NEW', 'ASSIGNED'):
        return 'Survey assignment'
    if enquiry.status == 'SURVEY_SCHEDULED':
        return 'Survey completion'
    if enquiry.status == 'QUOTATION_SUBMITTED':
        return 'Client approval'
    return '—'


def _next_for_enquiry(enquiry):
    if enquiry.status == 'SURVEY_COMPLETED':
        return 'Estimate BOQ / Quotation'
    if enquiry.status == 'QUOTATION_SUBMITTED':
        return 'Client decision'
    return '—'


def detect_stuck_cases():
    """Return basic stuck rows for reports (backward compatible)."""
    from case_intelligence.categories import CAT_STUCK_TOTAL
    from case_intelligence.stuck_cases import get_cases_by_category
    return [
        {
            'document_number': r['document_number'],
            'document_type': r['document_type'],
            'client': r['client'],
            'flag': r['flag'],
            'detail': r.get('status', r.get('next_action', '')),
        }
        for r in get_cases_by_category(CAT_STUCK_TOTAL, limit=500)
    ]


def _stuck_row(doc_number, doc_type, client, flag, detail):
    return {
        'document_number': doc_number,
        'document_type': doc_type,
        'client': client,
        'flag': flag,
        'detail': detail,
    }


def _stuck_for_object(obj, module):
    for row in detect_stuck_cases():
        if row['document_number'] == _doc_number(obj, module):
            return row['flag']
    return None


def _doc_number(obj, module):
    if module == MOD_ENQUIRY:
        return obj.enquiry_number
    if module == MOD_ORDER:
        return obj.order_no or str(obj.order_id)
    if module == MOD_QUOTATION:
        return obj.quotation_number
    if module == MOD_INVOICE:
        return obj.invoice_number
    if module == MOD_SCHEDULE:
        return obj.schedule_number
    if module == MOD_WCR:
        return obj.wcr_number
    return ''


def stuck_dashboard_counts():
    from case_intelligence.stuck_cases import stuck_dashboard_counts_fast
    counts = stuck_dashboard_counts_fast()
    stuck = detect_stuck_cases()
    counts['quotation_followup'] = counts.get('quotation_followup', 0)
    return counts, stuck


def client_case_history(client):
    from enquiries.models import Enquiry
    from quotations.models import Quotation
    from orders.models import Order
    from billing.models import Invoice

    enquiries = Enquiry.objects.filter(client=client).count()
    quotations = Quotation.objects.filter(client=client).count()
    orders = Order.objects.filter(client=client).count()
    invoices = Invoice.objects.filter(Q(client=client) | Q(order__client=client)).count()
    payments = Invoice.objects.filter(
        Q(client=client) | Q(order__client=client),
        payment_status='RECEIVED',
    ).count()
    outstanding = Invoice.objects.filter(
        Q(client=client) | Q(order__client=client),
        payment_status='PENDING',
        approval_status='APPROVED',
    ).aggregate(t=Sum('total'))['t'] or 0
    activities = CaseActivityLog.objects.filter(client=client).select_related('user').order_by('-activity_at')[:20]
    timeline = list(activities)
    return {
        'total_enquiries': enquiries,
        'total_quotations': quotations,
        'total_orders': orders,
        'total_invoices': invoices,
        'total_payments': payments,
        'outstanding_amount': outstanding,
        'recent_activities': timeline,
    }


def panel_context(content_object, *, module, document_number, **summary_kw):
    """Context dict for detail page includes."""
    stuck = _stuck_for_object(content_object, module) if content_object else None
    return {
        'case_timeline': get_timeline(content_object, limit=25),
        'case_summary': get_case_summary(
            content_object,
            module=module,
            document_number=document_number,
            **summary_kw,
        ),
        'case_health': HEALTH_RED if stuck else get_health(content_object, document_number),
        'case_health_label': HEALTH_LABELS.get(
            HEALTH_RED if stuck else get_health(content_object, document_number),
            'On Track',
        ),
        'case_stuck_flag': stuck,
        'show_case_tracker_link': True,
    }
