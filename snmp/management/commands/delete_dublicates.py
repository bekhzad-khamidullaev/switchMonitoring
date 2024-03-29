from django.core.management.base import BaseCommand
from django.db import connection

from django.db.models import Count
from snmp.models import Switch

class Command(BaseCommand):
    help = 'Delete duplicate entries from the Switch model'

    def handle(self, *args, **options):
        duplicate_ips = Switch.objects.values('ip').annotate(count=Count('ip')).filter(count__gt=1)

        # Iterate over duplicate IPs
        for duplicate_ip in duplicate_ips:
            ip = duplicate_ip['ip']
            
            # Retrieve duplicate hosts with the same IP
            duplicate_hosts = Switch.objects.filter(ip=ip).order_by('-id')[1:]

            # Keep the first instance and delete the duplicates
            for duplicate_host in duplicate_hosts:
                duplicate_host.delete()
        self.stdout.write(self.style.SUCCESS('Duplicates deleted successfully.'))



