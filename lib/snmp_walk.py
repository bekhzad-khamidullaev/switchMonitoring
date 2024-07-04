from pysnmp.hlapi import *

def perform_snmpwalk(ip, oid, community):
    try:
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # SNMP v2c
            UdpTransportTarget((ip, 161), timeout=2, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False  # Ensures the walk is limited to the specified OID tree
        )

        snmp_response = []
        for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if errorIndication:
                print(f"Error: {errorIndication}")
                break
            elif errorStatus:
                print(f"Error: {errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}")
                break
            else:
                for varBind in varBinds:
                    oid_str, value = varBind
                    snmp_response.append(int(value))  # Convert value to integer
        return snmp_response
    except Exception as e:
        print(f"Exception: {e}")
        return []