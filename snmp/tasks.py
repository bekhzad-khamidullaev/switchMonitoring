from celery import shared_task
from django.core.management import call_command


    

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


@shared_task
def poll_bandwidth_task():
    call_command('poll_bandwidth')


@shared_task
def cleanup_bandwidth_samples_task():
    call_command('cleanup_bandwidth_samples')
