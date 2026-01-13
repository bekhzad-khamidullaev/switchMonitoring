from snmp.services.snmp_client import SnmpClient, SnmpTarget
import math

from django.core.paginator import Paginator
from django.utils import timezone

from ..models import Switch, Interface, InterfaceL2, InterfaceOptics, MacEntry
from snmp.services.bridge_mib import collect_mac_table, get_pvid
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
        self.client = SnmpClient(SnmpTarget(host=str(self.ip), community=self.snmp_community))

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
        # Legacy name: this performs a single GET.
        try:
            val = self.client.get_one(oid)
            if val is None:
                return []
            try:
                rendered = str(int(val))
            except Exception:
                rendered = val.prettyPrint() if hasattr(val, 'prettyPrint') else str(val)
            return [f"{oid} = {rendered}"]
        except Exception:
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
    
class PortsInfo:

    def snmp_get(self, ip, community, oid):
        """MIB-aware SNMP GET.

        Supports both numeric and symbolic OIDs (e.g. 'IF-MIB::ifSpeed.1').
        """
        try:
            client = SnmpClient(SnmpTarget(host=str(ip), community=community))
            val = client.get_one(oid)
            if val is None:
                return None
            try:
                return str(int(val))
            except Exception:
                return val.prettyPrint() if hasattr(val, 'prettyPrint') else str(val)
        except Exception as e:
            logger.exception(f"Error during SNMP Get: {e}")
            return None


    def create_switch_ports(self, switch):
        ip = switch.ip
        community = switch.snmp_community_ro

        # Replace the following with the actual SNMP OIDs for port information
        port_oids = {
            'speed': 'IF-MIB::ifSpeed',
            'duplex': 'EtherLike-MIB::dot3StatsDuplexStatus',
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
        # Preload MAC table via Q-BRIDGE-MIB (vlan, ifIndex, mac)
        client = SnmpClient(SnmpTarget(host=str(switch.ip), community=switch.snmp_community_ro or self.snmp_community))
        mac_rows = collect_mac_table(client)
        mac_by_ifindex = {}
        for vlan, ifindex, mac in mac_rows:
            mac_by_ifindex.setdefault(ifindex, []).append((vlan, mac))

        ports = Interface.objects.filter(switch=switch)
        for port in ports:
            self.update_port_info_from_snmp(switch, port, client=client, mac_by_ifindex=mac_by_ifindex)

    def update_port_info_from_snmp(self, switch, port, client: SnmpClient, mac_by_ifindex: dict):
        ip = switch.ip
        community = switch.snmp_community_ro

        # Define SNMP OIDs for various port information
        port_oids = {
            'speed': f'IF-MIB::ifSpeed.{port.ifindex}',
            'admin_status': f'IF-MIB::ifAdminStatus.{port.ifindex}',
            'oper_status': f'IF-MIB::ifOperStatus.{port.ifindex}',
            # NOTE: VLAN/MAC requires BRIDGE/Q-BRIDGE MIB and usually walks, keep numeric fallback for now.
            'vlan_membership': f'.1.3.6.1.2.1.17.7.1.4.3.1.2.{port.ifindex}',
            'mac_addresses': f'.1.3.6.1.2.1.17.7.1.2.2.1.2.{port.ifindex}',
            'discards_in': f'IF-MIB::ifInDiscards.{port.ifindex}',
            'discards_out': f'IF-MIB::ifOutDiscards.{port.ifindex}',
        }

        # Perform SNMP queries for port information
        speed = self.snmp_get(ip, community, port_oids['speed'])
        admin_status = self.snmp_get(ip, community, port_oids['admin_status'])
        oper_status = self.snmp_get(ip, community, port_oids['oper_status'])
        vlan_membership = self.snmp_get(ip, community, port_oids['vlan_membership'])
        # MAC addresses collected once via Q-BRIDGE-MIB
        mac_addresses = None
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

        # Extract VLAN information
        l2, _ = InterfaceL2.objects.get_or_create(interface=port)
        if vlan_membership:
            l2.tagged_vlans = vlan_membership

        # Update PVID from Q-BRIDGE-MIB
        pvid = get_pvid(client, int(port.ifindex))
        if pvid is not None:
            l2.pvid = pvid

        l2.save(update_fields=['tagged_vlans', 'pvid'])

        # Save MAC entries collected via Q-BRIDGE-MIB (vlan + mac)
        for vlan, mac_address in mac_by_ifindex.get(int(port.ifindex), []):
            MacEntry.objects.update_or_create(
                switch=switch,
                mac=mac_address,
                vlan=vlan,
                defaults={'interface': port},
            )