from background_task import background
from django.core.management.base import BaseCommand
from snmp.models import Switch, SwitchModel, Vendor
import logging
from pysnmp.hlapi import *
import sys, os
from django.core.wsgi import get_wsgi_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

from snmp.models import Switch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ICMP RESPONSE")


SNMP_COMMUNITY = "snmp2netread"
OID_SYSTEM_DESCRIPTION = "1.3.6.1.2.1.1.1.0"

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


def update_switch_inventory_main():
    selected_switches = Switch.objects.filter(status=True)
    vendors = Vendor.objects.all()
    models = SwitchModel.objects.all()

    for selected_switch in selected_switches:
        vendor_name = None
        model_name = None
        for vendor in vendors:
            vendor_name = vendor.name
            for model in models:
                model_name = model.device_model
                logger.info(f'Vendor name: {vendor_name} and device model: {model_name}')
                    
                    
                snmp_response = perform_snmpwalk(selected_switch.device_ip, OID_SYSTEM_DESCRIPTION)
                if not snmp_response:
                    logger.warning(f"No SNMP response received for IP address: {selected_switch.device_ip}")
                    continue


if __name__ == "__main__":
    update_switch_inventory_main()
