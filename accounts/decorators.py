from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .access_control import REASON_MODULE, REASON_ROLE, store_denial_context
from .permissions import can_access
from .roles import user_role
from .security_log import log_access_denied


def access_denied_response(request, reason='unauthorized', module_key=None):
    """Redirect to the professional access-denied page (never raise template errors)."""
    attempted_url = request.get_full_path()
    log_access_denied(request, reason=reason, module_key=module_key, attempted_url=attempted_url)
    store_denial_context(
        request,
        reason=reason,
        module_key=module_key,
        attempted_url=attempted_url,
    )
    return redirect('access_denied')


def module_required(module_key):
    """Require login and permission for a module key."""
    def decorator(view_func):
        @login_required(login_url='login')
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not can_access(request.user, module_key):
                return access_denied_response(
                    request,
                    reason=REASON_MODULE,
                    module_key=module_key,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def role_required(*roles):
    """Legacy decorator — maps to role list; superuser always allowed."""
    def decorator(view_func):
        @login_required(login_url='login')
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if (
                request.user.is_superuser
                or user_role(request.user) in roles
                or getattr(request.user, 'role', None) in roles
            ):
                return view_func(request, *args, **kwargs)
            return access_denied_response(request, reason=REASON_ROLE)
        return wrapper
    return decorator


def login_required_oms(view_func):
    """Redirect unauthenticated users to login."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.urls import reverse
            login_url = reverse('login')
            next_url = request.get_full_path()
            return redirect(f'{login_url}?next={next_url}')
        return view_func(request, *args, **kwargs)
    return wrapper
