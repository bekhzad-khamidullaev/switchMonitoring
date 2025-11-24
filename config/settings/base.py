"""
Base settings for Django project.
"""
import os
from pathlib import Path
from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'celery',
    'background_task',
    'django_celery_results',
    'rest_framework',
    'compressor',
    'tailwind',
]

LOCAL_APPS = [
    'snmp',
    'users',
    'theme',
    'vendors',
    'zabbixapp',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'snmp.middleware.LoggingMiddleware',  # Custom logging middleware
    'snmp.middleware.HealthCheckMiddleware',  # Health check middleware
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'uz-UZ'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_files'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login settings
LOGIN_REDIRECT_URL = '/snmp/switches/'
LOGIN_URL = '/login/'

# Compressor settings
COMPRESS_ROOT = BASE_DIR / 'static'
COMPRESS_ENABLED = True
STATICFILES_FINDERS = ('compressor.finders.CompressorFinder',)

# Tailwind settings
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = ["127.0.0.1"]

# Celery Configuration
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_IMPORTS = ('snmp.tasks',)
CELERY_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE_FILENAME = os.path.join(BASE_DIR, 'celerybeat-schedule.db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ENABLE_UTC = True

CELERY_BEAT_SCHEDULE = {
    'update-switch-status': {
        'task': 'snmp.tasks.update_switch_status_task',
        'schedule': 300,  # Every 5 minutes
    },
    'update-optical-info': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': 14400,  # Every 4 hours
    },
    'update-switch-inventory': {
        'task': 'snmp.tasks.update_switch_inventory_task',
        'schedule': crontab(minute=0, hour=9),  # 09:00 AM
    },
    'subnet_discovery': {
        'task': 'snmp.tasks.subnet_discovery_task',
        'schedule': crontab(minute=0, hour=3),  # 03:00 AM
    },
    'auto-discover-devices': {
        'task': 'snmp.tasks.auto_discover_devices_task',
        'schedule': crontab(minute=30, hour=2),  # 02:30 AM daily
    },
    'monitor-all-uplinks': {
        'task': 'snmp.tasks.monitor_all_uplinks_task',
        'schedule': 600,  # Every 10 minutes
    },
    'comprehensive-health-check': {
        'task': 'snmp.tasks.comprehensive_health_check_task',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    'cleanup-old-data': {
        'task': 'snmp.tasks.cleanup_old_data_task',
        'schedule': crontab(minute=0, hour=1),  # 01:00 AM daily
    },
    'generate-daily-report': {
        'task': 'snmp.tasks.generate_daily_report_task',
        'schedule': crontab(minute=0, hour=6),  # 06:00 AM daily
    },
    'task-health-check': {
        'task': 'snmp.tasks.task_health_check',
        'schedule': 300,  # Every 5 minutes
    },
}

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Security Settings (will be overridden in production)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'