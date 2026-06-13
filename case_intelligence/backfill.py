"""Historical timeline backfill — idempotent via backfill_key."""

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from accounts.roles import user_role
from case_intelligence.constants import (
    MOD_ENQUIRY,
    MOD_ESTIMATE_BOQ,
    MOD_INVOICE,
    MOD_ORDER,
    MOD_PAYMENT,
    MOD_QUOTATION,
    MOD_SCHEDULE,
    MOD_WCR,
)
from case_intelligence.models import CaseActivityLog


def _user_display(user):
    if not user:
        return ''
    return user_role(user)


def ensure_backfill_event(
    backfill_key,
    *,
    module,
    document_type,
    document_number,
    description,
    activity_at=None,
    user=None,
    previous_status='',
    new_status='',
    remarks='',
    client=None,
    content_object=None,
):
    """Create a timeline entry once. Returns 'created', 'skipped', or 'error'."""
    if not document_number or not backfill_key:
        return 'error'
    if CaseActivityLog.objects.filter(backfill_key=backfill_key).exists():
        return 'skipped'
    ct = None
    oid = None
    if content_object is not None:
        ct = ContentType.objects.get_for_model(content_object)
        oid = content_object.pk
    when = activity_at or timezone.now()
    CaseActivityLog.objects.create(
        backfill_key=backfill_key,
        activity_at=when,
        module=module,
        document_type=document_type,
        document_number=str(document_number)[:60],
        description=description[:200],
        previous_status=(previous_status or '')[:50],
        new_status=(new_status or '')[:50],
        user=user if user and getattr(user, 'pk', None) else None,
        user_role=_user_display(user),
        remarks=remarks,
        client=client,
        content_type=ct,
        object_id=oid,
    )
    return 'created'


def backfill_enquiries(stdout_write):
    from enquiries.models import Enquiry

    created = skipped = 0
    qs = Enquiry.objects.select_related(
        'client', 'created_by', 'survey_engineer',
        'assigned_project_manager', 'converted_order',
    )
    for e in qs.iterator(chunk_size=200):
        r = ensure_backfill_event(
            f'enquiry:{e.pk}:created',
            module=MOD_ENQUIRY,
            document_type='Enquiry',
            document_number=e.enquiry_number,
            description='Enquiry Created',
            activity_at=e.created_at,
            user=e.created_by,
            new_status=e.status,
            client=e.client,
            content_object=e,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1

        if e.status != 'NEW':
            r = ensure_backfill_event(
                f'enquiry:{e.pk}:status:{e.status}',
                module=MOD_ENQUIRY,
                document_type='Enquiry',
                document_number=e.enquiry_number,
                description=f'Enquiry {e.get_status_display()}',
                activity_at=e.updated_at,
                new_status=e.status,
                client=e.client,
                content_object=e,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

        if e.survey_engineer_id:
            r = ensure_backfill_event(
                f'enquiry:{e.pk}:survey_assigned',
                module=MOD_ENQUIRY,
                document_type='Enquiry',
                document_number=e.enquiry_number,
                description='Survey Assigned',
                activity_at=e.updated_at,
                user=e.assigned_project_manager or e.created_by,
                new_status='SURVEY_SCHEDULED',
                client=e.client,
                content_object=e,
                remarks=str(e.survey_engineer),
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

        if e.converted_order_id:
            r = ensure_backfill_event(
                f'enquiry:{e.pk}:converted',
                module=MOD_ENQUIRY,
                document_type='Enquiry',
                document_number=e.enquiry_number,
                description='Converted To Order',
                activity_at=e.updated_at,
                new_status=e.status,
                client=e.client,
                content_object=e,
                remarks=e.converted_order.order_no,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Enquiries: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_estimate_boqs(stdout_write):
    from estimate_boq.models import EstimateBOQ

    created = skipped = 0
    qs = EstimateBOQ.objects.select_related('enquiry', 'enquiry__client', 'created_by')
    for eb in qs.iterator(chunk_size=200):
        r = ensure_backfill_event(
            f'estimate_boq:{eb.pk}:created',
            module=MOD_ESTIMATE_BOQ,
            document_type='Estimate BOQ',
            document_number=eb.estimate_boq_number,
            description='Estimate BOQ Created',
            activity_at=eb.created_at,
            user=eb.created_by,
            new_status=eb.status,
            client=eb.enquiry.client if eb.enquiry_id else None,
            content_object=eb,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1
        if eb.status == 'FINALIZED':
            r = ensure_backfill_event(
                f'estimate_boq:{eb.pk}:finalized',
                module=MOD_ESTIMATE_BOQ,
                document_type='Estimate BOQ',
                document_number=eb.estimate_boq_number,
                description='Estimate BOQ Finalized',
                activity_at=eb.updated_at,
                new_status=eb.status,
                client=eb.enquiry.client if eb.enquiry_id else None,
                content_object=eb,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Estimate BOQ: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_quotations(stdout_write):
    from quotations.models import Quotation

    created = skipped = 0
    qs = Quotation.objects.select_related('client', 'created_by', 'approved_by', 'enquiry')
    for q in qs.iterator(chunk_size=200):
        r = ensure_backfill_event(
            f'quotation:{q.pk}:created',
            module=MOD_QUOTATION,
            document_type='Quotation',
            document_number=q.quotation_number,
            description='Quotation Generated',
            activity_at=q.created_at,
            user=q.created_by,
            new_status=q.status,
            client=q.client,
            content_object=q,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1

        if q.status in ('SENT', 'UNDER_REVIEW'):
            r = ensure_backfill_event(
                f'quotation:{q.pk}:submitted',
                module=MOD_QUOTATION,
                document_type='Quotation',
                document_number=q.quotation_number,
                description='Quotation Submitted',
                activity_at=q.updated_at,
                user=q.created_by,
                new_status=q.status,
                client=q.client,
                content_object=q,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

        if q.approved_by_id or q.status in ('APPROVED', 'ACCEPTED'):
            r = ensure_backfill_event(
                f'quotation:{q.pk}:approved',
                module=MOD_QUOTATION,
                document_type='Quotation',
                document_number=q.quotation_number,
                description='Quotation Approved',
                activity_at=q.updated_at,
                user=q.approved_by or q.created_by,
                new_status=q.status,
                client=q.client,
                content_object=q,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

        if q.status == 'CONVERTED' and q.converted_order_id:
            r = ensure_backfill_event(
                f'quotation:{q.pk}:converted',
                module=MOD_QUOTATION,
                document_type='Quotation',
                document_number=q.quotation_number,
                description='Converted To Order',
                activity_at=q.updated_at,
                new_status=q.status,
                client=q.client,
                content_object=q,
                remarks=q.converted_order.order_no,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Quotations: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_orders(stdout_write):
    from orders.models import Order

    created = skipped = 0
    qs = Order.objects.select_related('client', 'assigned_to')
    for o in qs.iterator(chunk_size=200):
        doc = o.order_no or str(o.order_id)
        r = ensure_backfill_event(
            f'order:{o.pk}:created',
            module=MOD_ORDER,
            document_type='Order',
            document_number=doc,
            description='Order Created',
            activity_at=o.created_date,
            new_status=o.status,
            client=o.client,
            content_object=o,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1
        if o.status != 'NEW':
            r = ensure_backfill_event(
                f'order:{o.pk}:status:{o.status}',
                module=MOD_ORDER,
                document_type='Order',
                document_number=doc,
                description=f'Order {o.get_status_display()}',
                activity_at=o.created_date,
                new_status=o.status,
                client=o.client,
                content_object=o,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Orders: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_schedules(stdout_write):
    from scheduling.models import WorkSchedule

    created = skipped = 0
    qs = WorkSchedule.objects.select_related(
        'order', 'order__client', 'enquiry', 'enquiry__client',
        'lead_engineer', 'created_by',
    )
    for s in qs.iterator(chunk_size=200):
        client = None
        if s.order_id:
            client = s.order.client
        elif s.enquiry_id:
            client = s.enquiry.client
        r = ensure_backfill_event(
            f'schedule:{s.pk}:created',
            module=MOD_SCHEDULE,
            document_type='Schedule',
            document_number=s.schedule_number,
            description='Schedule Created',
            activity_at=s.created_at,
            user=s.created_by,
            new_status=s.status,
            client=client,
            content_object=s,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1
        if s.status == 'IN_PROGRESS':
            r = ensure_backfill_event(
                f'schedule:{s.pk}:work_started',
                module=MOD_SCHEDULE,
                document_type='Schedule',
                document_number=s.schedule_number,
                description='Work Started',
                activity_at=s.updated_at,
                user=s.lead_engineer,
                new_status=s.status,
                client=client,
                content_object=s,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1
        if s.status == 'COMPLETED':
            r = ensure_backfill_event(
                f'schedule:{s.pk}:completed',
                module=MOD_SCHEDULE,
                document_type='Schedule',
                document_number=s.schedule_number,
                description='Schedule Completed',
                activity_at=s.updated_at,
                user=s.lead_engineer,
                new_status=s.status,
                client=client,
                content_object=s,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Schedules: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_wcrs(stdout_write):
    from wcr.models import WorkCompletionReport

    created = skipped = 0
    qs = WorkCompletionReport.objects.select_related(
        'order', 'order__client', 'enquiry', 'enquiry__client', 'submitted_by',
    )
    for w in qs.iterator(chunk_size=200):
        client = None
        if w.enquiry_id:
            client = w.enquiry.client
        elif w.order_id:
            client = w.order.client
        r = ensure_backfill_event(
            f'wcr:{w.pk}:submitted',
            module=MOD_WCR,
            document_type='WCR',
            document_number=w.wcr_number,
            description='WCR Submitted',
            activity_at=w.submitted_date,
            user=w.submitted_by,
            new_status='SUBMITTED',
            client=client,
            content_object=w,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1
        if w.approved:
            r = ensure_backfill_event(
                f'wcr:{w.pk}:approved',
                module=MOD_WCR,
                document_type='WCR',
                document_number=w.wcr_number,
                description='WCR Approved',
                activity_at=w.submitted_date,
                user=w.submitted_by,
                new_status='APPROVED',
                client=client,
                content_object=w,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  WCR: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_invoices(stdout_write):
    from billing.models import Invoice, InvoiceApprovalAuditLog

    created = skipped = 0
    qs = Invoice.objects.select_related('order', 'order__client', 'created_by', 'approved_by')
    for inv in qs.iterator(chunk_size=200):
        client = inv.order.client
        from datetime import datetime
        created_when = inv.submitted_at
        if not created_when and inv.invoice_date:
            created_when = timezone.make_aware(
                datetime.combine(inv.invoice_date, datetime.min.time()),
            )
        r = ensure_backfill_event(
            f'invoice:{inv.pk}:created',
            module=MOD_INVOICE,
            document_type='Invoice',
            document_number=inv.invoice_number,
            description='Invoice Generated',
            activity_at=created_when or timezone.now(),
            user=inv.created_by,
            new_status=inv.approval_status,
            client=client,
            content_object=inv,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1

        for audit in InvoiceApprovalAuditLog.objects.filter(invoice=inv).order_by('created_at'):
            r = ensure_backfill_event(
                f'invoice:{inv.pk}:audit:{audit.pk}',
                module=MOD_INVOICE,
                document_type='Invoice',
                document_number=inv.invoice_number,
                description=f'Invoice {audit.get_action_display()}',
                activity_at=audit.created_at,
                user=audit.performed_by,
                previous_status=audit.previous_status,
                new_status=audit.new_status,
                client=client,
                content_object=inv,
                remarks=audit.remarks,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

        if inv.approved_at:
            r = ensure_backfill_event(
                f'invoice:{inv.pk}:approved',
                module=MOD_INVOICE,
                document_type='Invoice',
                document_number=inv.invoice_number,
                description='Invoice Approved',
                activity_at=inv.approved_at,
                user=inv.approved_by,
                new_status=inv.approval_status,
                client=client,
                content_object=inv,
            )
            if r == 'created':
                created += 1
            elif r == 'skipped':
                skipped += 1

    stdout_write(f'  Invoices: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def backfill_payments(stdout_write):
    from billing.models import Invoice

    created = skipped = 0
    qs = Invoice.objects.filter(payment_status='RECEIVED').select_related('order', 'order__client')
    for inv in qs.iterator(chunk_size=200):
        r = ensure_backfill_event(
            f'payment:{inv.pk}:received',
            module=MOD_PAYMENT,
            document_type='Payment',
            document_number=inv.invoice_number,
            description='Payment Received',
            activity_at=inv.approved_at or timezone.now(),
            new_status='RECEIVED',
            client=inv.order.client,
            content_object=inv,
        )
        if r == 'created':
            created += 1
        elif r == 'skipped':
            skipped += 1

    stdout_write(f'  Payments: {qs.count()} records — {created} events created, {skipped} skipped')
    return qs.count(), created, skipped


def run_full_backfill(stdout_write=print):
    """Run all backfill steps. Returns summary dict."""
    stdout_write('Starting case timeline backfill…')
    summary = {}
    steps = (
        ('enquiries', backfill_enquiries),
        ('estimate_boqs', backfill_estimate_boqs),
        ('quotations', backfill_quotations),
        ('orders', backfill_orders),
        ('schedules', backfill_schedules),
        ('wcrs', backfill_wcrs),
        ('invoices', backfill_invoices),
        ('payments', backfill_payments),
    )
    total_created = total_skipped = 0
    for key, fn in steps:
        count, created, skipped = fn(stdout_write)
        summary[key] = {'processed': count, 'created': created, 'skipped': skipped}
        total_created += created
        total_skipped += skipped
    summary['total_created'] = total_created
    summary['total_skipped'] = total_skipped
    stdout_write('')
    stdout_write(f'Processed Enquiries: {summary["enquiries"]["processed"]}')
    stdout_write(f'Processed Quotations: {summary["quotations"]["processed"]}')
    stdout_write(f'Processed Orders: {summary["orders"]["processed"]}')
    stdout_write(f'Processed Invoices: {summary["invoices"]["processed"]}')
    stdout_write(f'Events created: {total_created} | Skipped (already exist): {total_skipped}')
    stdout_write('Backfill Completed Successfully')
    return summary
