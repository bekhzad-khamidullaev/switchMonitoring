import asyncio
import logging
from django.core.management.base import BaseCommand
from snmp.models import Switch
from ping3 import ping
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
                return

            start_time = time.time()

            host_alive = ping(ip, unit='ms', size=32, timeout=2, interface='ens192')
            
            elapsed_time = time.time() - start_time

            switch = await sync_to_async(Switch.objects.filter(ip=ip).first)()

            if switch is None:
                status = False
                logger.info(status)
                switch.status = status
                await self.save_switch(switch)
            else:
                status = bool(host_alive)
                logger.info(host_alive)
                switch.status = status
                await self.save_switch(switch)

        except Exception as e:
            logger.info(f"Error updating switch status for {ip}: {e}")

    async def handle_async(self, *args, **options):
        total_start_time = time.time()
        switches_per_batch = 5

        while True:
            switches_count = await sync_to_async(Switch.objects.count)()

            for offset in range(0, switches_count, switches_per_batch):
                ip_addresses = await sync_to_async(list)(
                    Switch.objects.values_list('ip', flat=True).order_by('last_update')[offset:offset + switches_per_batch]
                )

                batch_start_time = time.time()

                tasks = [self.update_switch_status(ip) for ip in ip_addresses]
                await asyncio.gather(*tasks)

                batch_elapsed_time = time.time() - batch_start_time
                logger.info(f"Batch processed in {batch_elapsed_time:.2f} seconds")

            # Introduce a delay between iterations
            await asyncio.sleep(0)  # Adjust the delay as needed (e.g., 60 seconds)

            total_elapsed_time = time.time() - total_start_time
            logger.info(f"Total elapsed time: {total_elapsed_time:.2f} seconds")

    def handle(self, *args, **options):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.handle_async(*args, **options))
        except KeyboardInterrupt:
            # Allow the program to be terminated gracefully with Ctrl+C
            pass
