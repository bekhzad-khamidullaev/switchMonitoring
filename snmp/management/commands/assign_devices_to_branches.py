from django.core.management.base import BaseCommand

from snmp.models import Ats, Device


class Command(BaseCommand):
    help = 'Assign devices to groups/subgroups based on their IP addresses'

    def handle(self, *args, **options):
        devices = Device.objects.all()
        ats_list = Ats.objects.all()

        for device in devices:
            device_ip = device.ip
            for ats in ats_list:
                if ats.contains_ip(device_ip):
                    device.group = ats.group
                    device.subgroup = ats
                    device.save()
                    self.stdout.write(self.style.SUCCESS(f'Device {device.id} assigned to subgroup {ats.name}'))
                    break
