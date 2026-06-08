"""Shared authorized signatory helpers for all IOMS documents."""


SIGNATORY_FIELD_NAMES = (
    'authorized_signatory_name',
    'authorized_signatory_designation',
    'signature_image',
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


def format_signatory_lines(name='', designation=''):
    """
    Build signatory text lines for PDF/HTML.
    Fallback: returns only 'Authorized Signatory' when name/designation are empty.
    """
    lines = ['Authorized Signatory']
    if name:
        lines.append(name)
    if designation:
        lines.append(designation)
    return lines


def format_signatory_html(name='', designation=''):
    return '<br/>'.join(format_signatory_lines(name, designation))
