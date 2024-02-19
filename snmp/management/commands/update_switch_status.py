import asyncio
import logging
from django.core.management.base import BaseCommand
from snmp.models import Switch
from ping3 import ping
from asgiref.sync import sync_to_async
from snmp.tasks import update_switch_status_task



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

class Command(BaseCommand):
    help = 'Update switch data'

    @sync_to_async
    def save_switch(self, switch):
        switch.save()

    async def update_switch_status(self, ip):
        host_alive = ping(ip)
        self.stdout.write(self.style.SUCCESS(f"{host_alive} host ip {ip}"))
        switches = await sync_to_async(list)(Switch.objects.filter(ip=ip))
        for switch in switches:
            status = bool(host_alive)
            switch.status = status
            await self.save_switch(switch)

    async def handle_async(self, *args, **options):
        switches_per_batch = 100
        switches_count = await sync_to_async(Switch.objects.count)()

        for offset in range(0, switches_count, switches_per_batch):
            ip_addresses = await sync_to_async(list)(
                Switch.objects.values_list('ip', flat=True)[offset:offset + switches_per_batch]
            )
            tasks = [self.update_switch_status(ip) for ip in ip_addresses]
            await asyncio.gather(*tasks)

    def handle(self, *args, **options):
        asyncio.run(self.handle_async(*args, **options))
