from pathlib import Path
from django.conf import settings

COMPANY = {
    'name': 'Infomates Techno Solutions Pvt Ltd',
    'display_name': 'infomates TECHNO SOLUTIONS PRIVATE LIMITED',
    'address': 'Door No: 32/260A-3, 1st Floor, Bava Complex, Thammanam Jn., Kochi-682 032',
    'phones': ['8129400206', '9567378711'],
    'emails': ['infomates.manoj@gmail.com', 'surex.s@infomates.net'],
    'website': 'www.infomatestechnosolutions.com',
    'gstin': '32AACCI5396N1Z5',
    'pan': 'AACCI5396N',
    'state': 'Kerala',
    'state_code': '32',
    'bank_name': 'Union Bank of India',
    'bank_branch': 'Ponnurunni',
    'bank_account': '423701010037146',
    'bank_ifsc': 'UBIN0542377',
    'default_hsn_sac': '998422',
    'gst_rate_percent': 18,  # CGST 9% + SGST 9%
    'cgst_percent': 9,
    'sgst_percent': 9,
    'terms': [
        'Payment shall be made by NEFT / RTGS / cheque / DD in favour of '
        'Infomates Techno Solutions Pvt Ltd.',
        'Payment should be made within 30 days from the date of invoice.',
    ],
}

LOGO_PATH = Path(settings.BASE_DIR) / 'static' / 'branding' / 'infomates_logo.png'
