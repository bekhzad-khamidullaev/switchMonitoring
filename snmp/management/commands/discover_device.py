from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from snmp.models import ManagedDevice
from snmp.services.discovery.pipeline import run_device_discovery
from snmp.services.discovery.read_base_snmp import SnmpReadError


class Command(BaseCommand):
    help = 'Run SNMP discovery for a device and populate Device/Interface tables'

    def add_arguments(self, parser):
        parser.add_argument('--ip', dest='ip', help='Device IP address')
        parser.add_argument('--managed-device-id', dest='managed_device_id', type=int, help='Existing managed device ID')
        parser.add_argument('--switch-id', dest='managed_device_id_legacy', type=int, help='Deprecated alias for --managed-device-id')
        parser.add_argument(
            '--community',
            dest='community',
            default=settings.SNMP_DEFAULT_COMMUNITY_RO,
            help='SNMP community string',
        )
        parser.add_argument('--timeout', dest='timeout', type=int, default=2)
        parser.add_argument('--retries', dest='retries', type=int, default=1)

    def handle(self, *args, **options):
        ip = options.get('ip')
        managed_device = None
        managed_device_id = options.get('managed_device_id') or options.get('managed_device_id_legacy')

        if managed_device_id:
            try:
                managed_device = ManagedDevice.objects.get(pk=managed_device_id)
            except ManagedDevice.DoesNotExist as exc:
                raise CommandError(f"Managed device with id={managed_device_id} not found") from exc
            ip = ip or managed_device.ip

        if not ip:
            raise CommandError('Provide --ip or --managed-device-id')

        try:
            result = run_device_discovery(
                ip=str(ip),
                community=options['community'],
                managed_device=managed_device,
                timeout=options['timeout'],
                retries=options['retries'],
            )
        except SnmpReadError as exc:
            raise CommandError(f'Discovery failed: {exc}') from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Discovery done: device_id={result['device_id']} profile_id={result['profile_id']} "
                f"interfaces={result['interfaces_count']}"
            )
        )
