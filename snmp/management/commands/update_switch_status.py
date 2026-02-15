import asyncio
import logging

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from ping3 import ping

from snmp.models import ManagedDevice

logger = logging.getLogger("ICMP RESPONSE")


class Command(BaseCommand):
    help = 'Update switch ICMP status in one pass'

    @staticmethod
    async def _save_switch(switch):
        await sync_to_async(switch.save, thread_sensitive=True)()

    async def update_switch_status(self, ip):
        if ip is None:
            return

        switch = await sync_to_async(ManagedDevice.objects.filter(ip=ip).first)()
        if switch is None:
            logger.warning("switch was not found for ip=%s", ip)
            return

        try:
            host_alive = ping(ip, unit='ms', size=32, timeout=2)
            switch.status = host_alive is not None
            await self._save_switch(switch)
        except Exception as exc:
            logger.info("Error updating switch status for %s: %s", ip, exc)

    async def handle_async(self, *args, **options):
        ip_addresses = await sync_to_async(list)(
            ManagedDevice.objects.values_list('ip', flat=True).order_by('last_update')
        )
        tasks = [self.update_switch_status(ip) for ip in ip_addresses]
        await asyncio.gather(*tasks)

    def handle(self, *args, **options):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.handle_async(*args, **options))
