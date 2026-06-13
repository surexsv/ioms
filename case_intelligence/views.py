import csv

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.decorators import access_denied_response, module_required
from case_intelligence.constants import HEALTH_LABELS
from case_intelligence.models import CaseActivityLog
from case_intelligence.permissions import (
    MODULE_CASE_INTELLIGENCE,
    can_export_case_reports,
    can_view_case_intelligence,
)
from case_intelligence.services import (
    detect_stuck_cases,
    global_search,
    resolve_case_tracker,
    stuck_dashboard_counts,
)
from case_intelligence.stuck_cases import category_label, get_cases_by_category
from case_intelligence.categories import (
    CAT_DELAYED_ORDERS,
    CAT_DELAYED_SURVEYS,
    CAT_INVOICE_APPROVAL,
    CAT_PENDING_ENQUIRIES,
    CAT_PENDING_PAYMENTS,
    CAT_PENDING_WCR,
    CAT_QUOTATION_FOLLOWUP,
    CAT_STUCK_TOTAL,
)


@module_required(MODULE_CASE_INTELLIGENCE)
def case_search(request):
    if not can_view_case_intelligence(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    q = request.GET.get('q', '').strip()
    results = global_search(q, request.user) if q else []
    return render(request, 'case_intelligence/search.html', {
        'query': q,
        'results': results,
    })


@require_GET
@module_required(MODULE_CASE_INTELLIGENCE)
def case_search_api(request):
    if not can_view_case_intelligence(request.user):
        return JsonResponse({'results': []}, status=403)
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    results = global_search(q, request.user, limit=15)
    return JsonResponse({'results': [
        {
            'document_type': r['document_type'],
            'document_number': r['document_number'],
            'client': r['client'],
            'status': r['status'],
            'stage': r['stage'],
            'url_name': r['url_name'],
            'url_pk': r['url_pk'],
        }
        for r in results
    ]})


@module_required(MODULE_CASE_INTELLIGENCE)
def case_tracker(request):
    if not can_view_case_intelligence(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    doc = request.GET.get('doc', '').strip()
    ctx = resolve_case_tracker(doc) if doc else None
    if doc and not ctx:
        messages.warning(request, f'No case found for document number: {doc}')
    return render(request, 'case_intelligence/tracker.html', {
        'document_number': doc,
        'tracker': ctx,
        'health_labels': HEALTH_LABELS,
    })


@module_required(MODULE_CASE_INTELLIGENCE)
def stuck_dashboard(request):
    if not can_view_case_intelligence(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    counts, _ = stuck_dashboard_counts()
    category = request.GET.get('category', '')
    case_list = []
    category_title = ''
    if category:
        case_list = get_cases_by_category(category, limit=200)
        category_title = category_label(category)
    return render(request, 'case_intelligence/stuck_dashboard.html', {
        'counts': counts,
        'case_list': case_list,
        'category': category,
        'category_title': category_title,
    })


@module_required(MODULE_CASE_INTELLIGENCE)
def activity_log(request):
    if not can_view_case_intelligence(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    module_filter = request.GET.get('module', '')
    qs = CaseActivityLog.objects.select_related('user', 'client').order_by('-activity_at')
    if module_filter:
        qs = qs.filter(module=module_filter)
    return render(request, 'case_intelligence/activity_log.html', {
        'activities': qs[:300],
        'module_filter': module_filter,
    })


@module_required(MODULE_CASE_INTELLIGENCE)
def reports(request):
    if not can_view_case_intelligence(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    report = request.GET.get('report', 'stuck')
    stuck = detect_stuck_cases() if report in ('stuck', 'conversion', 'delay') else []
    conversion_rows = []
    if report == 'enquiry_conversion':
        from enquiries.models import Enquiry
        total = Enquiry.objects.count()
        converted = Enquiry.objects.filter(status='CONVERTED_TO_ORDER').count()
        conversion_rows = [{'label': 'Enquiry → Order', 'total': total, 'converted': converted}]
    if report == 'quotation_conversion':
        from quotations.models import Quotation
        total = Quotation.objects.count()
        converted = Quotation.objects.filter(status='CONVERTED').count()
        conversion_rows = [{'label': 'Quotation → Order', 'total': total, 'converted': converted}]
    return render(request, 'case_intelligence/reports.html', {
        'report': report,
        'stuck_cases': stuck,
        'conversion_rows': conversion_rows,
        'can_export': can_export_case_reports(request.user),
    })


@module_required(MODULE_CASE_INTELLIGENCE)
def export_stuck_csv(request):
    if not can_export_case_reports(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    stuck = detect_stuck_cases()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stuck_cases.csv"'
    writer = csv.writer(response)
    writer.writerow(['Document Number', 'Type', 'Client', 'Flag', 'Detail'])
    for row in stuck:
        writer.writerow([row['document_number'], row['document_type'], row['client'], row['flag'], row['detail']])
    return response


@module_required(MODULE_CASE_INTELLIGENCE)
def export_aging_csv(request):
    if not can_export_case_reports(request.user):
        return access_denied_response(request, module_key='case_intelligence')
    from enquiries.models import Enquiry
    from django.utils import timezone
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="case_aging.csv"'
    writer = csv.writer(response)
    writer.writerow(['Document', 'Type', 'Client', 'Status', 'Age Days'])
    today = timezone.localdate()
    for e in Enquiry.objects.exclude(status__in=('CLOSED', 'LOST', 'CONVERTED_TO_ORDER')).select_related('client'):
        age = (today - e.enquiry_date).days
        writer.writerow([e.enquiry_number, 'Enquiry', e.client.name, e.status, age])
    return response
