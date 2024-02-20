from pysnmp.hlapi import *
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


def perform_snmpwalk(ip, oid, community):
    try:
        snmp_walk = getCmd(
            SnmpEngine(),
            CommunityData(community),
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