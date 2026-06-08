import logging

from django.utils import timezone

logger = logging.getLogger('ioms.security')


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def log_access_denied(request, reason, module_key=None, attempted_url=None):
    user = request.user
    username = user.get_username() if user.is_authenticated else 'anonymous'
    logger.warning(
        'ACCESS_DENIED | user=%s | datetime=%s | module=%s | url=%s | ip=%s | reason=%s',
        username,
        timezone.now().isoformat(),
        module_key or '-',
        attempted_url or request.get_full_path(),
        get_client_ip(request),
        reason,
        extra={
            'user_id': getattr(user, 'pk', None),
            'attempted_url': attempted_url or request.get_full_path(),
            'module_key': module_key,
            'reason': reason,
            'ip': get_client_ip(request),
        },
    )


def log_system_error(request, exc):
    user = request.user
    username = user.get_username() if user.is_authenticated else 'anonymous'
    logger.exception(
        'SYSTEM_ERROR | user=%s | url=%s | ip=%s | error=%s',
        username,
        request.get_full_path(),
        get_client_ip(request),
        type(exc).__name__,
    )
