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
    # -------------------------
    # Device Availability
    # -------------------------
    'update-device-status': {
        'task': 'snmp.tasks.update_device_status_task',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'monitoring'},
    },

    # -------------------------
    # Optical Signal Monitoring
    # -------------------------
    
    # Full optical poll - every 4 hours
    'update-optical-info': {
        'task': 'snmp.tasks.update_optical_info_task',
        'schedule': crontab(minute=0, hour='*/4'),
        'options': {'queue': 'optical'},
    },
    
    # Critical/warning devices - every hour (priority monitoring)
    'update-optical-critical': {
        'task': 'snmp.tasks.update_optical_critical_task',
        'schedule': crontab(minute=30),  # Every hour at :30
        'options': {'queue': 'optical'},
    },
    
    # Check for alerts - every 15 minutes
    'check-optical-alerts': {
        'task': 'snmp.tasks.check_optical_alerts_task',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'alerts'},
    },
    
    # Daily optical report - every day at 6:00 AM
    'generate-optical-report': {
        'task': 'snmp.tasks.generate_optical_report_task',
        'schedule': crontab(minute=0, hour=6),
        'options': {'queue': 'reports'},
    },
    
    # Record optical history - every 4 hours (after optical poll)
    'record-optics-history': {
        'task': 'snmp.tasks.record_optics_history_task',
        'schedule': crontab(minute=5, hour='*/4'),  # 5 minutes after optical poll
        'options': {'queue': 'optical'},
    },
    
    # Create/update optical alerts - every 15 minutes
    'create-optics-alerts': {
        'task': 'snmp.tasks.create_optics_alerts_task',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'alerts'},
    },
    
    # Cleanup old optical history - daily at 4:00 AM
    'cleanup-optics-history': {
        'task': 'snmp.tasks.cleanup_optics_history_task',
        'schedule': crontab(minute=0, hour=4),
        'options': {'queue': 'maintenance'},
    },

    # -------------------------
    # Inventory & Discovery
    # -------------------------
    
    # Inventory update - daily at midnight
    'update-device-inventory': {
        'task': 'snmp.tasks.update_device_inventory_task',
        'schedule': crontab(minute=0, hour=0),
        'options': {'queue': 'inventory'},
    },

    # Subnet discovery - daily at 1:00 AM
    'subnet-discovery': {
        'task': 'snmp.tasks.subnet_discovery_task',
        'schedule': crontab(minute=0, hour=1),
        'options': {'queue': 'discovery'},
    },

    # -------------------------
    # Bandwidth Monitoring
    # -------------------------
    
    # Poll bandwidth counters - every 5 minutes
    'poll-bandwidth': {
        'task': 'snmp.tasks.poll_bandwidth_task',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'bandwidth'},
    },
    
    # Cleanup old samples - daily at 3:00 AM
    'cleanup-bandwidth-samples': {
        'task': 'snmp.tasks.cleanup_bandwidth_samples_task',
        'schedule': crontab(minute=0, hour=3),
        'options': {'queue': 'maintenance'},
    },
}

# Task routing to different queues for better load distribution
app.conf.task_routes = {
    'snmp.tasks.update_device_status_task': {'queue': 'monitoring'},
    'snmp.tasks.update_optical_*': {'queue': 'optical'},
    'snmp.tasks.check_optical_alerts_task': {'queue': 'alerts'},
    'snmp.tasks.generate_optical_report_task': {'queue': 'reports'},
    'snmp.tasks.update_device_inventory_task': {'queue': 'inventory'},
    'snmp.tasks.subnet_discovery_task': {'queue': 'discovery'},
    'snmp.tasks.poll_bandwidth_task': {'queue': 'bandwidth'},
    'snmp.tasks.cleanup_bandwidth_samples_task': {'queue': 'maintenance'},
}

# Default queue for tasks not explicitly routed
app.conf.task_default_queue = 'default'
