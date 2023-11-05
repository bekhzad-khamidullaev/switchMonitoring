from pysnmp.hlapi import *

# Определение параметров SNMP
ip_address = '10.101.33.15'
community_string = 'snmp2netread'

# OID для состояния оптических портов (пример)
optical_port_status_oid = '.1.3.6.1.4.1.890.1.5.8.68.117.2.1.7'

# Функция для получения информации о состоянии оптических портов
def get_optical_port_status(ip_address, community_string):
    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(
            SnmpEngine(),
            CommunityData(community_string),
            UdpTransportTarget((ip_address, 161)),
            ContextData(),
            ObjectType(ObjectIdentity(optical_port_status_oid)),
        )
    )

    if errorIndication:
        print(f"Ошибка: {errorIndication}")
    else:
        if errorStatus:
            print(f"Ошибка: {errorStatus.prettyPrint()}")
        else:
            for varBind in varBinds:
                print(f"OID: {varBind[0]}, Значение: {varBind[1]}")

if __name__ == "__main__":
    get_optical_port_status(ip_address, community_string)
