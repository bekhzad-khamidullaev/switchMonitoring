import logging

from snmp.services.snmp_client import SnmpClient, SnmpTarget


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SNMP RESPONSE")


def perform_snmpwalk(ip, oid, community):
    """Legacy helper retained for existing commands.

    Despite its name, this performs a single SNMP GET.

    `oid` can be either numeric OID or symbolic (e.g. 'SNMPv2-MIB::sysName.0').
    Returns a list of string lines similar to the old implementation.
    """
    try:
        client = SnmpClient(SnmpTarget(host=str(ip), community=community))
        val = client.get_one(oid)
        if val is None:
            return []
        # Some types (e.g. TimeTicks) prettyPrint into non-numeric format, but callers expect digits.
        try:
            rendered = str(int(val))
        except Exception:
            rendered = val.prettyPrint() if hasattr(val, 'prettyPrint') else str(val)
        return [f"{oid} = {rendered}"]
    except Exception as e:
        logger.error(f"Error during SNMP get: {e}")
        return []