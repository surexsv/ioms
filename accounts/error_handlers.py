from django.shortcuts import render
from django.urls import reverse

from .access_control import denial_context_for_request, REASON_UNAUTHORIZED
from .permissions import allowed_dashboard_url_name
from .security_log import log_access_denied, log_system_error


def _error_context(request, title, message, status_code):
    dashboard_name = 'login'
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        dashboard_name = allowed_dashboard_url_name(user)
    referer = request.META.get('HTTP_REFERER', '')
    return {
        'page_title': title,
        'message': message,
        'status_code': status_code,
        'dashboard_url_name': dashboard_name,
        'go_back_url': referer,
        'show_go_back': bool(referer),
    }


def permission_denied_view(request, exception=None):
    log_access_denied(
        request,
        reason='permission_denied',
        attempted_url=request.get_full_path(),
    )
    ctx = denial_context_for_request(request, reason=REASON_UNAUTHORIZED)
    ctx.update(_error_context(
        request,
        ctx['title'],
        ctx['message'],
        403,
    ))
    return render(request, 'accounts/access_denied.html', ctx, status=403)


def page_not_found_view(request, exception=None):
    ctx = _error_context(
        request,
        'Page Not Found',
        'The page you requested could not be found. It may have been moved or removed.',
        404,
    )
    return render(request, 'errors/not_found.html', ctx, status=404)


def server_error_view(request):
    ctx = _error_context(
        request,
        'Something Went Wrong',
        'An unexpected error occurred while processing your request. '
        'Our team has been notified. Please try again later or return to your dashboard.',
        500,
    )
    return render(request, 'errors/server_error.html', ctx, status=500)


def user_friendly_error_view(request, exc):
    log_system_error(request, exc)
    ctx = _error_context(
        request,
        'Something Went Wrong',
        'An unexpected error occurred while processing your request. '
        'Please try again later or contact your System Administrator if the problem persists.',
        500,
    )
    user = getattr(request, 'user', None)
    ctx['dashboard_url_name'] = (
        allowed_dashboard_url_name(user)
        if user is not None and user.is_authenticated else 'login'
    )
    return render(request, 'errors/server_error.html', ctx, status=500)
