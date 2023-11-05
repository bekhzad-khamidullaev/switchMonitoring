from pysnmp.hlapi import *
from .models import Switch, Olt

# Функция для получения значения по SNMP OID
def get_snmp_value(target_host, community, oid):
    errorIndication, errorStatus, errorIndex, varBinds = next(
        getCmd(SnmpEngine(),
               CommunityData(community),
               UdpTransportTarget((target_host, 161)),
               ContextData(),
               ObjectType(ObjectIdentity(oid)))
    )
    
    if errorIndication:
        print(errorIndication)
        return None
    elif errorStatus:
        print(f"{errorStatus} at {errorIndex}")
        return None
    else:
        for varBind in varBinds:
            return varBind[1]

oid = '.1.3.6.1.4.1.890.1.5.8.68.117.2.1.7'
# Функция для заполнения поля device_optical_info
def update_device_optical_info(device, oid):
    snmp_value = get_snmp_value(device.device_ip, device.device_snmp_community, oid)
    if snmp_value is not None:
        device.device_optical_info = int(snmp_value)
        device.save()

# Получение всех объектов Switch и обновление поля device_optical_info
switches = Switch.objects.all()
for switch in switches:
    update_device_optical_info(switch, switch.device_general_oid)

# Получение всех объектов Olt и обновление поля device_optical_info
olts = Olt.objects.all()
for olt in olts:
    update_device_optical_info(olt, olt.device_general_oid)
