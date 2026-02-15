import logging
import os
from urllib.parse import urlparse

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
import redis

from snmp.models import Device
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError
from snmp.services.polling.poller import poll_device_metrics

logger = logging.getLogger(__name__)

POLL_DISPATCH_ASYNC = os.getenv('POLL_ALL_DEVICES_ASYNC_DISPATCH', '1').lower() in {'1', 'true', 'yes', 'on'}
POLL_BATCH_SIZE = int(os.getenv('POLL_BATCH_SIZE', '500'))
DISCOVERY_BATCH_SIZE = int(os.getenv('DISCOVERY_BATCH_SIZE', '200'))
POLL_MAX_QUEUE_DEPTH = int(os.getenv('POLL_MAX_QUEUE_DEPTH', '20000'))


def _iter_device_ids(batch_size: int):
    return Device.objects.values_list('id', flat=True).iterator(chunk_size=batch_size)


def _poll_one_device(device_id: int) -> tuple[int, int]:
    try:
        saved = poll_device_metrics(device_id)
        return saved, 0
    except Exception as exc:
        logger.exception('poll failed for device', extra={'device_id': device_id, 'error': str(exc)})
        return 0, 1


def _is_redis_broker() -> bool:
    broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
    return urlparse(str(broker_url)).scheme.startswith('redis')


def _redis_queue_depth(queue_name: str) -> int | None:
    if not _is_redis_broker():
        return None
    try:
        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=2, socket_connect_timeout=2)
        return int(client.llen(queue_name))
    except Exception as exc:
        logger.warning('queue depth check failed', extra={'queue': queue_name, 'error': str(exc)})
        return None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def update_device_status_task(self):
    call_command('update_switch_status')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def update_device_optical_info_task(self):
    call_command('update_optical_info')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def update_device_inventory_task(self):
    call_command('update_switch_inventory')


@shared_task
def update_switch_status_task():
    return update_device_status_task()


@shared_task
def update_optical_info_task():
    return update_device_optical_info_task()


@shared_task
def update_switch_inventory_task():
    return update_device_inventory_task()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def subnet_discovery_task(self):
    call_command('subnet_discovery')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def poll_device_metrics_task(self, device_id):
    return poll_device_metrics(device_id)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3})
def poll_all_devices_metrics_task(self):
    queue_depth = _redis_queue_depth('polling')
    if queue_depth is not None and queue_depth >= POLL_MAX_QUEUE_DEPTH:
        logger.warning(
            'poll fanout throttled because queue depth is high',
            extra={'queue': 'polling', 'depth': queue_depth, 'limit': POLL_MAX_QUEUE_DEPTH},
        )
        return {'queued': 0, 'mode': 'throttled', 'queue_depth': queue_depth}

    if POLL_DISPATCH_ASYNC:
        queued = 0
        for device_id in _iter_device_ids(POLL_BATCH_SIZE):
            poll_device_metrics_task.delay(device_id)
            queued += 1
        return {'queued': queued, 'mode': 'fanout', 'queue_depth': queue_depth}

    total_saved = 0
    failures = 0
    for device_id in _iter_device_ids(POLL_BATCH_SIZE):
        saved, failed = _poll_one_device(device_id)
        total_saved += saved
        failures += failed
    return {'saved': total_saved, 'failed': failures, 'mode': 'inline', 'queue_depth': queue_depth}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3})
def discover_all_devices_task(self):
    success = 0
    failed = 0
    for device in Device.objects.select_related('managed_device').iterator(chunk_size=DISCOVERY_BATCH_SIZE):
        community = device.effective_snmp_community()
        try:
            run_device_discovery(ip=str(device.ip), community=community, managed_device=device.managed_device)
            success += 1
        except SnmpReadError:
            failed += 1
        except Exception as exc:
            logger.exception('discovery failed for device', extra={'device_id': device.id, 'error': str(exc)})
            failed += 1
    return {'success': success, 'failed': failed}
