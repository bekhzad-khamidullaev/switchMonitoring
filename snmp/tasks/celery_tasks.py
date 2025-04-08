from celery import shared_task
from snmp.models import Switch
from snmp.tasks.poll_ports import poll_ports

@shared_task
def poll_switch_ports_task(switch_id):
    try:
        switch = Switch.objects.get(pk=switch_id)
        poll_ports(switch)
        return f"Successfully polled ports for {switch.ip}"
    except Exception as e:
        return f"Error polling switch {switch_id}: {e}"

@shared_task
def poll_all_switches_task():
    for switch in Switch.objects.all():
        poll_switch_ports_task.delay(switch.pk)
