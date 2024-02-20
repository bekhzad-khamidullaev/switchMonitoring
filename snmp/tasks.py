from celery import shared_task
from django.core.management import call_command
from celery import current_task
from snmp.management.commands.startserver import Command as StartServerCommand

@shared_task
def runserver_task():
    start_server_command = StartServerCommand()
    start_server_command.handle()

@shared_task
def update_switch_status_task(switch_id):
    current_task.update_state(state='PROGRESS', meta={'status': 'Updating switch status'})
    call_command('update_switch_status', switch_id)
    return {'status': 'Switch status updated successfully'}
    
@shared_task
def update_optical_info_task():
    current_task.update_state(state='PROGRESS', meta={'status': 'Updating switch optical info'})
    call_command('update_optical_info')
    return {'status': 'Switch optical info updated successfully'}

@shared_task
def update_switch_inventory_task():
    current_task.update_state(state='PROGRESS', meta={'status': 'Updating switch inventory info'})
    call_command('update_switch_inventory')
    return {'status': 'Switch inventory info updated successfully'}
