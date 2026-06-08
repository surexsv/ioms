DOC_ORDER = 'ORDER'
DOC_QUOTATION = 'QUOTATION'
DOC_WCR = 'WCR'
DOC_BOQ = 'BOQ'
DOC_INVOICE = 'INVOICE'
DOC_PURCHASE_ORDER = 'PURCHASE_ORDER'
DOC_SCHEDULE = 'SCHEDULE'

DOCUMENT_TYPES = (
    (DOC_ORDER, 'Order'),
    (DOC_QUOTATION, 'Quotation'),
    (DOC_WCR, 'Work Completion Report'),
    (DOC_BOQ, 'BOQ'),
    (DOC_INVOICE, 'Invoice'),
    (DOC_PURCHASE_ORDER, 'Purchase Order'),
    (DOC_SCHEDULE, 'Work Schedule'),
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
}
