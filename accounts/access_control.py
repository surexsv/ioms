"""Centralized access-denied messaging and session handling."""

SESSION_REASON = 'ioms_denied_reason'
SESSION_MODULE = 'ioms_denied_module'
SESSION_ATTEMPTED_URL = 'ioms_denied_attempted_url'

REASON_UNAUTHORIZED = 'unauthorized'
REASON_MODULE = 'module'
REASON_ROLE = 'role'
REASON_FEATURE = 'feature'

DENIED_MESSAGES = {
    REASON_UNAUTHORIZED: (
        'You do not have permission to access this page or perform this action. '
        'If you believe this is required for your role, please contact your '
        'System Administrator or Reporting Manager.'
    ),
    REASON_MODULE: (
        'This module is available only to authorized users. '
        'If you believe this is required for your role, please contact your '
        'System Administrator or Reporting Manager.'
    ),
    REASON_ROLE: (
        'Your current role does not permit this action. '
        'Please contact your administrator if additional access is required.'
    ),
    REASON_FEATURE: (
        'You do not have permission to access this feature. '
        'If you believe this is required for your role, please contact your '
        'System Administrator or Reporting Manager.'
    ),
}

DENIED_TITLES = {
    REASON_UNAUTHORIZED: 'Access Restricted',
    REASON_MODULE: 'Access Restricted',
    REASON_ROLE: 'Access Restricted',
    REASON_FEATURE: 'Access Restricted',
}


def store_denial_context(request, reason=REASON_UNAUTHORIZED, module_key=None, attempted_url=None):
    request.session[SESSION_REASON] = reason
    request.session[SESSION_MODULE] = module_key or ''
    request.session[SESSION_ATTEMPTED_URL] = attempted_url or request.get_full_path()


def pop_denial_context(request):
    reason = request.session.pop(SESSION_REASON, REASON_UNAUTHORIZED)
    module_key = request.session.pop(SESSION_MODULE, '') or None
    attempted_url = request.session.pop(SESSION_ATTEMPTED_URL, '') or None
    return {
        'reason': reason,
        'module_key': module_key,
        'attempted_url': attempted_url,
        'title': DENIED_TITLES.get(reason, DENIED_TITLES[REASON_UNAUTHORIZED]),
        'message': DENIED_MESSAGES.get(reason, DENIED_MESSAGES[REASON_UNAUTHORIZED]),
    }


def denial_context_for_request(request, reason=REASON_UNAUTHORIZED, module_key=None):
    """Build context without session (direct render)."""
    return {
        'reason': reason,
        'module_key': module_key,
        'attempted_url': request.get_full_path(),
        'title': DENIED_TITLES.get(reason, DENIED_TITLES[REASON_UNAUTHORIZED]),
        'message': DENIED_MESSAGES.get(reason, DENIED_MESSAGES[REASON_UNAUTHORIZED]),
    }
