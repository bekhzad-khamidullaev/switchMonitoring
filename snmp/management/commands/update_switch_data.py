# import ping3
# from django.core.management.base import BaseCommand
# from snmp.models import Switch
# from snmp.models import Vendor
# from snmp.models import SwitchModel
# # Import the necessary SNMP-related modules from pysnmp
# from pysnmp.hlapi import *

# def perform_snmpwalk(ip, oid):
#     # Create an SNMP request
#     snmp_walk = getCmd(
#         SnmpEngine(),
#         CommunityData('snmp2netread'),  # Replace 'public' with your community string
#         UdpTransportTarget((ip, 161)),  # Replace '161' with the SNMP port
#         ContextData(),
#         ObjectType(ObjectIdentity(oid)),
#     )

#     # Execute the SNMP walk and collect the response
#     snmp_response = []
#     for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
#         if errorIndication:
#             # Handle SNMP error
#             logger.info(f"SNMP error: {errorIndication}")
#         else:
#             for varBind in varBinds:
#                 snmp_response.append(str(varBind))

#     return snmp_response

# class Command(BaseCommand):
#     help = 'Update switch data'

#     def handle(self, *args, **options):
#         # Step 2: Query the snmp_switch table to select IP addresses
#         ip_addresses = Switch.objects.values_list('device_ip', flat=True)

#         for ip in ip_addresses:
#             # Step 3: Check if the host is alive using ping3
#             host_alive = ping3.ping(ip)

#             if host_alive is not None:
#                 # The host is reachable

#                 # Step 4: Update the status field to True
#                 switch = Switch.objects.get(device_ip=ip)
#                 switch.status = True
#                 switch.save()

#                 # Step 5: Select IP addresses where status is True
#                 selected_switches = Switch.objects.filter(status=True)

#                 for selected_switch in selected_switches:
#                     device_type = selected_switch.device_type
#                     if device_type:
#                         device_model = device_type.device_model
#                         if device_model:
#                             vendor_name = device_model.vendor.name
                        
#                         if device_type and device_model:
#                             vendor_name = device_model.vendor.name
                            
                    
#                     # Step 6: Send an SNMPwalk request with the OID '1.3.6.1.2.1.1.1.0' to the selected IP address
#                     # (You can use an SNMP library like pysnmp to perform SNMP operations)
#                     snmp_response = perform_snmpwalk(selected_switch.device_ip, '1.3.6.1.2.1.1.1.0')

#                     # Step 7: Check the response for containing the name from the snmp_vendor table
#                     vendor_name = selected_switch.device_type.device_model.vendor.name
#                     if vendor_name in snmp_response:
#                         # Step 8: Check if the response contains the snmp_switchmodel device_model field
#                         device_model_name = selected_switch.device_type.device_model.device_model
#                         if device_model_name in snmp_response:
#                             # Step 9: Update device_model_id, device_model_local, and device_hostname
#                             selected_switch.device_model_id = SwitchModel.objects.get(device_model=device_model_name).pk
#                             selected_switch.device_model_local = device_model_name
#                             selected_switch.device_hostname = device_model_name
#                             selected_switch.save()

import ping3
from django.core.exceptions import MultipleObjectsReturnedwa
from django.core.management.base import BaseCommand
from snmp.models import Switch
from snmp.models import Vendor
from snmp.models import SwitchModel
import logging

from pysnmp.hlapi import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IfaceInfo")


def perform_snmpwalk(ip, oid):
    # Create an SNMP request
    snmp_walk = getCmd(
        SnmpEngine(),
        CommunityData('snmp2netread'),
        UdpTransportTarget((ip, 161)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    # Execute the SNMP walk and collect the response
    snmp_response = []
    for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
        if errorIndication:
            # Handle SNMP error
            logger.info(f"SNMP error: {errorIndication}")
        else:
            for varBind in varBinds:
                snmp_response.append(str(varBind))

    return snmp_response

class Command(BaseCommand):
    help = 'Update switch data'

    def handle(self, *args, **options):
        # Step 2: Query the snmp_switch table to select IP addresses
        ip_addresses = Switch.objects.values_list('device_ip', flat=True)

        for ip in ip_addresses:
            # Step 3: Check if the host is alive using ping3
            host_alive = ping3.ping(ip)
            logger.info(host_alive)
            if host_alive is not None:
                # The host is reachable
                

                # Step 4: Update the status field to True
                switch = Switch.objects.get(device_ip=ip)
                snmp_response = perform_snmpwalk(switch.device_ip, '1.3.6.1.2.1.1.1.0')
                response = snmp_response.strip().split()
                logger.info(response)
                switch.status = True
                switch.save()

                # Step 5: Select IP addresses where status is True
                # selected_switches = Switch.objects.filter(status=True)

                # for selected_switch in selected_switches:
                #     device_type = selected_switch.device_type
                #     if device_type:
                #         device_model = selected_switch.device_model
                #         if device_model:
                #             vendor_name = device_model.vendor.name

                #     if device_type and device_model:
                #         # Step 6: Send an SNMPwalk request with the OID '1.3.6.1.2.1.1.1.0' to the selected IP address
                #         snmp_response = perform_snmpwalk(selected_switch.device_ip, '1.3.6.1.2.1.1.1.0')
                #         response = snmp_response.strip().split()
                #         logger.info(response)
                #         # Step 7: Check the response for containing the name from the snmp_vendor table
                #         vendor_name = device_model.vendor.name
                #         if vendor_name in response:
                #             # Step 8: Check if the response contains the snmp_switchmodel device_model field
                #             device_model_name = device_model.device_model
                #             if device_model_name in response:
                #                 # Step 9: Update device_model_id, device_model_local, and device_hostname
                #                 selected_switch.device_model_id = SwitchModel.objects.get(device_model=device_model_name).pk
                #                 selected_switch.device_model_local = device_model_name
                #                 selected_switch.device_hostname = device_model_name
                #                 logger.info(selected_switch)
                #                 logger.info(selected_switch.device_hostname)
                #                 logger.info(selected_switch.device_model)
                #                 selected_switch.save()
