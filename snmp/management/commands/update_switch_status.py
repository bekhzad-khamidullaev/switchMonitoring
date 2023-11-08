import ping3
from django.core.management.base import BaseCommand
from snmp.models import Switch
import logging
# from background_task import background

from pysnmp.hlapi import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        ip_addresses = Switch.objects.values_list('device_ip', flat=True)
        for ip in ip_addresses:
            host_alive = ping3.ping(ip)
            logger.info(host_alive)
            if host_alive is not None:
                switches = Switch.objects.filter(device_ip=ip)
                for switch in switches:
                    switch.status = True
                    switch.save()
                    

# def run_update_switch_status_task():
#     Command()
