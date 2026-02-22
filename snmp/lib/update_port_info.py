from pysnmp.hlapi import *
from pysnmp import error
import math
from django.core.paginator import Paginator
from django.utils import timezone
from ..models import Mac, Device, DeviceNeighbor, DevicePort
from ..services.metrics.interface_filters import is_eligible_optical_ethernet
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
UNKNOWN_TEXT_VALUES = {'', 'unknown', 'n/a', 'na', '-', 'none', 'null'}

def mw_to_dbm(mw):
    if mw > 0:
        mw /= 1000
        dbm = 10 * math.log10(mw)
        return dbm
    else:
        return float('nan')



class SNMPUpdater:
    def __init__(self, selected_switch, snmp_community):
        self.selected_switch = selected_switch
        model_name = None
        raw_model = getattr(selected_switch, 'model', None)
        if hasattr(raw_model, 'device_model'):
            model_name = raw_model.device_model
        elif isinstance(raw_model, str):
            raw_model_normalized = raw_model.strip()
            if raw_model_normalized.lower() not in UNKNOWN_TEXT_VALUES:
                model_name = raw_model_normalized
        if model_name is None and getattr(selected_switch, 'device_type_id', None) and getattr(selected_switch, 'device_type', None):
            model_name = selected_switch.device_type.device_model
        self.model = model_name
        self.ip = selected_switch.ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()

    def get_snmp_oids(self):
        if self.model == 'MES3500-24S':
            return (
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.4.{port}',
            )
        elif self.model == 'MES2428':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2408':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2428B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES2408B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.{port}.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.{port}',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.{port}',
            )
        elif self.model == 'MES3500-24':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.{port}',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.{port}',
            )
        elif self.model == 'MES3500-10':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.{port}.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.{port}',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.{port}',
            )
        elif self.model == 'GS3700-24HP':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.{port}',
            )
        elif self.model == 'MES1124MB':
            return (
                'iso.3.6.1.4.1.89.90.1.2.1.3.{port}.8',
                'iso.3.6.1.4.1.89.90.1.2.1.3.{port}.9',
                'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5',
                '',
            )
        elif self.model == 'MGS3520-28':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.{port}.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.{port}',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.{port}',
            )
        elif self.model == 'SNR-S2985G-24TC':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',

            )
        elif self.model == 'SNR-S2985G-8T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',
            )
        elif self.model == 'SNR-S2982G-24T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.{port}',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.{port}',
                '',
                '',
            )
        elif self.model == 'T2600G-28TS':
            return (
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.5.{port}',
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.6.{port}',
                '',
                '',
            )
        elif self.model == 'S3328TP-SI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.{port}',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.{port}',
                '',
                '',
            )
        elif self.model == 'S3328TP-EI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.{port}',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.{port}',
                '',
                '',
            )
        else:
            return ('iso.3.6.1.4.1.2011.5.14.6.4.1.4.{port}',
                    'iso.3.6.1.4.1.2011.5.14.6.4.1.5.{port}',
                    None,
                    None)

    def perform_snmpwalk(self, oid):
        try:
            snmp_walk = getCmd(
                SnmpEngine(),
                CommunityData(self.snmp_community),
                UdpTransportTarget((self.ip, 161), timeout=2, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )

            snmp_response = []
            for (errorIndication, errorStatus, errorIndex, varBinds) in snmp_walk:
                if errorIndication:
                    continue
                if varBinds:
                    for varBind in varBinds:
                        snmp_response.append(str(varBind))
            return snmp_response
        except TimeoutError:
            return []
        except Exception as e:
            return []
    

    def update_switch_data(self):
        switch = self.selected_switch
        eligible_interfaces = [
            iface for iface in switch.interfaces.all()
            if is_eligible_optical_ethernet(iface)
        ]
        eligible_ports = {iface.if_index for iface in eligible_interfaces}
        DevicePort.objects.filter(managed_device=switch).exclude(port__in=eligible_ports).update(
            rx_signal=None,
            tx_signal=None,
            sfp_vendor=None,
            part_number=None,
        )
        if not eligible_interfaces:
            switch.tx_signal = None
            switch.rx_signal = None
            switch.sfp_vendor = None
            switch.part_number = None
            switch.save(update_fields=['tx_signal', 'rx_signal', 'sfp_vendor', 'part_number', 'updated'])
            return

        first_signals = None
        now = timezone.now()
        for iface in eligible_interfaces:
            port_index = iface.if_index
            tx_oid = self.TX_SIGNAL_OID.replace('{port}', str(port_index)) if self.TX_SIGNAL_OID else None
            rx_oid = self.RX_SIGNAL_OID.replace('{port}', str(port_index)) if self.RX_SIGNAL_OID else None
            vendor_oid = self.SFP_VENDOR_OID.replace('{port}', str(port_index)) if self.SFP_VENDOR_OID else None
            part_oid = self.PART_NUMBER_OID.replace('{port}', str(port_index)) if self.PART_NUMBER_OID else None

            tx_raw = self.perform_snmpwalk(tx_oid) if tx_oid else []
            rx_raw = self.perform_snmpwalk(rx_oid) if rx_oid else []
            tx_signal = self.extract_value(tx_raw)
            rx_signal = self.extract_value(rx_raw)
            parsed_tx, parsed_rx = self.parse_signals(tx_signal, rx_signal)

            sfp_vendor = self.extract_value(self.perform_snmpwalk(vendor_oid)) if vendor_oid else None
            part_number = self.extract_value(self.perform_snmpwalk(part_oid)) if part_oid else None

            port_defaults = {
                'name': iface.if_name or f"Port {port_index}",
                'alias': iface.if_alias or '',
                'description': '',
                'speed': 1000,
                'duplex': 1,
                'admin': 1,
                'oper': 1,
                'lastchange': 0,
                'discards_in': 0,
                'discards_out': 0,
                'mac_count': 0,
                'pvid': 0,
                'port_tagged': '',
                'port_untagged': '',
                'data': now,
                'oct_in': 0,
                'oct_out': 0,
            }
            port_obj, _ = DevicePort.objects.get_or_create(
                managed_device=switch,
                port=port_index,
                defaults=port_defaults,
            )
            port_obj.name = iface.if_name or port_obj.name or f"Port {port_index}"
            port_obj.alias = iface.if_alias or ''
            port_obj.data = now
            port_obj.tx_signal = parsed_tx
            port_obj.rx_signal = parsed_rx
            port_obj.sfp_vendor = sfp_vendor
            port_obj.part_number = part_number
            port_obj.save(update_fields=[
                'name',
                'alias',
                'data',
                'tx_signal',
                'rx_signal',
                'sfp_vendor',
                'part_number',
            ])

            if first_signals is None and (parsed_tx is not None or parsed_rx is not None):
                first_signals = (parsed_tx, parsed_rx, sfp_vendor, part_number)

        if first_signals is not None:
            switch.tx_signal, switch.rx_signal, switch.sfp_vendor, switch.part_number = first_signals
        else:
            switch.tx_signal = None
            switch.rx_signal = None
            switch.sfp_vendor = None
            switch.part_number = None
        switch.save(update_fields=['tx_signal', 'rx_signal', 'sfp_vendor', 'part_number', 'updated'])

    def parse_signals(self, tx_val, rx_val):
        parsed_tx = None
        parsed_rx = None
        model = self.model or ''
        try:
            if '3500' in model or 'GS3700' in model or 'MGS3520-28' in model:
                parsed_tx = round(float(tx_val), 2) / 100.0 if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) / 100.0 if rx_val is not None else None
            elif '3328' in model or 'T2600G' in model:
                parsed_tx = round(mw_to_dbm(float(tx_val)), 2) if tx_val is not None else None
                parsed_rx = round(mw_to_dbm(float(rx_val)), 2) if rx_val is not None else None
            elif 'SNR' in model:
                parsed_tx = round(float(tx_val), 2) if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) if rx_val is not None else None
            else:
                parsed_tx = round(float(tx_val), 2) / 1000.0 if tx_val is not None else None
                parsed_rx = round(float(rx_val), 2) / 1000.0 if rx_val is not None else None
        except (ValueError, TypeError):
            pass
        return parsed_tx, parsed_rx

    def extract_value(self, snmp_response):
        if snmp_response and len(snmp_response) > 0:
            value_str = snmp_response[0].split('=')[-1].strip()
            return value_str if value_str != 'None' else None
        return None
    
class PortsInfo():
    
    def snmp_get(self, ip, community, oid):
        try:
            logger.debug(f"Performing SNMP get for OID: {oid}")
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(SnmpEngine(),
                    CommunityData(community),
                    UdpTransportTarget((ip, 161)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)))
            )

            if errorIndication:
                logger.error(f"SNMP Get Error: {errorIndication}")
                return None
            elif errorStatus:
                if isinstance(errorStatus, error.InconsistentValueError):
                    logger.warning(f"SNMP Get Warning: {errorStatus}")
                    # Handle InconsistentValueError gracefully, e.g., skip this OID
                    return None
                else:
                    logger.error(f"SNMP Get Status: {errorStatus.prettyPrint()}, Index: {errorIndex}")
                    return None
            else:
                value = varBinds[0][1].prettyPrint()
                logger.debug(f"SNMP Get Response - Value: {value}")
                return value
        except Exception as e:
            logger.exception(f"Error during SNMP Get: {e}")
            return None


    def create_switch_ports(self, switch):
        ip = switch.ip
        community = switch.snmp_community_ro

        # Replace the following with the actual SNMP OIDs for port information
        port_oids = {
            'speed': '.1.3.6.1.2.1.2.2.1.5',
            'duplex': '.1.3.6.1.2.1.10.7.2.1.19',
            # Add more port-related OIDs as needed
        }

        max_ports = switch.model.max_ports

        for port_num in range(1, max_ports + 1):
            port_speed_oid = f'{port_oids["speed"]}.{port_num}'
            port_duplex_oid = f'{port_oids["duplex"]}.{port_num}'

            # Perform SNMP queries for port information
            speed = self.snmp_get(ip, community, port_speed_oid)
            duplex = self.snmp_get(ip, community, port_duplex_oid)

            # Set default values for speed if SNMP data is not available
            speed = int(speed) if speed is not None else 0  # Adjust this default value as needed

            # Create port record with retrieved data
            DevicePort.objects.create(
                managed_device=switch,
                port=port_num,
                speed=speed,
                duplex=int(duplex) if duplex is not None else None,
                # Add other port fields here
            )
            switch.save()
            
    def update_port_data(self, switch):
        # Get all ports for the given switch
        ports = DevicePort.objects.filter(managed_device=switch)

        for port in ports:
            self.update_port_info_from_snmp(switch, port)

    def update_port_info_from_snmp(self, switch, port):
        ip = switch.ip
        community = switch.snmp_community_ro

        # Define SNMP OIDs for various port information
        port_oids = {
            'speed': f'.1.3.6.1.2.1.2.2.1.5.{port.port}',
            'admin_status': f'.1.3.6.1.2.1.2.2.1.7.{port.port}',
            'oper_status': f'.1.3.6.1.2.1.2.2.1.8.{port.port}',
            'vlan_membership': f'.1.3.6.1.2.1.17.7.1.4.3.1.2.{port.port}',
            'mac_addresses': f'.1.3.6.1.2.1.17.7.1.2.2.1.2.{port.port}',
            'discards_in': f'.1.3.6.1.2.1.2.2.1.13.{port.port}',
            'discards_out': f'.1.3.6.1.2.1.2.2.1.19.{port.port}',
        }

        # Perform SNMP queries for port information
        speed = self.snmp_get(ip, community, port_oids['speed'])
        admin_status = self.snmp_get(ip, community, port_oids['admin_status'])
        oper_status = self.snmp_get(ip, community, port_oids['oper_status'])
        vlan_membership = self.snmp_get(ip, community, port_oids['vlan_membership'])
        mac_addresses = self.snmp_get(ip, community, port_oids['mac_addresses'])
        discards_in = self.snmp_get(ip, community, port_oids['discards_in'])
        discards_out = self.snmp_get(ip, community, port_oids['discards_out'])

        # Update port data in the database
        port.speed = int(speed) if speed else None
        port.admin = int(admin_status) if admin_status else None
        port.oper = int(oper_status) if oper_status else None
        port.discards_in = int(discards_in) if discards_in else None
        port.discards_out = int(discards_out) if discards_out else None


        port.duplex = 0

        # Extract VLAN information and MAC addresses
        if vlan_membership:
            port.port_tagged = vlan_membership.split(',')
        if mac_addresses:
            # Assuming MAC addresses are separated by commas
            mac_list = mac_addresses.split(',')
            for mac_address in mac_list:
                # Check if the MAC address already exists in the database
                mac, created = Mac.objects.get_or_create(
                    switch=switch,
                    mac=mac_address,
                    vlan=port.pvid,
                )
                if created:
                    print(f"New MAC address discovered: {mac_address}")

        port.save()
