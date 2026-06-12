from company_settings.models import CompanySettings

from config.company import COMPANY
from company_settings.signatory import (
    closing_already_has_thanks,
    get_document_signatory,
    strip_signatory_footer_paragraphs,
)



from .defaults import (

    DEFAULT_CLOSING_PARAGRAPH,

    DEFAULT_COVERING_LETTER_BODY,

    DEFAULT_COVERING_LETTER_SUBJECT,

)





def body_to_paragraphs(text):

    if not text:

        return []

    return [p.strip() for p in str(text).split('\n\n') if p.strip()]





def paragraphs_to_body(paragraphs):

    return '\n\n'.join(p.strip() for p in paragraphs if p and p.strip())





def get_default_covering_letter_content(template=None, cl_settings=None):

    """Resolve default subject/body from template or covering letter settings."""

    if template is not None:

        return template.subject, template.body



    if cl_settings is None:

        from .models import CoveringLetterSettings

        cl_settings = CoveringLetterSettings.get_solo()



    subject = cl_settings.default_subject.strip() or DEFAULT_COVERING_LETTER_SUBJECT

    body = cl_settings.default_body.strip() or DEFAULT_COVERING_LETTER_BODY

    return subject, body





def resolve_covering_letter_subject(quotation, cl_settings=None):

    if quotation.covering_letter_subject.strip():

        return quotation.covering_letter_subject.strip()

    if quotation.proposal_template_id:

        return quotation.proposal_template.subject

    subject, _ = get_default_covering_letter_content(cl_settings=cl_settings)

    return subject





def resolve_covering_letter_body(quotation, cl_settings=None):

    if quotation.covering_letter_body.strip():

        return quotation.covering_letter_body.strip()

    if quotation.proposal_template_id:

        return quotation.proposal_template.body

    _, body = get_default_covering_letter_content(cl_settings=cl_settings)

    return body





def covering_letter_context(quotation, cl_settings=None):

    """Auto-filled covering letter data for preview, print, and PDF."""

    if cl_settings is None:

        from .models import CoveringLetterSettings

        cl_settings = CoveringLetterSettings.get_solo()



    client = quotation.client

    subject = resolve_covering_letter_subject(quotation, cl_settings)

    body = resolve_covering_letter_body(quotation, cl_settings)

    closing = cl_settings.closing_paragraph.strip() or DEFAULT_CLOSING_PARAGRAPH

    signatory = get_document_signatory(quotation)

    company_settings = CompanySettings.get_solo()



    signature_image = signatory['signature_image'] if quotation.include_signature else None

    company_seal = company_settings.company_seal if quotation.include_company_seal else None

    body_paragraphs = strip_signatory_footer_paragraphs(body_to_paragraphs(body))

    return {

        'cl_settings': cl_settings,

        'subject': subject,

        'body': body,

        'body_paragraphs': body_paragraphs,

        'closing_paragraph': closing,

        'company_introduction': cl_settings.company_introduction.strip(),

        'signatory': signatory,

        'signatory_name': signatory['name'],

        'designation': signatory['designation'],

        'quotation_number': quotation.quotation_number or '—',

        'quotation_date': quotation.quotation_date,

        'client_name': client.name,

        'client_address': client.address,

        'contact_person': quotation.contact_person,

        'project_name': quotation.subject,

        'reference_number': quotation.reference_number,

        'include_covering_letter': quotation.include_covering_letter,

        'include_terms': quotation.include_terms,

        'include_company_seal': quotation.include_company_seal,

        'include_signature': quotation.include_signature,

        'signature_image': signature_image,

        'company_seal': company_seal,

        'company_name': COMPANY['name'],

        'show_thanks_closing': not closing_already_has_thanks(body_paragraphs, closing),

    }


