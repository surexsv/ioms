from config.version import (
    DISPLAY_TITLE,
    PRODUCT_NAME,
    RELEASE_DATE,
    RELEASE_STATUS,
    SHORT_NAME,
    VERSION,
    VERSION_LABEL,
)


def ioms_version(request):
    return {
        'ioms_product_name': PRODUCT_NAME,
        'ioms_short_name': SHORT_NAME,
        'ioms_version': VERSION,
        'ioms_version_label': VERSION_LABEL,
        'ioms_display_title': DISPLAY_TITLE,
        'ioms_release_status': RELEASE_STATUS,
        'ioms_release_date': RELEASE_DATE,
    }
