from .defaults import (
    DEFAULT_BANK_DETAILS,
    DEFAULT_FOOTER_NOTES,
    DEFAULT_PAYMENT_TERMS,
    DEFAULT_TERMS_AND_CONDITIONS,
    DEFAULT_VALIDITY_DAYS,
    DEFAULT_VALIDITY_PERIOD,
)


def build_default_terms_text(settings=None):
    """Combine master settings into the text stored on new quotations."""
    if settings is None:
        from .models import QuotationSettings
        settings = QuotationSettings.get_solo()

    sections = []
    for field in ('terms_and_conditions', 'validity_period', 'payment_terms'):
        value = getattr(settings, field, '').strip()
        if value:
            sections.append(value)
    return '\n\n'.join(sections)


def resolve_quotation_terms(quotation, settings=None):
    """Terms text for PDF, print, and preview."""
    if quotation.terms_and_conditions.strip():
        return quotation.terms_and_conditions.strip()
    return build_default_terms_text(settings)


def quotation_document_sections(quotation, settings=None):
    """Shared context for PDF, print view, and detail preview."""
    if settings is None:
        from .models import QuotationSettings
        settings = QuotationSettings.get_solo()

    return {
        'settings': settings,
        'terms_text': resolve_quotation_terms(quotation, settings),
        'bank_details': settings.bank_details.strip(),
        'footer_notes': settings.footer_notes.strip(),
        'payment_terms': settings.payment_terms.strip(),
        'validity_period': settings.validity_period.strip(),
    }
