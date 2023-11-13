# from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Vendor
import logging
from pysnmp.hlapi import *
import sys, re
from datetime import timedelta



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_DESCRIPTION ="1.3.6.1.2.1.1.1"
OID_SYSTEM_HOSTNAME='iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME='iso.3.6.1.2.1.1.3.0'

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


# def convert_uptime_to_human_readable(uptime_in_hundredths):
#     total_seconds = int(uptime_in_hundredths) / 100.0
#     uptime_timedelta = timedelta(seconds=total_seconds)
    
#     years = uptime_timedelta.days // 365
#     months = (uptime_timedelta.days % 365) // 30
#     days = uptime_timedelta.days % 30
#     hours, remainder = divmod(uptime_timedelta.seconds, 3600)
#     minutes, seconds = divmod(remainder, 60)

#     return f"{years} years, {months} months, {days} days, {hours} hours, {minutes} minutes, {seconds} seconds"

class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        selected_switches = Switch.objects.filter(status=True)
        vendors = Vendor.objects.all()
        models = SwitchModel.objects.all()

        for selected_switch in selected_switches:
            vendor_name = None
            model_name = None
            snmp_response_hostname = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_HOSTNAME)
            snmp_response_uptime = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_UPTIME)
            # logger.info(f'{snmp_response_hostname} ================== {snmp_response_uptime}')
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

                # uptime = match2.group(1).strip()
                # logger.info(uptime)
            else:
                logger.warning(f"Unexpected SNMP response format for uptime: {snmp_response_uptime[0]}")
                continue


            selected_switch.device_hostname = hostname
            selected_switch.uptime = uptime
            selected_switch.save()
                
            for vendor in vendors:
                vendor_name = vendor.name
                for model in models:
                    model_name = model.device_model
                    logger.info(f'Vendor name: {vendor_name} and device model: {model_name}')             
                    snmp_response = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_DESCRIPTION)
                    if not snmp_response:
                        logger.warning(f"No SNMP response (vendor) received for IP address: {selected_switch.device_ip}")
                        continue

                    response = str(snmp_response[0]).strip().split()
                    logger.info(response)
                    if vendor_name in response:
                        if model_name in response:
                            selected_switch.device_model_local = model_name
                            selected_switch.save()
                            logger.info(f"Updated device_model for switch {selected_switch.device_hostname} to {model_name}")
                        else:
                            logger.warning(f"Device model name {model_name} not found in SNMP response for switch {selected_switch.device_hostname}")
                    else:
                        logger.warning(f"Vendor name {vendor_name} not found in SNMP response for switch {selected_switch.device_hostname}")
                    
                    
                else:
                    logger.warning(f'Skipping switch {selected_switch.id} due to missing vendor for {model_name}')
                    continue

