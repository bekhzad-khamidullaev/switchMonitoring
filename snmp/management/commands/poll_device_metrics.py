from django.core.management.base import BaseCommand, CommandError

from snmp.models import Device
from snmp.services.polling.poller import poll_device_metrics


class Command(BaseCommand):
    help = 'Poll active metric subscriptions for one device or for all devices'

    def add_arguments(self, parser):
        parser.add_argument('--device-id', type=int, dest='device_id')

    def handle(self, *args, **options):
        device_id = options.get('device_id')

        if device_id:
            if not Device.objects.filter(pk=device_id).exists():
                raise CommandError(f'Device {device_id} not found')
            count = poll_device_metrics(device_id)
            self.stdout.write(self.style.SUCCESS(f'samples_saved={count} for device_id={device_id}'))
            return

        total = 0
        for did in Device.objects.values_list('id', flat=True):
            total += poll_device_metrics(did)

        self.stdout.write(self.style.SUCCESS(f'total_samples_saved={total}'))
