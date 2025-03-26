import asyncio
import logging
import time
import ipaddress
from django.core.management.base import BaseCommand
from snmp.models import Switch
from ping3 import ping
from asgiref.sync import sync_to_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")

# Define subnet filter
SUBNET = ipaddress.ip_network("10.47.64.0/19", strict=False)


class Command(BaseCommand):
    help = "Update switch status via ICMP ping"

    async def save_switch(self, switch):
        """Asynchronously save switch status to the database."""
        await sync_to_async(switch.save, thread_sensitive=True)()

    async def update_switch_status(self, switch):
        """Ping the switch and update its status."""
        try:
            start_time = time.time()
            response = ping(switch.ip, unit="ms", size=32, timeout=2)
            elapsed_time = time.time() - start_time

            switch.status = bool(response)
            await self.save_switch(switch)
            logger.info(f"Updated {switch.ip}: Status {'UP' if switch.status else 'DOWN'} (RTT: {elapsed_time:.2f} sec)")

        except Exception as e:
            logger.error(f"Error updating switch status for {switch.ip}: {e}")

    async def handle_async(self):
        """Handle switch status updates in batches."""
        total_start_time = time.time()
        switches_per_batch = 10

        while True:
            # Fetch all switches and filter in Python
            all_switches = await sync_to_async(lambda: list(Switch.objects.all()), thread_sensitive=True)()
            filtered_switches = [switch for switch in all_switches if ipaddress.IPv4Address(switch.ip) in SUBNET]

            # Process switches in batches
            for offset in range(0, len(filtered_switches), switches_per_batch):
                batch = filtered_switches[offset : offset + switches_per_batch]
                batch_start_time = time.time()

                tasks = [self.update_switch_status(switch) for switch in batch]
                await asyncio.gather(*tasks)

                batch_elapsed_time = time.time() - batch_start_time
                logger.info(f"Batch processed in {batch_elapsed_time:.2f} seconds")

            # Introduce delay before next cycle
            await asyncio.sleep(3)

            total_elapsed_time = time.time() - total_start_time
            logger.info(f"Total elapsed time: {total_elapsed_time:.2f} seconds")

    def handle(self, *args, **options):
        """Entry point for Django management command."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.handle_async())
        except KeyboardInterrupt:
            logger.info("Process interrupted by user.")
        finally:
            loop.close()
