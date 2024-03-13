import time
import logging
import re
from django.core.paginator import Paginator
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel
from .snmp import perform_snmpwalk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'


def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        switches_per_page = 10  # Adjust as needed
        delay_seconds = 1  # Adjust as needed

        while True:
            paginator = Paginator(Switch.objects.filter(status=True).order_by('last_update'), switches_per_page)

            for page_number in range(1, paginator.num_pages + 1):
                selected_switches = paginator.page(page_number)

                for selected_switch in selected_switches:
                    SNMP_COMMUNITY = "snmp2netread"
                    snmp_response_hostname = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_HOSTNAME, SNMP_COMMUNITY)
                    snmp_response_uptime = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_UPTIME, SNMP_COMMUNITY)

                    if not snmp_response_hostname or not snmp_response_uptime:
                        logger.warning(f"No SNMP response received for IP address: {selected_switch.ip}")
                        continue

                    try:
                        match_hostname = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', snmp_response_hostname[0])
                        if match_hostname:
                            selected_switch.hostname = match_hostname.group(1).strip()
                            logger.info(f"Hostname updated for {selected_switch.ip}: {selected_switch.hostname}")
                        else:
                            raise ValueError(f"Unexpected SNMP response format for hostname: {snmp_response_hostname[0]}. Response: {snmp_response_hostname}")
                    except Exception as e:
                        logger.error(f"Error processing hostname for {selected_switch.ip}: {e}")
                        continue

                    try:
                        match_uptime = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', snmp_response_uptime[0])
                        if match_uptime:
                            selected_switch.uptime = convert_uptime_to_human_readable(match_uptime.group(1).strip())
                            logger.info(f"Uptime updated for {selected_switch.ip}: {selected_switch.uptime}")
                        else:
                            raise ValueError(f"Unexpected SNMP response format for uptime: {snmp_response_uptime[0]}. Response: {snmp_response_uptime}")
                    except Exception as e:
                        logger.error(f"Error processing uptime for {selected_switch.ip}: {e}")
                        continue

                    selected_switch.save()

                    snmp_response_description = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_DESCRIPTION, SNMP_COMMUNITY)
                    if not snmp_response_description:
                        logger.warning(f"No SNMP response received for IP address: {selected_switch.ip}")
                        continue

                    try:
                        response_description = str(snmp_response_description[0]).strip().split()
                        # logger.info(f"Response description for {selected_switch.ip}: {response_description}")

                        # Retrieve the SwitchModel instance based on your model relationships
                        db_model_instance = SwitchModel.objects.get(pk=selected_switch.model.id)
                        db_model = db_model_instance.device_model

                        if db_model in response_description:
                            selected_switch.model = db_model_instance
                            selected_switch.save()
                            logger.info(f"Updated device_model for switch {selected_switch.hostname} to {db_model}")
                        else:
                            logger.warning(f"Device model name {db_model} not found in SNMP response for switch {selected_switch.hostname}")
                    except Exception as e:
                        logger.error(f"Error processing SNMP response for {selected_switch.ip}: {e}")
                        logger.error(f"SNMP Response for {selected_switch.ip}: {snmp_response_description}")
                        continue

            time.sleep(delay_seconds)

if __name__ == '__main__':
    Command().handle()
