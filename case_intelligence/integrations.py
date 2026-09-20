"""Integration helpers — call from module views alongside existing log_activity."""

from case_intelligence.constants import (
    MOD_BOQ,
    MOD_ENQUIRY,
    MOD_ESTIMATE_BOQ,
    MOD_INVOICE,
    MOD_ORDER,
    MOD_PAYMENT,
    MOD_PM,
    MOD_QUOTATION,
    MOD_SCHEDULE,
    MOD_WCR,
)
from case_intelligence.logger import log_case_event


def enquiry_created(user, enquiry, remarks=''):
    log_case_event(
        user, module=MOD_ENQUIRY, document_type='Enquiry',
        document_number=enquiry.enquiry_number,
        description='Enquiry Created', new_status=enquiry.status,
        client=enquiry.client, content_object=enquiry, remarks=remarks,
    )


def enquiry_status_changed(user, enquiry, old_status, remarks=''):
    log_case_event(
        user, module=MOD_ENQUIRY, document_type='Enquiry',
        document_number=enquiry.enquiry_number,
        description=f'Enquiry {enquiry.get_status_display()}',
        previous_status=old_status, new_status=enquiry.status,
        client=enquiry.client, content_object=enquiry, remarks=remarks,
    )


def survey_assigned(user, enquiry, remarks=''):
    log_case_event(
        user, module=MOD_ENQUIRY, document_type='Enquiry',
        document_number=enquiry.enquiry_number,
        description='Survey Assigned', new_status=enquiry.status,
        client=enquiry.client, content_object=enquiry, remarks=remarks,
    )


def survey_completed(user, enquiry, remarks=''):
    log_case_event(
        user, module=MOD_ENQUIRY, document_type='Enquiry',
        document_number=enquiry.enquiry_number,
        description='Survey Completed', new_status=enquiry.status,
        client=enquiry.client, content_object=enquiry, remarks=remarks,
    )


def estimate_boq_created(user, eboq, remarks=''):
    enquiry = eboq.enquiry
    log_case_event(
        user, module=MOD_ESTIMATE_BOQ, document_type='Estimate BOQ',
        document_number=eboq.estimate_boq_number,
        description='Estimate BOQ Created', new_status=eboq.status,
        client=enquiry.client if enquiry else None,
        content_object=eboq, remarks=remarks,
    )


def quotation_created(user, quotation, remarks=''):
    log_case_event(
        user, module=MOD_QUOTATION, document_type='Quotation',
        document_number=quotation.quotation_number,
        description='Quotation Generated', new_status=quotation.status,
        client=quotation.client, content_object=quotation, remarks=remarks,
    )


def quotation_submitted(user, quotation, remarks=''):
    log_case_event(
        user, module=MOD_QUOTATION, document_type='Quotation',
        document_number=quotation.quotation_number,
        description='Quotation Submitted', new_status=quotation.status,
        client=quotation.client, content_object=quotation, remarks=remarks,
    )


def quotation_approved(user, quotation, remarks=''):
    log_case_event(
        user, module=MOD_QUOTATION, document_type='Quotation',
        document_number=quotation.quotation_number,
        description='Quotation Approved', new_status=quotation.status,
        client=quotation.client, content_object=quotation, remarks=remarks,
    )


def order_created(user, order, remarks=''):
    log_case_event(
        user, module=MOD_ORDER, document_type='Order',
        document_number=order.order_no or str(order.order_id),
        description='Order Created', new_status=order.status,
        client=order.client, content_object=order, remarks=remarks,
    )


def order_converted_from_enquiry(user, order, enquiry, remarks=''):
    log_case_event(
        user, module=MOD_ENQUIRY, document_type='Enquiry',
        document_number=enquiry.enquiry_number,
        description='Converted To Order', previous_status=enquiry.status,
        new_status=enquiry.status, client=enquiry.client,
        content_object=enquiry, remarks=remarks or order.order_no,
    )
    order_created(user, order, remarks=f'From {enquiry.enquiry_number}')


def schedule_created(user, schedule, remarks=''):
    client = None
    if schedule.order_id:
        client = schedule.order.client
    elif schedule.enquiry_id:
        client = schedule.enquiry.client
    log_case_event(
        user, module=MOD_SCHEDULE, document_type='Schedule',
        document_number=schedule.schedule_number,
        description='Schedule Created', new_status=schedule.status,
        client=client, content_object=schedule, remarks=remarks,
    )


def work_started(user, schedule, remarks=''):
    client = schedule.order.client if schedule.order_id else (
        schedule.enquiry.client if schedule.enquiry_id else None
    )
    log_case_event(
        user, module=MOD_SCHEDULE, document_type='Schedule',
        document_number=schedule.schedule_number,
        description='Work Started', previous_status='ASSIGNED',
        new_status=schedule.status, client=client,
        content_object=schedule, remarks=remarks,
    )


def wcr_submitted(user, wcr, remarks=''):
    client = None
    doc = wcr.wcr_number
    if wcr.enquiry_id:
        client = wcr.enquiry.client
    elif wcr.order_id:
        client = wcr.order.client
    log_case_event(
        user, module=MOD_WCR, document_type='WCR',
        document_number=doc, description='WCR Submitted',
        new_status='SUBMITTED', client=client, content_object=wcr, remarks=remarks,
    )


def invoice_generated(user, invoice, remarks=''):
    log_case_event(
        user, module=MOD_INVOICE, document_type='Invoice',
        document_number=invoice.invoice_number,
        description='Invoice Generated', new_status=invoice.approval_status,
        client=invoice.order.client, content_object=invoice, remarks=remarks,
    )


def invoice_approved(user, invoice, remarks=''):
    log_case_event(
        user, module=MOD_INVOICE, document_type='Invoice',
        document_number=invoice.invoice_number,
        description='Invoice Approved', previous_status='SUBMITTED',
        new_status=invoice.approval_status,
        client=invoice.order.client, content_object=invoice, remarks=remarks,
    )


def payment_received(user, invoice, remarks=''):
    log_case_event(
        user, module=MOD_PAYMENT, document_type='Payment',
        document_number=invoice.invoice_number,
        description='Payment Received', new_status='RECEIVED',
        client=invoice.order.client, content_object=invoice, remarks=remarks,
    )


def boq_created(user, boq, remarks=''):
    log_case_event(
        user, module=MOD_BOQ, document_type='BOQ',
        document_number=boq.boq_number,
        description='BOQ Created', new_status=boq.status,
        client=boq.order.client if boq.order_id else None,
        content_object=boq, remarks=remarks,
    )


def pm_observation_created(user, observation, remarks=''):
    log_case_event(
        user, module=MOD_PM, document_type='PM Observation',
        document_number=observation.pm_number or str(observation.pk),
        description='PM Observation Created', new_status=observation.admin_status,
        client=observation.client, content_object=observation, remarks=remarks,
    )
