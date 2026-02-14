from celery import shared_task
from django.core.management import call_command

from snmp.models import Device
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError
from snmp.services.polling.poller import poll_device_metrics


@shared_task
def update_switch_status_task():
    call_command('update_switch_status')


@shared_task
def update_optical_info_task():
    call_command('update_optical_info')


@shared_task
def update_switch_inventory_task():
    call_command('update_switch_inventory')


@shared_task
def subnet_discovery_task():
    call_command('subnet_discovery')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def poll_device_metrics_task(self, device_id):
    return poll_device_metrics(device_id)


@shared_task
def poll_all_devices_metrics_task():
    total = 0
    for device_id in Device.objects.values_list('id', flat=True):
        total += poll_device_metrics(device_id)
    return total


@shared_task
def discover_all_devices_task():
    success = 0
    failed = 0
    for device in Device.objects.select_related('switch'):
        community = 'public'
        if device.switch_id and device.switch.snmp_community_ro:
            community = device.switch.snmp_community_ro
        try:
            run_device_discovery(ip=str(device.ip), community=community, switch=device.switch)
            success += 1
        except SnmpReadError:
            failed += 1
    return {'success': success, 'failed': failed}
