from django.core.management.base import BaseCommand
from django.db import connection

from django.db.models import Count
from snmp.models import Device

class Command(BaseCommand):
    help = 'Delete duplicate entries from the managed device model'

    def handle(self, *args, **options):
        duplicate_ips = Device.objects.values('ip').annotate(count=Count('ip')).filter(count__gt=1)
        duplicate_hostname = Device.objects.values('hostname').annotate(count=Count('hostname')).filter(count__gt=1)

        # Iterate over duplicate IPs
        for hostname in duplicate_hostname:
            hostname = hostname['hostname']
            
            # Retrieve duplicate hosts with the same IP
            duplicate_hosts = Device.objects.filter(hostname=hostname).order_by('-hostname')[1:]

            # Keep the first instance and delete the duplicates
            for duplicate_host in duplicate_hosts:
                duplicate_host.delete()
        self.stdout.write(self.style.SUCCESS('Duplicates deleted successfully.'))


