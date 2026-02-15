import asyncio
import ipaddress
import logging
import time

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from ping3 import ping

from snmp.models import ManagedDevice

logger = logging.getLogger("ICMP RESPONSE")
SUBNET = ipaddress.ip_network("10.47.64.0/19", strict=False)


class Command(BaseCommand):
    help = "Update switch status via ICMP ping (subnet-filtered)"

    async def save_switch(self, switch):
        await sync_to_async(switch.save, thread_sensitive=True)()

    async def update_switch_status(self, switch):
        try:
            start_time = time.time()
            response = ping(switch.ip, unit="ms", size=32, timeout=2)
            elapsed_time = time.time() - start_time
            switch.status = response is not None
            await self.save_switch(switch)
            logger.info(
                "Updated %s: Status %s (RTT: %.2f sec)",
                switch.ip,
                'UP' if switch.status else 'DOWN',
                elapsed_time,
            )
        except Exception as exc:
            logger.error("Error updating switch status for %s: %s", switch.ip, exc)

    async def handle_async(self):
        all_switches = await sync_to_async(lambda: list(ManagedDevice.objects.all()), thread_sensitive=True)()
        filtered_switches = [
            switch for switch in all_switches if ipaddress.IPv4Address(switch.ip) in SUBNET
        ]
        tasks = [self.update_switch_status(switch) for switch in filtered_switches]
        await asyncio.gather(*tasks)

    def handle(self, *args, **options):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_async())
        finally:
            loop.close()
