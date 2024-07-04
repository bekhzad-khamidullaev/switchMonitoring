from lib.snmp_walk import perform_snmpwalk
from olt_monitoring.models import Olt, Slot
from django.db.models import Count
from django.core.paginator import Paginator
from django.core.management.base import BaseCommand
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("SNMP RESPONSE")

class Command(BaseCommand):
    help = 'Get host temperature'

    def handle(self, *args, **options):
        hosts_per_page = 100
        delay_seconds = 3600

        while True:
            paginator = Paginator(Olt.objects.filter(status=True).order_by('-pk'), hosts_per_page)
            try:
                for page in range(1, paginator.num_pages + 1):
                    hosts = paginator.page(page)
                    duplicate_ips = Olt.objects.values('ip').annotate(count=Count('ip')).filter(count__gt=1)
                    
                    for duplicate_ip in duplicate_ips:
                        ip = duplicate_ip['ip']
                        duplicate_hosts = Olt.objects.filter(ip=ip).order_by('-id')[1:]
                        for duplicate_host in duplicate_hosts:
                            duplicate_host.delete()

                    for host in hosts:
                        temperatureStatus = host.model.temperatureStatus if host.model else None
                        slot_oid = host.model.slot_oid if host.model else None
                        if temperatureStatus and slot_oid:
                            community = host.community_ro
                            temperatures = perform_snmpwalk(host.ip, temperatureStatus, community)
                            slot_numbers = perform_snmpwalk(host.ip, slot_oid, community)

                            # Ensure both lists have the same length
                            if len(temperatures) == len(slot_numbers):
                                for slot_number, temperature in zip(slot_numbers, temperatures):
                                    Slot.objects.update_or_create(
                                        host=host, 
                                        slot_number=slot_number, 
                                        defaults={'temperature': f'{temperature} °C'}
                                    )
                                logger.info(f"Updated temperatures for host {host.hostname} ip: {host.ip}")
                            else:
                                logger.error(f"Mismatch in the number of slot numbers and temperatures for host {host.hostname} ip: {host.ip}")


            except Exception as e:
                logger.error(f"Error processing SNMP response: {e}")
                continue


if __name__ == '__main__':
    Command().handle()
