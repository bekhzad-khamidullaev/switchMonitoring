from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


app = Celery('config')


app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.broker_connection_retry_on_startup = True


app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


app.conf.beat_schedule = {
    # Availability
    'update-switch-status': {
        'task': 'snmp.tasks.update_switch_status_task',
        'schedule': crontab(minute='*/5'),
    },

    # Optical (legacy collector; can be swapped to update_optical_info_mib later)
    'update-optical-info': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': crontab(minute=0, hour='*/4'),
    },

    # Inventory
    'update-switch-inventory': {
        'task': 'snmp.tasks.update_switch_inventory_task',
        'schedule': crontab(minute=0, hour=0),
    },

    # Discovery
    'subnet-discovery': {
        'task': 'snmp.tasks.subnet_discovery_task',
        'schedule': crontab(minute=0, hour=1),
    },

    # Bandwidth counters
    'poll-bandwidth': {
        'task': 'snmp.tasks.poll_bandwidth_task',
        'schedule': crontab(minute='*/5'),
    },
    'cleanup-bandwidth-samples': {
        'task': 'snmp.tasks.cleanup_bandwidth_samples_task',
        'schedule': crontab(minute=0, hour=3),
    },
}
