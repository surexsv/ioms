"""
Local / development settings.

Default module: config.settings.development
"""

import os

from .base import *  # noqa: F401,F403

# Keep the existing local secret as fallback so current developers are not blocked.
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-ro=ckic9ngy26o)13oj8go&=xg*xvs#=&y6fvihybj6p301g5r',
)

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

# Development static files are served from STATICFILES_DIRS (base).
# STATIC_ROOT is optional locally (useful if you run collectstatic).
STATIC_ROOT = BASE_DIR / 'staticfiles'  # noqa: F405
