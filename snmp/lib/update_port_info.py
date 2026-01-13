from pysnmp.hlapi import *
from pysnmp import error
import math

from django.core.paginator import Paginator
from django.utils import timezone

from ..models import Switch, Interface, InterfaceL2, InterfaceOptics, MacEntry
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        if selected_switch.model:
            self.model = selected_switch.model.device_model
        else:
            self.model = None
        self.ip = selected_switch.ip
        self.snmp_community = snmp_community
        self.TX_SIGNAL_OID, self.RX_SIGNAL_OID, self.SFP_VENDOR_OID, self.PART_NUMBER_OID = self.get_snmp_oids()

    def get_snmp_oids(self):
        if self.model == 'MES3500-24S':
            return (
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.4',
                '1.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.5',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.2.25',
                '1.3.6.1.4.1.890.1.15.3.84.1.1.1.4.25',
            )
        elif self.model == 'MES2428':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.25',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.25',
            )
        elif self.model == 'MES2408':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.9',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.9',
            )
        elif self.model == 'MES2428B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.25.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.25',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.25',
            )
        elif self.model == 'MES2408B':
            return (
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.4.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.2.1.8.9.5.1',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.5.9',
                'iso.3.6.1.4.1.35265.52.1.1.3.1.1.10.9',
            )
        elif self.model == 'MES3500-24':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.25.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.25.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.25',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.25',
            )
        elif self.model == 'MES3500-10':
            return (
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.9.4',
                'iso.3.6.1.4.1.890.1.5.8.68.117.2.1.7.9.5',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.3.9',
                'iso.3.6.1.4.1.890.1.5.8.68.117.1.1.4.9',
            )
        elif self.model == 'GS3700-24HP':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.25',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.28',
            )
        elif self.model == 'MES1124MB':
            return (
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.8',
                'iso.3.6.1.4.1.89.90.1.2.1.3.49.9',
                'iso.3.6.1.4.1.35265.1.23.53.1.1.1.5',
                '',
            )
        elif self.model == 'MGS3520-28':
            return (
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.4',
                'iso.3.6.1.4.1.890.1.15.3.84.1.2.1.6.25.5',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.2.25',
                'iso.3.6.1.4.1.890.1.15.3.84.1.1.1.3.25',
            )
        elif self.model == 'SNR-S2985G-24TC':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.25',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.25',
                '',
                '',

            )
        elif self.model == 'SNR-S2985G-8T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.9',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.9',
                '',
                '',
            )
        elif self.model == 'SNR-S2982G-24T':
            return (
                'iso.3.6.1.4.1.40418.7.100.30.1.1.22.25',
                'iso.3.6.1.4.1.40418.7.100.30.1.1.17.25',
                '',
                '',
            )
        elif self.model == 'T2600G-28TS':
            return (
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.5.49177',
                'iso.3.6.1.4.1.11863.6.96.1.7.1.1.6.49177',
                '',
                '',
            )
        elif self.model == 'S3328TP-SI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014',
                '',
                '',
            )
        elif self.model == 'S3328TP-EI':
            return (
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.9.67240014',
                'iso.3.6.1.4.1.2011.5.25.31.1.1.3.1.8.67240014',
                '',
                '',
            )
        else:
            return ('iso.3.6.1.4.1.2011.5.14.6.4.1.4.234881088',
                    'iso.3.6.1.4.1.2011.5.14.6.4.1.5.234881088',
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
        TX_SIGNAL_raw = self.perform_snmpwalk(self.TX_SIGNAL_OID)
        RX_SIGNAL_raw = self.perform_snmpwalk(self.RX_SIGNAL_OID)

        if TX_SIGNAL_raw is not None and RX_SIGNAL_raw is not None:
            TX_SIGNAL = self.extract_value(TX_SIGNAL_raw)
            RX_SIGNAL = self.extract_value(RX_SIGNAL_raw)
        else:
            TX_SIGNAL = None
            RX_SIGNAL = None

        if self.SFP_VENDOR_OID and self.PART_NUMBER_OID is not None:
            SFP_VENDOR_raw = self.perform_snmpwalk(self.SFP_VENDOR_OID)
            PART_NUMBER_raw = self.perform_snmpwalk(self.PART_NUMBER_OID)
            SFP_VENDOR = self.extract_value(SFP_VENDOR_raw)
            PART_NUMBER = self.extract_value(PART_NUMBER_raw)
        else:
            SFP_VENDOR = None
            PART_NUMBER = None

        switch = self.selected_switch

        # Switch-level optics fields are deprecated.
        # Best-effort: if a "main port" is set on the switch (legacy FK), store optics to that interface.
        rx_dbm = None
        tx_dbm = None
        try:
            if '3500' in self.model or 'GS3700' in self.model or 'MGS3520-28' in self.model:
                tx_dbm = round(float(TX_SIGNAL), 2) / 100.0 if TX_SIGNAL is not None else None
                rx_dbm = round(float(RX_SIGNAL), 2) / 100.0 if RX_SIGNAL is not None else None
            elif '3328' in self.model or 'T2600G' in self.model:
                tx_dbm = round(mw_to_dbm(float(TX_SIGNAL)), 2) if TX_SIGNAL is not None else None
                rx_dbm = round(mw_to_dbm(float(RX_SIGNAL)), 2) if RX_SIGNAL is not None else None
            elif 'SNR' in self.model:
                tx_dbm = round(float(TX_SIGNAL), 2) if TX_SIGNAL is not None else None
                rx_dbm = round(float(RX_SIGNAL), 2) if RX_SIGNAL is not None else None
            else:
                tx_dbm = round(float(TX_SIGNAL), 2) / 1000.0 if TX_SIGNAL is not None else None
                rx_dbm = round(float(RX_SIGNAL), 2) / 1000.0 if RX_SIGNAL is not None else None
        except (ValueError, TypeError):
            rx_dbm = None
            tx_dbm = None

        # Persist to per-interface optics if possible
        try:
            legacy_port = getattr(switch, 'port', None)
            if legacy_port is not None:
                ifindex = int(getattr(legacy_port, 'port', 0) or 0)
                iface = Interface.objects.filter(switch=switch, ifindex=ifindex).first()
                if iface:
                    InterfaceOptics.objects.update_or_create(
                        interface=iface,
                        defaults={
                            'rx_dbm': rx_dbm,
                            'tx_dbm': tx_dbm,
                            'sfp_vendor': SFP_VENDOR if SFP_VENDOR is not None else None,
                            'part_number': PART_NUMBER if PART_NUMBER is not None else None,
                            'polled_at': timezone.now(),
                        },
                    )
        except Exception:
            pass

        # Keep switch inventory fields untouched

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

            iface_defaults = {
                'speed': speed,
                'duplex': int(duplex) if duplex is not None else None,
                'polled_at': timezone.now(),
            }
            iface, _ = Interface.objects.update_or_create(
                switch=switch,
                ifindex=port_num,
                defaults=iface_defaults,
            )
            InterfaceL2.objects.update_or_create(interface=iface, defaults={})
            
    def update_port_data(self, switch):
        # Get all ports for the given switch
        ports = Interface.objects.filter(switch=switch)

        for port in ports:
            self.update_port_info_from_snmp(switch, port)

    def update_port_info_from_snmp(self, switch, port):
        ip = switch.ip
        community = switch.snmp_community_ro

        # Define SNMP OIDs for various port information
        port_oids = {
            'speed': f'.1.3.6.1.2.1.2.2.1.5.{port.ifindex}',
            'admin_status': f'.1.3.6.1.2.1.2.2.1.7.{port.ifindex}',
            'oper_status': f'.1.3.6.1.2.1.2.2.1.8.{port.ifindex}',
            'vlan_membership': f'.1.3.6.1.2.1.17.7.1.4.3.1.2.{port.ifindex}',
            'mac_addresses': f'.1.3.6.1.2.1.17.7.1.2.2.1.2.{port.ifindex}',
            'discards_in': f'.1.3.6.1.2.1.2.2.1.13.{port.ifindex}',
            'discards_out': f'.1.3.6.1.2.1.2.2.1.19.{port.ifindex}',
        }

        # Perform SNMP queries for port information
        speed = self.snmp_get(ip, community, port_oids['speed'])
        admin_status = self.snmp_get(ip, community, port_oids['admin_status'])
        oper_status = self.snmp_get(ip, community, port_oids['oper_status'])
        vlan_membership = self.snmp_get(ip, community, port_oids['vlan_membership'])
        mac_addresses = self.snmp_get(ip, community, port_oids['mac_addresses'])
        discards_in = self.snmp_get(ip, community, port_oids['discards_in'])
        discards_out = self.snmp_get(ip, community, port_oids['discards_out'])

        # Update interface data
        port.speed = int(speed) if speed else None
        port.admin = int(admin_status) if admin_status else None
        port.oper = int(oper_status) if oper_status else None
        port.discards_in = int(discards_in) if discards_in else None
        port.discards_out = int(discards_out) if discards_out else None
        port.duplex = 0
        port.polled_at = timezone.now()
        port.save(update_fields=['speed', 'admin', 'oper', 'discards_in', 'discards_out', 'duplex', 'polled_at'])

        # Extract VLAN information and MAC addresses
        l2, _ = InterfaceL2.objects.get_or_create(interface=port)
        if vlan_membership:
            l2.tagged_vlans = vlan_membership
        l2.save(update_fields=['tagged_vlans'])

        pvid = l2.pvid
        if mac_addresses:
            mac_list = [m.strip() for m in mac_addresses.split(',') if m.strip()]
            for mac_address in mac_list:
                MacEntry.objects.update_or_create(
                    switch=switch,
                    mac=mac_address,
                    vlan=pvid or 0,
                    defaults={'interface': port},
                )