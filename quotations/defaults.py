"""Default quotation master settings (seeded into QuotationSettings on first run)."""

DEFAULT_TERMS_AND_CONDITIONS = """1. Billing shall be based on actual quantities executed and supplied.

2. Purchase Order (PO) must be issued in favour of:
   Infomates Techno Solutions (P) Ltd
   Bava Complex, Thammanam, Kochi – 682032.

3. Implementation period: Within 30 working days from receipt of Purchase Order, advance payment (if applicable), and site readiness.

4. Taxes:
   GST and other applicable taxes shall be charged as per prevailing Government regulations at the time of invoicing. Any statutory changes after submission of the quotation shall be charged extra.

5. All required permissions, approvals, landlord consent, and statutory clearances shall be arranged by the customer before commencement of work.

6. Mode of Payment:
   All payments shall be made through Cheque, Demand Draft (DD), RTGS, NEFT, or Bank Transfer favouring:
   Infomates Techno Solutions (P) Ltd

9. Prices and material availability are subject to market fluctuations and stock availability. Therefore, final pricing and delivery schedules may vary slightly at the time of order confirmation.

10. Any additional work, materials, services, civil work, electrical work, transportation, permissions, or requirements not specifically mentioned in this quotation shall be charged extra."""

DEFAULT_VALIDITY_PERIOD = """Quotation Validity:
This quotation is valid for one (1) week from the date of quotation."""

DEFAULT_PAYMENT_TERMS = """Payment Terms:

* Payment for supply materials shall be made in advance against Purchase Order (PO) or written order confirmation.
* Balance payment shall be released within 10 days from completion of work and submission of invoice."""

DEFAULT_BANK_DETAILS = """Bank Name: Union Bank of India
Branch: Ponnurunni
Account No: 423701010037146
IFSC: UBIN0542377
Account Name: Infomates Techno Solutions (P) Ltd"""

DEFAULT_FOOTER_NOTES = ''
DEFAULT_VALIDITY_DAYS = 7

DEFAULT_COVERING_LETTER_SUBJECT = 'Submission of Commercial Proposal / Quotation'

DEFAULT_COVERING_LETTER_BODY = """Dear Sir/Madam,

Greetings from Infomates Techno Solutions (P) Ltd.

We thank you for the opportunity to submit our proposal for the subject work.

Based on the discussions, site survey, and requirements shared, we are pleased to submit our commercial proposal for your kind consideration.

We assure you of our best services and support and look forward to establishing a long-term business relationship with your esteemed organization.

The detailed quotation is enclosed for your review.

Should you require any clarification, please feel free to contact us.

Thanking you and assuring you of our best attention at all times.

Yours faithfully,

For Infomates Techno Solutions (P) Ltd

Authorized Signatory"""

DEFAULT_COMPANY_INTRODUCTION = (
    'Infomates Techno Solutions (P) Ltd is a leading provider of telecom, IT, '
    'networking, and field service solutions.'
)

DEFAULT_CLOSING_PARAGRAPH = (
    'Thanking you and assuring you of our best attention at all times.'
)

SEED_PROPOSAL_TEMPLATES = [
    {
        'name': 'Standard Quotation',
        'subject': DEFAULT_COVERING_LETTER_SUBJECT,
        'body': DEFAULT_COVERING_LETTER_BODY,
        'is_default': True,
    },
    {
        'name': 'Telecom Infrastructure Proposal',
        'subject': 'Submission of Telecom Infrastructure Proposal',
        'body': """Dear Sir/Madam,

Greetings from Infomates Techno Solutions (P) Ltd.

We thank you for the opportunity to submit our proposal for telecom infrastructure works.

Based on the site survey, technical discussions, and scope shared, we are pleased to submit our commercial proposal for your kind consideration.

We assure you of quality execution, timely delivery, and dedicated post-implementation support.

The detailed commercial quotation is enclosed for your review.

Should you require any clarification, please feel free to contact us.

Thanking you and assuring you of our best attention at all times.

Yours faithfully,

For Infomates Techno Solutions (P) Ltd

Authorized Signatory""",
    },
    {
        'name': 'ISP Project Proposal',
        'subject': 'Submission of ISP Project Proposal',
        'body': """Dear Sir/Madam,

Greetings from Infomates Techno Solutions (P) Ltd.

We thank you for inviting us to submit our proposal for the ISP project.

Based on your requirements and our technical assessment, we are pleased to present our commercial proposal for your review.

We are committed to reliable connectivity solutions and professional project execution.

The detailed quotation is enclosed for your kind consideration.

Should you require any clarification, please feel free to contact us.

Thanking you and assuring you of our best attention at all times.

Yours faithfully,

For Infomates Techno Solutions (P) Ltd

Authorized Signatory""",
    },
    {
        'name': 'AMC Proposal',
        'subject': 'Submission of Annual Maintenance Contract Proposal',
        'body': """Dear Sir/Madam,

Greetings from Infomates Techno Solutions (P) Ltd.

We thank you for the opportunity to submit our Annual Maintenance Contract (AMC) proposal.

Based on the equipment inventory and service requirements discussed, we are pleased to submit our commercial proposal for your consideration.

We assure you of prompt support, preventive maintenance, and dependable service throughout the contract period.

The detailed quotation is enclosed for your review.

Should you require any clarification, please feel free to contact us.

Thanking you and assuring you of our best attention at all times.

Yours faithfully,

For Infomates Techno Solutions (P) Ltd

Authorized Signatory""",
    },
    {
        'name': 'Corporate IT Support Proposal',
        'subject': 'Submission of Enterprise IT Support Proposal',
        'body': """Dear Sir/Madam,

Greetings from Infomates Techno Solutions (P) Ltd.

We thank you for the opportunity to submit our enterprise IT support proposal.

Based on the discussions regarding your IT infrastructure and support needs, we are pleased to submit our commercial proposal for your kind consideration.

We assure you of professional service delivery and a long-term partnership approach.

The detailed quotation is enclosed for your review.

Should you require any clarification, please feel free to contact us.

Thanking you and assuring you of our best attention at all times.

Yours faithfully,

For Infomates Techno Solutions (P) Ltd

Authorized Signatory""",
    },
]
