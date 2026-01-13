import time
import logging
from django.core.paginator import Paginator
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Ats
from snmp.services.snmp_client import SnmpClient, SnmpTarget
from django.db.models import Count

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_HOSTNAME = 'SNMPv2-MIB::sysName.0'
OID_SYSTEM_UPTIME = 'SNMPv2-MIB::sysUpTime.0'
OID_SYSTEM_DESCRIPTION = 'SNMPv2-MIB::sysDescr.0'


def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        switches_per_page = 10
        delay_seconds = 1

        while True:
            paginator = Paginator(Switch.objects.filter(status=True).order_by('-pk'), switches_per_page)

            for page_number in range(1, paginator.num_pages + 1):
                selected_switches = paginator.page(page_number)
                ats = Ats.objects.all()
                duplicate_ips = Switch.objects.values('ip').annotate(count=Count('ip')).filter(count__gt=1)
                for selected_switch in selected_switches:
                    SNMP_COMMUNITY = "snmp2netread"
                    client = SnmpClient(SnmpTarget(host=str(selected_switch.ip), community=SNMP_COMMUNITY))
                    sys_name = client.get_one(OID_SYSTEM_HOSTNAME)
                    sys_uptime = client.get_one(OID_SYSTEM_UPTIME)
                    for branch in ats:
                        if branch.contains_ip(selected_switch.ip):
                            selected_switch.ats = branch

                    if sys_name is None or sys_uptime is None:
                        logger.warning(f"No SNMP response received for IP address: {selected_switch.ip}")
                        continue

                    try:
                        selected_switch.hostname = sys_name.prettyPrint() if hasattr(sys_name, 'prettyPrint') else str(sys_name)
                    except Exception as e:
                        logger.error(f"Error processing hostname for {selected_switch.ip}: {e}")
                        continue

                    try:
                        selected_switch.uptime = convert_uptime_to_human_readable(int(sys_uptime))
                    except Exception as e:
                        logger.error(f"Error processing uptime for {selected_switch.ip}: {e}")
                        continue

                    sys_descr = client.get_one(OID_SYSTEM_DESCRIPTION)
                    if sys_descr is None:
                        continue
                    snmp_response_description = [sys_descr.prettyPrint() if hasattr(sys_descr, 'prettyPrint') else str(sys_descr)]
                    for duplicate_ip in duplicate_ips:
                        ip = duplicate_ip['ip']
                        
                        # Retrieve duplicate hosts with the same IP
                        duplicate_hosts = Switch.objects.filter(ip=ip).order_by('-id')[1:]

                        # Keep the first instance and delete the duplicates
                        for duplicate_host in duplicate_hosts:
                            duplicate_host.delete()
                    try:
                        response_description = str(snmp_response_description[0]).strip().split()
                        # logger.info(f"Response description for {selected_switch.ip}: {response_description}")

                        # Retrieve the SwitchModel instance based on your model relationships
                        
                        switch_models = SwitchModel.objects.all()
                        for db_model_instance in switch_models:
                            db_model = db_model_instance.device_model

                            if db_model in response_description:
                                selected_switch.model = db_model_instance
                                selected_switch.save()
                            else:
                                continue
                    except Exception as e:
                        logger.error(f"Error processing SNMP response for {selected_switch.ip}: {e}")
                        continue

            time.sleep(delay_seconds)

if __name__ == '__main__':
    Command().handle()
