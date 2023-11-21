from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel
import logging
from pysnmp.hlapi import *
import sys
import re
from datetime import timedelta


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_DESCRIPTION = "iso.3.6.1.2.1.1.1.0"
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'


def perform_snmpwalk(ip, oid):
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
        while True:
            selected_switches = Switch.objects.filter(status=True).order_by('pk')
            models = SwitchModel.objects.all()
            
            for selected_switch in selected_switches:
                snmp_response_hostname = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_HOSTNAME)
                snmp_response_uptime = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_UPTIME)
                
                if not snmp_response_hostname:
                    logger.warning(f"No SNMP response (uptime and hostname) received for IP address: {selected_switch.device_ip}")
                    continue

                match1 = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', snmp_response_hostname[0])
                if match1:
                    hostname = match1.group(1).strip()
                    logger.info(hostname)
                else:
                    logger.warning(f"Unexpected SNMP response format for hostname: {snmp_response_hostname[0]}")
                    continue

                match2 = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', snmp_response_uptime[0])
                logger.info(match2)
                if match2:
                    uptime = convert_uptime_to_human_readable(match2.group(1).strip())
                    logger.info(uptime)
                else:
                    logger.warning(f"Unexpected SNMP response format for uptime: {snmp_response_uptime[0]}")
                    continue

                selected_switch.device_hostname = hostname
                selected_switch.uptime = uptime
                selected_switch.save()

                for model in models:
                    device_model = model.device_model
                    logger.info(f'device model: {device_model}')             
                    snmp_response = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_DESCRIPTION)
                    
                    if not snmp_response:
                        logger.warning(f"No SNMP response (vendor) received for IP address: {selected_switch.device_ip}")
                        continue

                    response = str(snmp_response[0]).strip().split()
                    logger.info(response)

                    if device_model in response:
                        selected_switch.device_model = model
                        selected_switch.save()
                        logger.info(f"Updated device_model for switch {selected_switch.device_hostname} to {device_model}")
                        break
                else:
                    logger.warning(f"Device model name {device_model} not found in SNMP response for switch {selected_switch.device_hostname}")
