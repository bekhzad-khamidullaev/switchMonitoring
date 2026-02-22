import asyncio
import logging

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from ping3 import ping

from snmp.models import Device

logger = logging.getLogger("ICMP RESPONSE")


class Command(BaseCommand):
    help = 'Update device ICMP status in one pass'

    @staticmethod
    async def _save_device(device):
        await sync_to_async(device.save, thread_sensitive=True)()

    async def update_device_status(self, ip):
        if ip is None:
            return

        device = await sync_to_async(Device.objects.filter(ip=ip).first)()
        if device is None:
            logger.warning("device was not found for ip=%s", ip)
            return

        try:
            host_alive = ping(str(ip), unit='ms', size=32, timeout=2)
            device.status = host_alive is not None
            await self._save_device(device)
        except Exception as exc:
            logger.info("Error updating device status for %s: %s", ip, exc)
            device.status = False
            await self._save_device(device)

    async def handle_async(self, *args, **options):
        ip_addresses = await sync_to_async(list)(
            Device.objects.values_list('ip', flat=True).order_by('updated')
        )
        tasks = [self.update_device_status(ip) for ip in ip_addresses]
        await asyncio.gather(*tasks)

    def handle(self, *args, **options):
        asyncio.run(self.handle_async(*args, **options))
