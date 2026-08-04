"""
Backward-compatible package entrypoint.

`config.settings` continues to resolve for existing scripts/tools by loading
development settings. Prefer setting DJANGO_SETTINGS_MODULE explicitly:

  config.settings.development  (default in manage.py / wsgi / asgi)
  config.settings.production
"""

from .development import *  # noqa: F401,F403
