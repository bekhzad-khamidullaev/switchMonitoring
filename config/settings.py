from pathlib import Path
import os
from celery.schedules import crontab


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-q_c2d9*79bojtl-_la-50e*3b!rqg!gd^@tl@dxe2!dygp6@+%'


DEBUG = True

ALLOWED_HOSTS = ['*']

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'snmp',
        'USER': 'snmp',
        'PASSWORD': 'admin',
        'HOST': '127.0.0.1',
        'PORT': '',
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


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True



STATIC_URL = '/static/'


STATIC_ROOT = os.path.join(BASE_DIR, 'static')


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CELERY_BROKER_URL = 'redis://localhost:6379/0'

CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'

CELERY_TIMEZONE = 'Asia/Tashkent'


CELERY_IMPORTS = ('snmp.tasks',)


CELERY_TRACK_STARTED = True

CELERY_BEAT_SCHEDULE_FILENAME = os.path.join(BASE_DIR, 'celerybeat-schedule.db')


CELERY_BEAT_SCHEDULE = {
    'update-switch-status': {
        'task': 'snmp.tasks.update_switch_status_task',
        'schedule': crontab(minute='*/1'),  # Every 30 minutes
    },
    'update-optical-info-first': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': crontab(minute=0, hour=4),  # 04:00 AM
    },
    'update-optical-info-second': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': crontab(minute=0, hour=18),  # 06:00 PM
    },
    'update-switch-inventory': {
        'task': 'snmp.tasks.update_switch_inventory_task',
        'schedule': crontab(minute=0, hour=3),  # 03:00 AM
    },
}