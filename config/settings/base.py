import os
from pathlib import Path

from celery.schedules import crontab
from kombu import Exchange, Queue
from config.settings.components import (
    env_bool,
    env_list,
    load_host_config,
    load_metrics_config,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DJANGO_ENV = os.getenv("DJANGO_ENV", "dev").strip().lower()
DEBUG = env_bool("DEBUG", DJANGO_ENV not in {"prod", "production"})
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY is required when DEBUG is False")

HOSTING = load_host_config(env_name=DJANGO_ENV)
ALLOWED_HOSTS = HOSTING.allowed_hosts
CSRF_TRUSTED_ORIGINS = HOSTING.csrf_trusted_origins
HOST_CONFIG = HOSTING.as_dict()

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
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
        'CONN_HEALTH_CHECKS': env_bool('DB_CONN_HEALTH_CHECKS', True),
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
USE_TZ = True

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(BASE_DIR / '.cache' / 'django'),
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
        },
    }
}

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
CELERY_TASK_ACKS_LATE = env_bool('CELERY_TASK_ACKS_LATE', True)
CELERY_TASK_REJECT_ON_WORKER_LOST = env_bool('CELERY_TASK_REJECT_ON_WORKER_LOST', True)
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv('CELERY_WORKER_PREFETCH_MULTIPLIER', '1'))
CELERY_WORKER_CONCURRENCY = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.getenv('CELERY_WORKER_MAX_TASKS_PER_CHILD', '200'))
CELERY_WORKER_MAX_MEMORY_PER_CHILD = int(os.getenv('CELERY_WORKER_MAX_MEMORY_PER_CHILD', '262144'))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '120'))
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '180'))
CELERY_TASK_DEFAULT_QUEUE = os.getenv('CELERY_TASK_DEFAULT_QUEUE', 'default')
CELERY_RESULT_EXPIRES = int(os.getenv('CELERY_RESULT_EXPIRES', '3600'))
CELERY_BROKER_CONNECTION_RETRY = env_bool('CELERY_BROKER_CONNECTION_RETRY', True)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = env_bool('CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP', True)
CELERY_BROKER_CONNECTION_MAX_RETRIES = int(os.getenv('CELERY_BROKER_CONNECTION_MAX_RETRIES', '0')) or None
CELERY_BROKER_POOL_LIMIT = int(os.getenv('CELERY_BROKER_POOL_LIMIT', '10'))
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': int(os.getenv('CELERY_VISIBILITY_TIMEOUT', '21600')),
    'socket_connect_timeout': int(os.getenv('CELERY_SOCKET_CONNECT_TIMEOUT', '5')),
    'socket_timeout': int(os.getenv('CELERY_SOCKET_TIMEOUT', '30')),
    'retry_on_timeout': True,
}
CELERY_TASK_ROUTES = {
    'snmp.tasks.poll_device_metrics_task': {'queue': 'polling'},
    'snmp.tasks.poll_all_devices_metrics_task': {'queue': 'default'},
    'snmp.tasks.discover_device_task': {'queue': 'discovery'},
    'snmp.tasks.discover_all_devices_task': {'queue': 'discovery'},
    'snmp.tasks.subnet_autoprovision_task': {'queue': 'discovery'},
    'snmp.tasks.subnet_discovery_task': {'queue': 'discovery'},
    'snmp.tasks.assign_device_profiles_task': {'queue': 'maintenance'},
    'snmp.tasks.update_device_status_task': {'queue': 'maintenance'},
    'snmp.tasks.update_device_optical_info_task': {'queue': 'maintenance'},
    'snmp.tasks.update_device_inventory_task': {'queue': 'maintenance'},
    'snmp.tasks.maintain_metric_samples_task': {'queue': 'maintenance'},
    'snmp.tasks.update_switch_status_task': {'queue': 'maintenance'},
    'snmp.tasks.update_optical_info_task': {'queue': 'maintenance'},
    'snmp.tasks.update_switch_inventory_task': {'queue': 'maintenance'},
}
CELERY_ENABLE_DEAD_LETTER = env_bool('CELERY_ENABLE_DEAD_LETTER', True)
_is_amqp_broker = str(CELERY_BROKER_URL).startswith(('amqp://', 'pyamqp://'))
_dead_letter_exchange = os.getenv('CELERY_DEAD_LETTER_EXCHANGE', 'celery.dlx')
_default_exchange = Exchange(os.getenv('CELERY_DEFAULT_EXCHANGE', 'celery'), type='direct')

def _queue_args(queue_name: str):
    if CELERY_ENABLE_DEAD_LETTER and _is_amqp_broker:
        return {
            'x-dead-letter-exchange': _dead_letter_exchange,
            'x-dead-letter-routing-key': f'{queue_name}.dead',
        }
    return None

CELERY_TASK_QUEUES = (
    Queue('default', exchange=_default_exchange, routing_key='default', queue_arguments=_queue_args('default')),
    Queue('polling', exchange=_default_exchange, routing_key='polling', queue_arguments=_queue_args('polling')),
    Queue('discovery', exchange=_default_exchange, routing_key='discovery', queue_arguments=_queue_args('discovery')),
    Queue('maintenance', exchange=_default_exchange, routing_key='maintenance', queue_arguments=_queue_args('maintenance')),
)
if CELERY_ENABLE_DEAD_LETTER and _is_amqp_broker:
    CELERY_TASK_QUEUES += (
        Queue('default.dead', exchange=Exchange(_dead_letter_exchange, type='direct'), routing_key='default.dead'),
        Queue('polling.dead', exchange=Exchange(_dead_letter_exchange, type='direct'), routing_key='polling.dead'),
        Queue('discovery.dead', exchange=Exchange(_dead_letter_exchange, type='direct'), routing_key='discovery.dead'),
        Queue('maintenance.dead', exchange=Exchange(_dead_letter_exchange, type='direct'), routing_key='maintenance.dead'),
    )
METRICS = load_metrics_config()
METRICS_CONFIG = METRICS.as_dict()
LEGACY_TASKS_ENABLED = METRICS.legacy_tasks_enabled
POLL_ALL_DEVICES_INTERVAL_SEC = METRICS.poll_interval_sec
POLL_ALL_DEVICES_ASYNC_DISPATCH = METRICS.poll_async_dispatch
POLL_BATCH_SIZE = METRICS.poll_batch_size
POLL_MAX_QUEUE_DEPTH = METRICS.poll_max_queue_depth
DISCOVERY_BATCH_SIZE = METRICS.discovery_batch_size
DISCOVERY_MAX_QUEUE_DEPTH = METRICS.discovery_max_queue_depth
METRIC_SAMPLE_RETENTION_ENABLED = METRICS.retention_enabled
METRIC_SAMPLE_RETENTION_DAYS = METRICS.retention_days
METRIC_SAMPLE_RETENTION_BATCH_SIZE = METRICS.retention_batch_size
METRIC_SAMPLE_RETENTION_MAX_BATCHES = METRICS.retention_max_batches
METRIC_SAMPLE_RETENTION_HOUR = METRICS.retention_hour
METRIC_SAMPLE_RETENTION_MINUTE = METRICS.retention_minute
AUTOPROVISION_ENABLED = METRICS.autoprovision_enabled
AUTOPROVISION_HOUR = METRICS.autoprovision_hour
AUTOPROVISION_MINUTE = METRICS.autoprovision_minute
AUTOPROVISION_ASSIGN_PROFILES = METRICS.autoprovision_assign_profiles

CELERY_BEAT_SCHEDULE = {
    'poll-all-device-metrics': {
        'task': 'snmp.tasks.poll_all_devices_metrics_task',
        'schedule': POLL_ALL_DEVICES_INTERVAL_SEC,
    },
    'discover-all-devices': {
        'task': 'snmp.tasks.discover_all_devices_task',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}

if METRIC_SAMPLE_RETENTION_ENABLED:
    CELERY_BEAT_SCHEDULE.update({
        'maintain-metric-samples': {
            'task': 'snmp.tasks.maintain_metric_samples_task',
            'schedule': crontab(
                minute=METRIC_SAMPLE_RETENTION_MINUTE,
                hour=METRIC_SAMPLE_RETENTION_HOUR,
            ),
        },
    })

if LEGACY_TASKS_ENABLED:
    CELERY_BEAT_SCHEDULE.update({
        'update-device-status': {
            'task': 'snmp.tasks.update_device_status_task',
            'schedule': 300,
        },
        'update-optical-info': {
            'task': 'snmp.tasks.update_device_optical_info_task',
            'schedule': 14400,
        },
        'update-device-inventory': {
            'task': 'snmp.tasks.update_device_inventory_task',
            'schedule': crontab(minute=0, hour=9),
        },
        'subnet_discovery': {
            'task': 'snmp.tasks.subnet_discovery_task',
            'schedule': crontab(minute=0, hour=3),
        },
    })

if AUTOPROVISION_ENABLED:
    CELERY_BEAT_SCHEDULE.update({
        'subnet-autoprovision': {
            'task': 'snmp.tasks.subnet_autoprovision_task',
            'schedule': crontab(minute=AUTOPROVISION_MINUTE, hour=AUTOPROVISION_HOUR),
        },
    })

LOGIN_REDIRECT_URL = '/snmp/devices/'

COMPRESS_ROOT = BASE_DIR / 'static'
COMPRESS_ENABLED = False
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]
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
