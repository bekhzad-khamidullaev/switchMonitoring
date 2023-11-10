# from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Vendor
import logging
from pysnmp.hlapi import *
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_DESCRIPTION = "1.3.6.1.2.1.1.1.0"
OID_SYSTEM_HOSTNAME='1.3.6.1.2.1.1.5'
OID_SYSTEM_UPTIME='1.3.6.1.2.1.1.3'

def perform_snmpwalk(ip, oid):
    snmp_walk = getCmd(
        SnmpEngine(),
        CommunityData(SNMP_COMMUNITY),
        UdpTransportTarget((ip, 161)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    snmp_response = []
    for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
        if errorIndication:
            logger.error(f"SNMP error: {errorIndication}")
            sys.exit(1)
        for varBind in varBinds:
            snmp_response.append(str(varBind))
    return snmp_response


class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        selected_switches = Switch.objects.filter(status=True)
        vendors = Vendor.objects.all()
        models = SwitchModel.objects.all()

        for selected_switch in selected_switches:
            vendor_name = None
            model_name = None
            snmp_response = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_DESCRIPTION)
            if not snmp_response:
                logger.warning(f"No SNMP response received for IP address: {selected_switch.device_ip}")
                continue

                response = str(snmp_response[0]).strip().split()
                logger.info(response)
                selected_switch.device_hostname = response
                selected_switch.save()
                
            for vendor in vendors:
                vendor_name = vendor.name
                for model in models:
                    model_name = model.device_model
                    logger.info(f'Vendor name: {vendor_name} and device model: {model_name}')
                    
                    
                    snmp_response = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_DESCRIPTION)
                    if not snmp_response:
                        logger.warning(f"No SNMP response received for IP address: {selected_switch.device_ip}")
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

# def run_update_switch_status_inventory():
#     Command()
