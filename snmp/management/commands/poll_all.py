from django.core.management.base import BaseCommand
from snmp.models import Switch
from snmp.tasks.poll_ports import poll_ports

class Command(BaseCommand):
    help = "Poll all switches' ports"

    def handle(self, *args, **kwargs):
        for sw in Switch.objects.all():
            self.stdout.write(f"Polling {sw}")
            poll_ports(sw)
