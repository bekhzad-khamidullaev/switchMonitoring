from snmp import update_switch_status, update_switch_inventory
from celery import shared_task

@shared_task
def run_update_switch_status_task():
    update_switch_status.main()
    
@shared_task
def run_update_switch_status_task():
    update_switch_inventory.main()