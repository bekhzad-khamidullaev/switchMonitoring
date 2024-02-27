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
    call_command('update_switch_inventory_task')
    
