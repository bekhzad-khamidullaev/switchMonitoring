#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import logging
from pysnmp.hlapi import *
from pysnmp import debug
from pysnmp.entity.rfc3413.oneliner import cmdgen
from snmp.models import Switch
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
settings.configure()

# Constants for SNMP OIDs
IF_ADMIN_STATUS = '7'
IF_OPER_STATUS = '8'
IF_IN_OCTETS = '10'
IF_OUT_OCTETS = '16'

# Set debug output to verbose for PySNMP
debug.setLogger(debug.Debug('all'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename="./log.txt",
    format='%(asctime)s %(name)s.%(funcName)s +%(lineno)s: %(levelname)-8s [%(process)d] %(message)s',
)
logger = logging.getLogger("./log.txt")


class Device:
    def __init__(self, ip_switch, ro_community, oid_mt, port=161):
        self.ip = ip_switch
        self.ro = ro_community
        self.oid = oid_mt
        self.port = port
        self.if_oids = [IF_ADMIN_STATUS, IF_OPER_STATUS, IF_IN_OCTETS, IF_OUT_OCTETS]
        self.types_response = {
            IF_ADMIN_STATUS: 'ifAdminStatus',
            IF_OPER_STATUS: 'ifOperStatus',
            IF_IN_OCTETS: 'ifInOctets',
            IF_OUT_OCTETS: 'ifOutOctets',
        }
        self.part_mt_oid = re.search(r"(\d\.\d\.\d\.\d\.\d\.\d\.)(?P<part_mt>.*?)$", self.oid).group('part_mt')
        self.re_mt = re.compile(f'\S+({self.part_mt_oid})\.(?P<port>\d{1, 2})\.(?P<sign>\d+)',
                                re.MULTILINE | re.DOTALL)
        self.re_if = re.compile("\S+\:\:\S+2\.2\.1\.(?P<key>\d+)\.(?P<port>\d{1,2})$",
                                re.MULTILINE | re.DOTALL)
        self.result = {}

    def get_ifwalk(self) -> dict:
        """
        Retrieve information from SNMP-enabled devices.
        :return: Dictionary containing device information.
        """
        oids_form = [(oid_if,) for oid_if in self.if_oids]
        oids_form.extend((self.oid,))

        try:
            cmdGen = cmdgen.CommandGenerator()
            errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.nextCmd(
                cmdgen.CommunityData(self.ro, mpModel=1),
                cmdgen.UdpTransportTarget((self.ip, self.port)),
                *oids_form
            )

            if errorIndication:
                raise Exception(f"errorIndication: {errorIndication}")
            if errorStatus:
                raise Exception(f"errorStatus: {errorStatus.prettyPrint(), errorIndex and varBindTable[-1][int(errorIndex) - 1] or '?'}")

            # Process the SNMP responses and populate the result dictionary
            for varBindTableRow in varBindTable:
                for name, val in varBindTableRow:
                    founds_mt_responce = self.re_mt.search(name.prettyPrint())
                    if founds_mt_responce is not None:
                        port = founds_mt_responce.group("port")
                        self.result.setdefault('sign', {})[port] = founds_mt_responce.group("sign")
                        self.result.setdefault('link', {})[port] = val.prettyPrint()

                    found_if_responce = self.re_if.search(name.prettyPrint())
                    if found_if_responce is not None:
                        port = found_if_responce.group('port')
                        type_response = self.types_response.get(found_if_responce.group('key'))
                        if (type_response in ['ifAdminStatus', 'ifOperStatus']) and (val.prettyPrint() == '1'):
                            status = 'up' if val.prettyPrint() == '1' else 'down'
                            self.result.setdefault(type_response, {})[port] = status
                            continue
                        self.result.setdefault(type_response, {})[port] = val.prettyPrint()

        except Exception as ex:
            logger.error(f"An error occurred: {ex}")

        return self.result


if __name__ == "__main":
    # Fetch switches from the database and iterate through them
    switches = Switch.objects.all()
    for switch in switches:
        # Initialize and query each device
        device = Device(switch, switch.device_snmp_community, switch.device_general_oid)
        device_info = device.get_ifwalk()
        # Process the device information as needed
        print(device_info)  # Example: Print the information
