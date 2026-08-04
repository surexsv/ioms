"""
Production settings.

Secrets and hostnames must come from environment variables — never commit them.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(
            f'Missing required environment variable: {name}'
        )
    return value


DEBUG = False

SECRET_KEY = _require_env('SECRET_KEY')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', '').split(',')
    if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS must be set in production (comma-separated).'
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _require_env('DATABASE_NAME'),
        'USER': _require_env('DATABASE_USER'),
        'PASSWORD': _require_env('DATABASE_PASSWORD'),
        'HOST': os.environ.get('DATABASE_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('DATABASE_CONN_MAX_AGE', '60')),
    }
}

STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405

# HTTPS / proxy (set SECURE_SSL_REDIRECT=False only while testing HTTP)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in (
    '1', 'true', 'yes', 'on',
)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'False').lower() in (
    '1', 'true', 'yes', 'on',
)

_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in _csrf_origins.split(',') if origin.strip()
]
