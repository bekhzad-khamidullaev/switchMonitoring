import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

from monitoring.models import Device, DeviceModel, Vendor, Interface

logger = logging.getLogger(__name__)

SYS_DESCR = '1.3.6.1.2.1.1.1.0'
SYS_OBJECT_ID = '1.3.6.1.2.1.1.2.0'
IF_NUMBER = '1.3.6.1.2.1.2.1.0'
IF_SPEED = '1.3.6.1.2.1.2.2.1.5'
IF_ADMIN_STATUS = '1.3.6.1.2.1.2.2.1.7'
IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'


def snmp_get(ip: str, community: str, oid: str):
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((ip, 161), timeout=2, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )
    error_indication, error_status, error_index, var_binds = next(iterator)
    if error_indication or error_status:
        return None
    return var_binds[0][1].prettyPrint()


def detect_model(device: Device):
    sysobj = snmp_get(device.ip, device.community, SYS_OBJECT_ID)
    if not sysobj:
        return
    model = DeviceModel.objects.filter(sys_object_id=sysobj).first()
    if model:
        if device.model_id != model.id:
            device.model = model
            device.save(update_fields=["model"])
    else:
        descr = snmp_get(device.ip, device.community, SYS_DESCR) or ''
        vendor_name = descr.split()[0] if descr else 'Unknown'
        vendor, _ = Vendor.objects.get_or_create(name=vendor_name)
        model = DeviceModel.objects.create(vendor=vendor, name=descr, sys_object_id=sysobj, max_ports=int(snmp_get(device.ip, device.community, IF_NUMBER) or 0))
        device.model = model
        device.save(update_fields=["model"])


def update_interfaces(device: Device):
    if not device.model:
        return
    port_count = device.model.max_ports or int(snmp_get(device.ip, device.community, IF_NUMBER) or 0)
    for idx in range(1, port_count + 1):
        port, _ = Interface.objects.get_or_create(device=device, index=idx)
        speed = snmp_get(device.ip, device.community, f"{IF_SPEED}.{idx}")
        admin = snmp_get(device.ip, device.community, f"{IF_ADMIN_STATUS}.{idx}")
        oper = snmp_get(device.ip, device.community, f"{IF_OPER_STATUS}.{idx}")
        port.speed = int(speed) if speed else None
        port.admin_status = admin == '1'
        port.oper_status = oper == '1'
        port.save()


class Command(BaseCommand):
    help = 'Poll devices and update port information'

    def handle(self, *args, **options):
        for device in Device.objects.all():
            detect_model(device)
            update_interfaces(device)
            device.last_polled = timezone.now()
            device.status = True
            device.save(update_fields=["last_polled", "status"])
            self.stdout.write(self.style.SUCCESS(f"Updated {device}"))
