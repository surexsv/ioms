from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse

from .access_control import REASON_MODULE, store_denial_context
from .error_handlers import user_friendly_error_view
from .permissions import (
    can_access,
    can_view_billing,
    resolve_path_module,
    allowed_dashboard_url_name,
    MODULE_DASHBOARD_DIRECTOR,
)
from .security_log import log_access_denied


class OMSAccessMiddleware:
    """Enforce login, profile approval, and module access."""

    EXEMPT_PATHS = {
        '/',
        '/login',
        '/logout',
        '/logged-out',
        '/access-denied',
        '/register',
        '/profile-resubmit',
    }

    APPROVAL_EXEMPT_PATHS = {
        '/account-status',
        '/logout',
        '/logged-out',
        '/profile-resubmit',
    }

    EXEMPT_PREFIXES = (
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        normalized = path.rstrip('/') or '/'

        if self._is_exempt(path):
            return self.get_response(request)

        if path.startswith('/admin/'):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return redirect_to_login(path, login_url=reverse('login'))

        user = request.user
        if not user.is_superuser and not user.is_profile_approved:
            if normalized not in self.APPROVAL_EXEMPT_PATHS and not path.startswith('/profile-resubmit'):
                return redirect('account_status')

        if path.startswith('/billing/'):
            if not can_view_billing(request.user):
                log_access_denied(
                    request,
                    reason=REASON_MODULE,
                    module_key='billing',
                    attempted_url=request.get_full_path(),
                )
                store_denial_context(
                    request,
                    reason=REASON_MODULE,
                    module_key='billing',
                    attempted_url=request.get_full_path(),
                )
                return redirect('access_denied')
        else:
            module_key = resolve_path_module(path)
            if module_key and not can_access(request.user, module_key):
                log_access_denied(
                    request,
                    reason=REASON_MODULE,
                    module_key=module_key,
                    attempted_url=request.get_full_path(),
                )
                store_denial_context(
                    request,
                    reason=REASON_MODULE,
                    module_key=module_key,
                    attempted_url=request.get_full_path(),
                )
                return redirect('access_denied')

        if path in ('/dashboard/', '/dashboard'):
            if not can_access(request.user, MODULE_DASHBOARD_DIRECTOR):
                return redirect(allowed_dashboard_url_name(request.user))

        response = self.get_response(request)

        if not request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'

        return response

    def _is_exempt(self, path):
        normalized = path.rstrip('/') or '/'
        if normalized in self.EXEMPT_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)


class OMSUserFriendlyErrorMiddleware:
    """Replace technical Django exceptions with professional error pages for end users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            if settings.DEBUG and getattr(request.user, 'is_superuser', False):
                raise
            return user_friendly_error_view(request, exc)
