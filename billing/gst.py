"""GST determination and tax breakdown for IOMS invoices."""

from decimal import Decimal, ROUND_HALF_UP

from config.company import COMPANY

GST_TYPE_INTRA = 'INTRA_STATE'
GST_TYPE_INTER = 'INTER_STATE'

GST_TYPE_CHOICES = (
    (GST_TYPE_INTRA, 'Intra-State (CGST + SGST)'),
    (GST_TYPE_INTER, 'Inter-State (IGST)'),
)

COMPANY_STATE = COMPANY['state']
COMPANY_STATE_CODE = COMPANY['state_code']

# GSTIN first-two-digit state codes (common states)
GSTIN_STATE_CODE_MAP = {
    '01': 'Jammu & Kashmir',
    '02': 'Himachal Pradesh',
    '03': 'Punjab',
    '04': 'Chandigarh',
    '05': 'Uttarakhand',
    '06': 'Haryana',
    '07': 'Delhi',
    '08': 'Rajasthan',
    '09': 'Uttar Pradesh',
    '10': 'Bihar',
    '11': 'Sikkim',
    '12': 'Arunachal Pradesh',
    '13': 'Nagaland',
    '14': 'Manipur',
    '15': 'Mizoram',
    '16': 'Tripura',
    '17': 'Meghalaya',
    '18': 'Assam',
    '19': 'West Bengal',
    '20': 'Jharkhand',
    '21': 'Odisha',
    '22': 'Chhattisgarh',
    '23': 'Madhya Pradesh',
    '24': 'Gujarat',
    '26': 'Dadra and Nagar Haveli and Daman and Diu',
    '27': 'Maharashtra',
    '29': 'Karnataka',
    '30': 'Goa',
    '31': 'Lakshadweep',
    '32': 'Kerala',
    '33': 'Tamil Nadu',
    '34': 'Puducherry',
    '35': 'Andaman and Nicobar Islands',
    '36': 'Telangana',
    '37': 'Andhra Pradesh',
    '38': 'Ladakh',
}

INDIAN_STATE_CHOICES = tuple(
    sorted({name for name in GSTIN_STATE_CODE_MAP.values()}, key=str.lower)
)


def gstin_state_code(gst_number):
    gst = (gst_number or '').strip().upper()
    if len(gst) >= 2 and gst[:2].isdigit():
        return gst[:2]
    return ''


def pan_from_gstin(gst_number):
    """Extract 10-character PAN embedded in a 15-digit GSTIN (positions 3–12)."""
    gst = (gst_number or '').strip().upper()
    if len(gst) >= 12:
        return gst[2:12]
    return ''


def state_name_from_code(state_code):
    return GSTIN_STATE_CODE_MAP.get((state_code or '').strip(), '')


def gst_type_label(gst_type):
    if gst_type == GST_TYPE_INTRA:
        return 'Intra-State (CGST + SGST)'
    return 'Inter-State (IGST)'


def resolve_client_gst_type(client):
    """
    Preferred: explicit client.gst_type.
    Fallback: client state / state_code / GSTIN prefix vs company Kerala (32).
    """
    explicit = (getattr(client, 'gst_type', None) or '').strip()
    if explicit in (GST_TYPE_INTRA, GST_TYPE_INTER):
        return explicit

    state_code = (getattr(client, 'state_code', None) or '').strip()
    if not state_code:
        state_code = gstin_state_code(getattr(client, 'gst_number', ''))

    if state_code:
        return GST_TYPE_INTRA if state_code == COMPANY_STATE_CODE else GST_TYPE_INTER

    state_name = (getattr(client, 'state', None) or '').strip().lower()
    if state_name:
        if state_name == COMPANY_STATE.lower():
            return GST_TYPE_INTRA
        return GST_TYPE_INTER

    return GST_TYPE_INTER


def resolve_client_state_display(client):
    """State name and code for invoice PDF addressing."""
    state_code = (getattr(client, 'state_code', None) or '').strip()
    if not state_code:
        state_code = gstin_state_code(getattr(client, 'gst_number', ''))

    state_name = (getattr(client, 'state', None) or '').strip()
    if not state_name and state_code:
        state_name = state_name_from_code(state_code)
    return state_name or '—', state_code or '—'


def calculate_gst_breakdown(taxable_amount, gst_type):
    """Return total GST and component amounts for intra vs inter state."""
    taxable = Decimal(taxable_amount or 0)
    rate = Decimal(str(COMPANY['gst_rate_percent'])) / Decimal('100')
    total_gst = (taxable * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    if gst_type == GST_TYPE_INTRA:
        half = (total_gst / 2).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        other = total_gst - half
        return {
            'gst_type': GST_TYPE_INTRA,
            'gst': total_gst,
            'cgst_amount': half,
            'sgst_amount': other,
            'igst_amount': Decimal('0.00'),
        }

    return {
        'gst_type': GST_TYPE_INTER,
        'gst': total_gst,
        'cgst_amount': Decimal('0.00'),
        'sgst_amount': Decimal('0.00'),
        'igst_amount': total_gst,
    }


def sync_client_gst_fields(client, save=False):
    """
    Populate state / state_code / gst_type / pan_number from GSTIN when missing.
    Used by migration utility and management command.
    """
    state_code = (client.state_code or '').strip() or gstin_state_code(client.gst_number)
    if state_code and not client.state_code:
        client.state_code = state_code

    if not (client.state or '').strip() and state_code:
        client.state = state_name_from_code(state_code)

    if not (client.gst_type or '').strip():
        client.gst_type = resolve_client_gst_type(client)

    pan_number = (getattr(client, 'pan_number', None) or '').strip()
    if not pan_number and getattr(client, 'gst_number', None):
        inferred_pan = pan_from_gstin(client.gst_number)
        if inferred_pan:
            client.pan_number = inferred_pan

    if save:
        client.save(update_fields=['state', 'state_code', 'gst_type', 'pan_number'])
    return client
