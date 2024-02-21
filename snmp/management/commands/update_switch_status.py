import asyncio
import logging
from django.core.management.base import BaseCommand
from snmp.models import Switch
from ping3 import ping, verbose_ping
from asgiref.sync import sync_to_async
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

class Command(BaseCommand):
    help = 'Update switch data'

    @sync_to_async
    def save_switch(self, switch):
        switch.save()

    async def update_switch_status(self, ip):
        try:
            if ip is None:
                logger.info("IP address is None. Skipping update.")
                return

            start_time = time.time()

            host_alive = ping(ip, unit='ms', size=32, timeout=2,interface='ens192')

            elapsed_time = time.time() - start_time

            if host_alive is not None:  # Check if ping was successful
                logger.info(
                    f"Response time: {host_alive} ms, host ip: {ip}, Elapsed time: {elapsed_time:.2f} seconds"
                )

                switches = await sync_to_async(list)(Switch.objects.filter(ip=ip).order_by('-last_update'))
                for switch in switches:
                    status = bool(host_alive)
                    switch.status = status
                    await self.save_switch(switch)
            else:
                logger.info(f"Host {ip} not reachable, Elapsed time: {elapsed_time:.2f} seconds")
        except Exception as e:
            logger.info(f"Error updating switch status for {ip}: {e}")

    async def handle_async(self, *args, **options):
        total_start_time = time.time()
        switches_per_batch = 5

        while True:
            switches_count = await sync_to_async(Switch.objects.count)()

            for offset in range(0, switches_count, switches_per_batch):
                ip_addresses = await sync_to_async(list)(
                    Switch.objects.values_list('ip', flat=True)[offset:offset + switches_per_batch]
                )

                batch_start_time = time.time()

                tasks = [self.update_switch_status(ip) for ip in ip_addresses]
                await asyncio.gather(*tasks)

                batch_elapsed_time = time.time() - batch_start_time
                logger.info(f"Batch processed in {batch_elapsed_time:.2f} seconds")

            # Introduce a delay between iterations
            await asyncio.sleep(60)  # Adjust the delay as needed (e.g., 60 seconds)

        total_elapsed_time = time.time() - total_start_time
        logger.info(f"Total elapsed time: {total_elapsed_time:.2f} seconds")

    def handle(self, *args, **options):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.handle_async(*args, **options))
        except KeyboardInterrupt:
            # Allow the program to be terminated gracefully with Ctrl+C
            pass
