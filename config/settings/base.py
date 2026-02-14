from pathlib import Path
import os
import importlib.util
from celery.schedules import crontab


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()
DEBUG = env_bool("DEBUG", DJANGO_ENV not in {"prod", "production"})
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY is required when DEBUG is False")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'celery',
    'snmp',
    'users',
    'django_celery_results',
    'rest_framework',
]


def _is_available(app_name):
    return importlib.util.find_spec(app_name) is not None


for optional_app in ['background_task', 'compressor', 'tailwind', 'theme', 'vendors', 'zabbixapp']:
    if _is_available(optional_app):
        INSTALLED_APPS.append(optional_app)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'config.middleware.MethodNotAllowedMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'snmp'),
        'USER': os.getenv('DB_USER', 'snmp'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

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

LANGUAGE_CODE = 'uz-UZ'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = False

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_files'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_IMPORTS = ('snmp.tasks',)
CELERY_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE_FILENAME = os.path.join(BASE_DIR, 'celerybeat-schedule.db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ENABLE_UTC = True
LEGACY_TASKS_ENABLED = env_bool('LEGACY_TASKS_ENABLED', False)

CELERY_BEAT_SCHEDULE = {
    'poll-all-device-metrics': {
        'task': 'snmp.tasks.poll_all_devices_metrics_task',
        'schedule': int(os.getenv('POLL_ALL_DEVICES_INTERVAL_SEC', '300')),
    },
    'discover-all-devices': {
        'task': 'snmp.tasks.discover_all_devices_task',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}

if LEGACY_TASKS_ENABLED:
    CELERY_BEAT_SCHEDULE.update({
        'update-switch-status': {
            'task': 'snmp.tasks.update_switch_status_task',
            'schedule': 300,
        },
        'update-optical-info': {
            'task': 'snmp.tasks.update_optical_info_task',
            'schedule': 14400,
        },
        'update-switch-inventory': {
            'task': 'snmp.tasks.update_switch_inventory_task',
            'schedule': crontab(minute=0, hour=9),
        },
        'subnet_discovery': {
            'task': 'snmp.tasks.subnet_discovery_task',
            'schedule': crontab(minute=0, hour=3),
        },
    })

LOGIN_REDIRECT_URL = '/snmp/switches/'

COMPRESS_ROOT = BASE_DIR / 'static'
COMPRESS_ENABLED = _is_available('compressor')
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]
if _is_available('compressor'):
    STATICFILES_FINDERS.append('compressor.finders.CompressorFinder')

TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = [
    '127.0.0.1',
]

SNMP_DEFAULT_COMMUNITY_RO = os.getenv('SNMP_DEFAULT_COMMUNITY_RO', 'public')
SNMP_DEFAULT_COMMUNITY_RW = os.getenv('SNMP_DEFAULT_COMMUNITY_RW', 'private')
ZABBIX_URL = os.getenv('ZABBIX_URL', '')
ZABBIX_TOKEN = os.getenv('ZABBIX_TOKEN', '')
ZABBIX_VERIFY_SSL = env_bool('ZABBIX_VERIFY_SSL', True)

ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL', '')
ALERT_NOTIFY_TIMEOUT = int(os.getenv('ALERT_NOTIFY_TIMEOUT', '5'))
ALERT_EMAIL_FROM = os.getenv('ALERT_EMAIL_FROM', 'monitoring@localhost')
ALERT_EMAIL_TO = env_list('ALERT_EMAIL_TO', '')
ALERT_MIN_CONSECUTIVE_BREACH = int(os.getenv('ALERT_MIN_CONSECUTIVE_BREACH', '2'))
ALERT_MIN_CONSECUTIVE_RECOVERY = int(os.getenv('ALERT_MIN_CONSECUTIVE_RECOVERY', '2'))

LOG_JSON = env_bool('LOG_JSON', True)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'config.logging.JsonFormatter',
        },
        'plain': {
            'format': '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if LOG_JSON else 'plain',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'snmp': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
