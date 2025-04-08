from pysnmp.hlapi import *
from pysnmp.proto.rfc1902 import (
    Integer, OctetString, Counter64, Gauge32, TimeTicks,
    IpAddress, Bits, ObjectName, ObjectIdentifier, Unsigned32
)

from snmp.mib_loader import mib_view
import logging

logger = logging.getLogger("SNMP")

def resolve_object_identity(mib, var, index=None, fallback_oid=None):
    try:
        identity = ObjectIdentity(mib, var)
        if index:
            identity = identity.addAsn1MibSource().addMibSource().addIndex(index)
        identity = identity.resolveWithMib(mib_view)
        return identity
    except Exception as e:
        logger.warning(f"⚠️ Failed to resolve {mib}::{var}, fallback to OID: {fallback_oid}. Reason: {e}")
        if fallback_oid:
            return ObjectIdentity(fallback_oid)
        raise

def convert_snmp_value(value):
    """Converts SNMP types to Python-native types with extended support."""
    try:
        if isinstance(value, (Integer, Counter64, Gauge32, TimeTicks, Unsigned32)):
            return int(value)
        elif isinstance(value, OctetString):
            try:
                return str(value.prettyPrint())
            except Exception:
                return bytes(value).decode(errors='ignore')
        elif isinstance(value, IpAddress):
            return str(value.prettyPrint())  # IP address
        elif isinstance(value, Bits):
            return str(value.prettyPrint())  # usually string of bits or set
        elif isinstance(value, (ObjectIdentifier, ObjectName)):
            return str(value)
        elif hasattr(value, 'prettyPrint'):
            return str(value.prettyPrint())  # fallback for unknown types
        else:
            return str(value)
    except Exception as e:
        return f"[unreadable value: {e}]"

def snmp_get(ip, community, mib, var, index=None, fallback_oid=None):
    identity = resolve_object_identity(mib, var, index, fallback_oid)

    g = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),
        UdpTransportTarget((ip, 161), timeout=2, retries=2),
        ContextData(),
        ObjectType(identity)
    )

    for (errIndication, errStatus, errIndex, varBinds) in g:
        if errIndication or errStatus:
            logger.warning(f"[GET] SNMP Error from {ip}: {errIndication or errStatus.prettyPrint()}")
            return None
        for varBind in varBinds:
            return convert_snmp_value(varBind[1])
    return None

def snmp_walk(ip, community, mib, var, fallback_oid=None):
    identity = resolve_object_identity(mib, var, fallback_oid=fallback_oid)

    iterator = nextCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),
        UdpTransportTarget((ip, 161), timeout=2, retries=2),
        ContextData(),
        ObjectType(identity),
        lexicographicMode=False
    )

    result = []
    for (errIndication, errStatus, errIndex, varBinds) in iterator:
        if errIndication or errStatus:
            logger.warning(f"[WALK] SNMP Error from {ip}: {errIndication or errStatus.prettyPrint()}")
            break
        for varBind in varBinds:
            result.append((str(varBind[0]), convert_snmp_value(varBind[1])))
    return result
