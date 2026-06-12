"""Shared authorized signatory helpers for all IOMS documents."""


SIGNATORY_FIELD_NAMES = (
    'authorized_signatory_name',
    'authorized_signatory_designation',
    'signature_image',
)

_SIGNATORY_FOOTER_MARKERS = (
    'yours faithfully',
    'for infomates',
    'authorized signatory',
)


def _image_has_file(image_field):
    return bool(image_field and getattr(image_field, 'name', None))


def get_document_signatory(document):
    """
    Read signatory details from any model using AuthorizedSignatoryMixin.
    Never falls back to hardcoded names.
    """
    name = (getattr(document, 'authorized_signatory_name', None) or '').strip()
    designation = (getattr(document, 'authorized_signatory_designation', None) or '').strip()
    signature_image = getattr(document, 'signature_image', None)
    return {
        'name': name,
        'designation': designation,
        'signatory_name': name,
        'signature_image': signature_image if _image_has_file(signature_image) else None,
    }


def strip_signatory_footer_paragraphs(paragraphs):
    """Remove embedded signatory closing lines from covering letter body paragraphs."""
    filtered = []
    for paragraph in paragraphs:
        text = (paragraph or '').strip()
        if not text:
            continue
        lower = text.lower()
        if any(lower.startswith(marker) for marker in _SIGNATORY_FOOTER_MARKERS):
            continue
        if lower in _SIGNATORY_FOOTER_MARKERS:
            continue
        filtered.append(text)
    return filtered


def format_signatory_lines(name='', designation=''):
    """Plain-text signatory lines for simple displays."""
    lines = ['Authorized Signatory:']
    lines.append('_____________________')
    if name:
        lines.append(f'Name: {name}')
    else:
        lines.append('Name: _____________________')
    if designation:
        lines.append(f'Designation: {designation}')
    else:
        lines.append('Designation: _____________________')
    return lines


def format_signatory_html(name='', designation=''):
    return '<br/>'.join(format_signatory_lines(name, designation))


def format_signatory_approval_html(name='', designation=''):
    """Final approval block — single authorized signatory section."""
    return format_signatory_html(name, designation)


THANKS_CLOSING_PARAGRAPH = (
    'Thanking you and assuring you of our best attention at all times.'
)


def closing_already_has_thanks(paragraphs, closing=''):
    """True when the thanks line is already present in body or closing text."""
    thanks_lower = THANKS_CLOSING_PARAGRAPH.lower()
    for text in list(paragraphs) + ([closing] if closing else []):
        if thanks_lower in (text or '').strip().lower():
            return True
    return False


def format_covering_letter_signatory_html(
    name='',
    designation='',
    company_name='',
    include_thanks=True,
):
    """
    Covering letter authorization block for quotation PDF.
    Name and designation are user-editable; blank values stay empty.
    """
    name = (name or '').strip()
    designation = (designation or '').strip()
    lines = []
    if include_thanks:
        lines.append(THANKS_CLOSING_PARAGRAPH)
        lines.append('')
    lines.append(f'<b>For {company_name}</b>')
    lines.append('')
    lines.append('<b>Authorized Signatory:</b>')
    lines.append('')
    lines.append('_____________________________')
    lines.append(f'Name: {name}' if name else 'Name:')
    lines.append(
        f'Designation: {designation}' if designation else 'Designation:'
    )
    return '<br/>'.join(lines)
