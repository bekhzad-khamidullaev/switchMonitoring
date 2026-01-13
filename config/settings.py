from pathlib import Path
import os
from celery.schedules import crontab


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-q_c2d9*79bojtl-_la-50e*3b!rqg!gd^@tl@dxe2!dygp6@+%'


DEBUG = True
ALLOWED_HOSTS = ['*','ddm.tshtt.uz','10.10.137.120']

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
    'background_task',
    'django_celery_results',
    'rest_framework',
    'compressor',
    'tailwind',
    'theme',
    # 'olt_monitoring',
    'vendors',
    'zabbixapp',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# APPEND_SLASH=False

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': 'snmp',
#         'USER': 'snmp',
#         'PASSWORD': 'admin',
#         'HOST': '127.0.0.1',
#         'PORT': '',
#     }
# }

# Database configuration
# Default to SQLite for local/dev runs. Can be overridden via environment variables.
#
# Examples:
#   SQLite (default):
#     DB_ENGINE=django.db.backends.sqlite3
#     DB_NAME=/path/to/db.sqlite3
#
#   PostgreSQL:
#     DB_ENGINE=django.db.backends.postgresql
#     DB_NAME=snmp DB_USER=snmp DB_PASSWORD=admin DB_HOST=127.0.0.1 DB_PORT=5432
DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
DB_NAME = os.getenv("DB_NAME", str(BASE_DIR / "db.sqlite3"))
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "")

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DB_NAME,
        **({"USER": DB_USER} if DB_USER else {}),
        **({"PASSWORD": DB_PASSWORD} if DB_PASSWORD else {}),
        **({"HOST": DB_HOST} if DB_HOST else {}),
        **({"PORT": DB_PORT} if DB_PORT else {}),
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


# --- Файлы ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static_files"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STATICFILES_DIRS = [BASE_DIR / "static"]


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "staticfiles"),
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
# CELERY_RESULT_BACKEND = 'django-db'
# CELERY_CACHE_BACKEND = 'django-cache'
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
        'schedule': 300,
    },
    'update-optical-info': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': 14400,
    },
    'update-switch-inventory': {
        'task': 'snmp.tasks.update_switch_inventory_task',
        'schedule': crontab(minute=0, hour=9),  # 09:00 AM
    },
    'subnet_discovery': {
        'task': 'snmp.tasks.subnet_discovery_task',
        'schedule': crontab(minute=0, hour=3),  # 04:00 AM
    },
}



LOGIN_REDIRECT_URL = '/snmp/switches/'

COMPRESS_ROOT = BASE_DIR / 'static'
 
COMPRESS_ENABLED = True
 
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]


TAILWIND_APP_NAME = 'theme'

INTERNAL_IPS = [
    "127.0.0.1",
]