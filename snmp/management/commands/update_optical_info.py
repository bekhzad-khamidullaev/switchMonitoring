from django.core.management.base import BaseCommand

from snmp.lib.update_port_info import SNMPUpdater
from snmp.models import Device
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update device optical data'

    def handle(self, *args, **options):
        selected_switches = (
            Device.objects.filter(status=True)
            .select_related('device_type')
            .prefetch_related('interfaces')
            .order_by('-pk')
        )
        for selected_switch in selected_switches:
            try:
                updater = SNMPUpdater(selected_switch, selected_switch.effective_snmp_community())
                updater.update_switch_data()
            except Exception:
                logger.exception(
                    "Failed to update optical info for device_id=%s ip=%s",
                    selected_switch.pk,
                    selected_switch.ip,
                )
