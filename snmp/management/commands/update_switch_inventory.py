import logging
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.db.models import Count

from snmp.models import Ats, ManagedDevice, ManagedDeviceType
from .snmp import perform_snmpwalk

logger = logging.getLogger("SNMP RESPONSE")

OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'


def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


class Command(BaseCommand):
    help = 'Update switch inventory in one pass'

    def handle(self, *args, **options):
        snmp_community = settings.SNMP_DEFAULT_COMMUNITY_RO
        ats_list = list(Ats.objects.all())
        switch_models = list(ManagedDeviceType.objects.all())

        paginator = Paginator(ManagedDevice.objects.filter(status=True).order_by('-pk'), 10)
        for page_number in range(1, paginator.num_pages + 1):
            selected_switches = paginator.page(page_number)
            for selected_switch in selected_switches:
                hostname_resp = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_HOSTNAME, snmp_community)
                uptime_resp = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_UPTIME, snmp_community)
                if not hostname_resp or not uptime_resp:
                    logger.warning("No SNMP response for ip=%s", selected_switch.ip)
                    continue

                for ats in ats_list:
                    if ats.contains_ip(selected_switch.ip):
                        selected_switch.branch = ats.branch
                        selected_switch.ats = ats
                        break

                match_hostname = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', hostname_resp[0])
                if match_hostname:
                    selected_switch.hostname = match_hostname.group(1).strip()
                else:
                    logger.error("Unexpected hostname response for ip=%s", selected_switch.ip)
                    continue

                match_uptime = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', uptime_resp[0])
                if match_uptime:
                    selected_switch.uptime = convert_uptime_to_human_readable(match_uptime.group(1).strip())
                else:
                    logger.error("Unexpected uptime response for ip=%s", selected_switch.ip)
                    continue

                descr_resp = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_DESCRIPTION, snmp_community)
                if not descr_resp:
                    continue
                response_description = str(descr_resp[0]).strip().split()
                for db_model_instance in switch_models:
                    if db_model_instance.device_model in response_description:
                        selected_switch.model = db_model_instance
                        break

                selected_switch.save()

        duplicate_ips = ManagedDevice.objects.values('ip').annotate(count=Count('ip')).filter(count__gt=1)
        for duplicate_ip in duplicate_ips:
            ip = duplicate_ip['ip']
            duplicate_hosts = ManagedDevice.objects.filter(ip=ip).order_by('-id')[1:]
            for duplicate_host in duplicate_hosts:
                duplicate_host.delete()
