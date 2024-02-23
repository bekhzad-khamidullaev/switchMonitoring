import time
from django.core.paginator import Paginator
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel
import logging
from pysnmp.hlapi import *
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'



def perform_snmpwalk(ip, oid, SNMP_COMMUNITY):
    try:
        snmp_walk = getCmd(
            SnmpEngine(),
            CommunityData(SNMP_COMMUNITY),
            UdpTransportTarget((ip, 161), timeout=2, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

        snmp_response = []
        for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
            if errorIndication:
                logger.error(f"SNMP error: {errorIndication}")
                continue
            for varBind in varBinds:
                snmp_response.append(str(varBind))
        return snmp_response
    except TimeoutError:
        logger.warning(f"SNMP timeout for IP address: {ip}")
        return []
    except Exception as e:
        logger.error(f"Error during SNMP walk: {e}")
        return []


def convert_uptime_to_human_readable(uptime_in_hundredths):
    total_seconds = int(uptime_in_hundredths) / 100.0
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    return f"{int(days)} days, {int(hours)} hours"


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        switches_per_page = 10  # Adjust as needed
        delay_seconds = 3600  # Adjust as needed

        while True:
            # Use Paginator to get switches with pagination
            paginator = Paginator(Switch.objects.filter(status=True).order_by('pk'), switches_per_page)

            for page_number in range(1, paginator.num_pages + 1):
                selected_switches = paginator.page(page_number)

                for selected_switch in selected_switches:
                    SNMP_COMMUNITY = "snmp2netread"
                    # SNMP_COMMUNITY = selected_switch.snmp_community_ro
                    snmp_response_hostname = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_HOSTNAME, SNMP_COMMUNITY)
                    snmp_response_uptime = perform_snmpwalk(selected_switch.ip, OID_SYSTEM_UPTIME, SNMP_COMMUNITY)

                    if not snmp_response_hostname or not snmp_response_uptime:
                        logger.warning(f"No SNMP response received for IP address: {selected_switch.ip}")
                        continue

                    # Process hostname
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

                    # Process uptime
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
                        logger.info(f"Response description for {selected_switch.ip}: {response_description}")

                        for model in SwitchModel.objects.all():
                            device_model = model.device_model
                            logger.info(f'device model: {device_model}')

                            if device_model in response_description:
                                selected_switch.model = model
                                selected_switch.save()
                                logger.info(f"Updated device_model for switch {selected_switch.hostname} to {device_model}")
                                break
                        else:
                            logger.warning(f"Device model name {device_model} not found in SNMP response for switch {selected_switch.hostname}")
                    except Exception as e:
                        logger.error(f"Error processing SNMP response for {selected_switch.ip}: {e}")
                        logger.error(f"SNMP Response for {selected_switch.ip}: {snmp_response_description}")
                        continue

            time.sleep(delay_seconds)

if __name__ == '__main__':
    Command().handle()
