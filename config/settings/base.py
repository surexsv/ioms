"""
Common Django settings for all environments.

Environment-specific values live in development.py / production.py.
Database ENGINE / NAME / USER / PASSWORD are NOT defined here.
"""

import os
from pathlib import Path

# config/settings/base.py → parents: settings → config → project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'accounts.apps.AccountsConfig',
    'clients',
    'orders',
    'wcr',
    'billing',
    'boq',
    'quotations',
    'attendance',
    'dashboard',
    'document_generator',
    'company_settings',
    'scheduling',
    'enquiries',
    'estimate_boq',
    'productivity',
    'case_intelligence',
    'daily_meetings',
    'employee_requests',
    'special_projects',
    'fleet',
    'project_expenses.apps.ProjectExpensesConfig',
    'preventive_maintenance.apps.PreventiveMaintenanceConfig',
    'task_manager.apps.TaskManagerConfig',
    'voice_assistant.apps.VoiceAssistantConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.OMSAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.OMSUserFriendlyErrorMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.oms_navigation',
                'accounts.version_context.ioms_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
# Office clocks follow India Standard Time. Datetimes stay timezone-aware
# and are stored in UTC; screens and local dates use Asia/Kolkata (UTC+5:30).
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

AUTH_USER_MODEL = 'accounts.User'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Optional. When set, Malayalam field notes are rewritten as professional English.
IOMS_AI_API_KEY = os.environ.get('IOMS_AI_API_KEY', '')
IOMS_AI_API_URL = os.environ.get('IOMS_AI_API_URL', 'https://api.openai.com/v1/chat/completions')
IOMS_AI_MODEL = os.environ.get('IOMS_AI_MODEL', 'gpt-4o-mini')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'director_dashboard'
LOGOUT_REDIRECT_URL = 'logout_success'

(BASE_DIR / 'logs').mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[{asctime}] {levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'security',
        },
        'security_console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'security',
        },
    },
    'loggers': {
        'ioms.security': {
            'handlers': ['security_file', 'security_console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
