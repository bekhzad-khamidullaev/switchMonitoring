import asyncio
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from snmp.models import Device
from snmp.services.discovery.read_base_snmp import snmp_get, OID_SYS_OBJECT_ID, OID_SYS_DESCR, SnmpReadError
from snmp.services.discovery.normalize import normalize_vendor_model

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Lightweight SNMP discovery to fetch vendor/model/firmware for Devices'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Limit number of devices')
        parser.add_argument('--workers', type=int, default=50, help='Max concurrent workers')
        parser.add_argument('--timeout', type=int, default=2, help='SNMP timeout')
        parser.add_argument('--retries', type=int, default=1, help='SNMP retries')

    async def discover_device(self, device, semaphore, timeout, retries):
        async with semaphore:
            community = device.snmp_community_ro or "public" # Fallback to common default
            try:
                # We use run_in_executor because pysnmp hlapi is synchronous
                loop = asyncio.get_event_loop()
                
                sys_object_id = await loop.run_in_executor(
                    None, snmp_get, device.ip, community, OID_SYS_OBJECT_ID, timeout, retries
                )
                sys_descr = await loop.run_in_executor(
                    None, snmp_get, device.ip, community, OID_SYS_DESCR, timeout, retries
                )

                if sys_object_id or sys_descr:
                    normalized = normalize_vendor_model(sys_object_id, sys_descr)
                    device.vendor = normalized.get('vendor', '')
                    device.model = normalized.get('model', '')
                    device.firmware = normalized.get('firmware', '')
                    device.sys_object_id = sys_object_id
                    device.last_discovered_at = timezone.now()
                    await asyncio.to_thread(device.save)
                    return True
            except Exception as e:
                # logger.debug(f"Failed to discover {device.ip}: {e}")
                pass
            return False

    async def handle_async(self, *args, **options):
        limit = options['limit']
        workers = options['workers']
        timeout = options['timeout']
        retries = options['retries']

        devices_qs = Device.objects.filter(vendor='', model='')
        if limit:
            devices_qs = devices_qs[:limit]
        
        devices = await asyncio.to_thread(list, devices_qs)
        total = len(devices)
        self.stdout.write(f"Starting discovery for {total} devices with {workers} workers...")

        semaphore = asyncio.Semaphore(workers)
        tasks = [self.discover_device(d, semaphore, timeout, retries) for d in devices]
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r)
        
        self.stdout.write(self.style.SUCCESS(f"Finished. Successfully discovered: {success_count}/{total}"))

    def handle(self, *args, **options):
        asyncio.run(self.handle_async(*args, **options))
