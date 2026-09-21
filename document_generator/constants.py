DOC_ORDER = 'ORDER'
DOC_QUOTATION = 'QUOTATION'
DOC_WCR = 'WCR'
DOC_BOQ = 'BOQ'
DOC_INVOICE = 'INVOICE'
DOC_PURCHASE_ORDER = 'PURCHASE_ORDER'
DOC_SCHEDULE = 'SCHEDULE'
DOC_ENQUIRY = 'ENQUIRY'
DOC_ESTIMATE_BOQ = 'ESTIMATE_BOQ'
DOC_REQUEST = 'REQUEST'
DOC_SPECIAL_PROJECT = 'SPECIAL_PROJECT'
DOC_PM = 'PM_OBSERVATION'

DOCUMENT_TYPES = (
    (DOC_ORDER, 'Order'),
    (DOC_QUOTATION, 'Quotation'),
    (DOC_WCR, 'Work Completion Report'),
    (DOC_BOQ, 'BOQ'),
    (DOC_INVOICE, 'Invoice'),
    (DOC_PURCHASE_ORDER, 'Purchase Order'),
    (DOC_SCHEDULE, 'Work Schedule'),
    (DOC_ENQUIRY, 'Enquiry'),
    (DOC_ESTIMATE_BOQ, 'Estimate BOQ'),
    (DOC_REQUEST, 'Employee Request'),
    (DOC_SPECIAL_PROJECT, 'Special Project'),
    (DOC_PM, 'PM Observation'),
)

DOCUMENT_TYPE_LABELS = dict(DOCUMENT_TYPES)

PREFIX_FIELD_MAP = {
    DOC_ORDER: 'order_prefix',
    DOC_QUOTATION: 'quotation_prefix',
    DOC_WCR: 'wcr_prefix',
    DOC_BOQ: 'boq_prefix',
    DOC_INVOICE: 'invoice_prefix',
    DOC_PURCHASE_ORDER: 'purchase_order_prefix',
    DOC_SCHEDULE: 'schedule_prefix',
    DOC_ENQUIRY: 'enquiry_prefix',
    DOC_ESTIMATE_BOQ: 'estimate_boq_prefix',
    DOC_REQUEST: 'request_prefix',
    DOC_SPECIAL_PROJECT: 'special_project_prefix',
    DOC_PM: 'pm_prefix',
}
