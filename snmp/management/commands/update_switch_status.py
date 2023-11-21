import asyncio
import logging
from django.core.management.base import BaseCommand
from snmp.models import Switch
from ping3 import ping
from asgiref.sync import sync_to_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

class Command(BaseCommand):
    help = 'Update switch data'

    @sync_to_async
    def update_switch_status(self, ip):
        host_alive = ping(ip)
        logger.info(host_alive)
        if host_alive is not None:
            switches = Switch.objects.filter(device_ip=ip)
            for switch in switches:
                switch.status = True
                switch.save()

    async def handle_async(self, *args, **options):
        ip_addresses = await sync_to_async(list)(Switch.objects.values_list('device_ip', flat=True))


        tasks = [self.update_switch_status(ip) for ip in ip_addresses]


        await asyncio.gather(*tasks)

    def handle(self, *args, **options):

        asyncio.run(self.handle_async(*args, **options))

