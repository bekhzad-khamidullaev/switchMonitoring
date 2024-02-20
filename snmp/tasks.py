from celery import shared_task
from django.core.management import call_command
from snmp.models import Switch


    
# @shared_task
# def update_switch_status_task(ip):
#     call_command('update_switch_status', ip)

@shared_task
def update_switch_status_task(ip):
    switch = Switch.objects.get(ip=ip)
    from .management.commands import update_switch_status
    update_switch_status(ip)

@shared_task
def update_optical_info_task():
    call_command('update_optical_info')
    
@shared_task
def update_switch_inventory_task():
    call_command('update_switch_inventory_task')
    
