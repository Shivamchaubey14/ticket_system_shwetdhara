import os
from decouple import config   
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SECURITY WARNING: keep the secret key used in production secret!
# ============================================
SECRET_KEY = config('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# ============================================
# HOST CONFIGURATION
# ============================================
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:8000,http://127.0.0.1:8000').split(',')

ALLOWED_ORIGINS = config('ALLOWED_ORIGINS', default='http://localhost:8000,http://127.0.0.1:8000').split(',')

SITE_URL = config('SITE_URL', default='http://localhost:8000')

# ============================================
# REST FRAMEWORK & JWT
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'main_app_ticket.authentication.JWTCookieAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_REFRESH': 'refresh_token',
    'AUTH_COOKIE_SECURE': True,
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_SAMESITE': 'Lax',
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# ============================================
# APPLICATION DEFINITION
# ============================================
INSTALLED_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom apps
    'main_app_ticket',
    'django_celery_beat',
    'django_celery_results',
]

MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ticket_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ticket_system.wsgi.application'

# ============================================
# DATABASE (MySQL from .env)
# ============================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST': config('DATABASE_HOST', default='localhost'),
        'PORT': config('DATABASE_PORT', default='3306'),
    }
}

# ============================================
# CUSTOM USER MODEL
# ============================================
AUTH_USER_MODEL = 'main_app_ticket.CustomUser'

# ============================================
# PASSWORD VALIDATION
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'en-us'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = '/'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC FILES
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================================
# EMAIL SETTINGS (from .env)
# ============================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')
EMAIL_TIMEOUT = 30

# ============================================
# ESCALATION MONITOR
# ============================================
ESCALATION_TIER1_GRACE_HOURS = 4
ESCALATION_TIER2_GRACE_HOURS = 24
ESCALATION_CE_EMAIL = config('ESCALATION_CE_EMAIL')
ESCALATION_CE_NAME = "Chief Executive"
ESCALATION_SENDER_NAME = config('ESCALATION_SENDER_NAME', default='KSTS')
ESCALATION_CC_EMAIL = config('ESCALATION_CC_EMAIL', default='')
KSTS_BASE_URL = config('KSTS_BASE_URL', default='http://localhost:8000')
KSTS_SYSTEM_NAME = config('KSTS_SYSTEM_NAME', default='KSTS')

# ============================================
# CELERY CONFIGURATION
# ============================================
REDIS_HOST = config('REDIS_HOST', default='localhost')
REDIS_PORT = config('REDIS_PORT', default='6379')
REDIS_DB = config('REDIS_DB', default='0')
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "ksts-overdue-auto-escalate-every-15min": {
        "task": "ksts.escalation.overdue_sweep",
        "schedule": 900,
    },
    "ksts-tier2-sweep-every-30min": {
        "task": "ksts.escalation.tier2_sweep",
        "schedule": 1800,
    },
}

# ============================================
# ESCALATION ADDITIONAL
# ============================================
ESCALATION_TIER2_DELAY_HOURS = 24

# ============================================
# NOTE: Add to INSTALLED_APPS if not already:
#   "django_celery_beat",
#   "django_celery_results",
# ============================================