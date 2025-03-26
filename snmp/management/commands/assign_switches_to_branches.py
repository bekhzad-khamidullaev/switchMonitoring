from django.core.management.base import BaseCommand
from snmp.models import Switch, Ats

class Command(BaseCommand):
    help = 'Assign switches to branches based on their IP addresses'

    def handle(self, *args, **options):
        switches = Switch.objects.all()
        ats = Ats.objects.all()

        for switch in switches:
            switch_ip = switch.ip
            for branch in ats:
                if branch.contains_ip(switch_ip):
                    switch.branch = branch.branch
                    switch.ats = branch
                    switch.save()
                    self.stdout.write(self.style.SUCCESS(f'Switch {switch.id} assigned to branch {branch.name}'))
                    break
