from pysnmp.hlapi import *
from snmp.snmp_client import snmp_walk, snmp_get
from snmp.models import SwitchPort, SwitchPortStats
import re
from django.utils.timezone import now

# OID constants
IFDESCR_OID = 'IF-MIB', 'ifDescr'
IFADMIN_OID = 'IF-MIB', 'ifAdminStatus'
IFOPER_OID = 'IF-MIB', 'ifOperStatus'
IFSPEED_OID = 'IF-MIB', 'ifSpeed'
PVID_OID = 'Q-BRIDGE-MIB', 'dot1qPvid'
RX_OID = 'IF-MIB', 'ifHCInOctets'
TX_OID = 'IF-MIB', 'ifHCOutOctets'

FILTER_REGEX = re.compile(r'(^|\b)(tunnel|loopback|null|vlan)(\d+)?($|\b)', re.IGNORECASE)


def poll_ports(switch):
    ip = switch.ip
    community = switch.snmp_community_ro

    descr_table = snmp_walk(ip, community, *IFDESCR_OID)
    admin_table = snmp_walk(ip, community, *IFADMIN_OID)
    oper_table = snmp_walk(ip, community, *IFOPER_OID)
    speed_table = snmp_walk(ip, community, *IFSPEED_OID)
    pvid_table = snmp_walk(ip, community, *PVID_OID)
    rx_table = snmp_walk(ip, community, *RX_OID)
    tx_table = snmp_walk(ip, community, *TX_OID)

    # Filter out unwanted interfaces here
    filtered_descr_table = [(k, v) for k, v in descr_table if not FILTER_REGEX.search(v)]

    descr_map = {k.split('.')[-1]: v for k, v in filtered_descr_table}
    admin_map = {k.split('.')[-1]: v for k, v in admin_table}
    oper_map = {k.split('.')[-1]: v for k, v in oper_table}
    speed_map = {k.split('.')[-1]: v for k, v in speed_table}
    pvid_map = {k.split('.')[-1]: v for k, v in pvid_table}
    rx_map = {k.split('.')[-1]: v for k, v in rx_table}
    tx_map = {k.split('.')[-1]: v for k, v in tx_table}

    switch.ports.all().delete()

    for index, descr in descr_map.items():
        try:
            port = SwitchPort(
                switch=switch,
                port_index=int(index),
                description=descr.strip(),
                admin_state=admin_map.get(index, ''),
                oper_state=oper_map.get(index, ''),
                speed=speed_map.get(index, ''),
            )

            vlan = pvid_map.get(index)
            if vlan:
                try:
                    port.vlan_id = int(vlan)
                except ValueError:
                    pass

            rx = rx_map.get(index)
            tx = tx_map.get(index)

            if rx and tx:
                try:
                    port.rx_signal = float(rx) / 1e6  # Convert to Mbps
                    port.tx_signal = float(tx) / 1e6
                except ValueError:
                    port.rx_signal = None
                    port.tx_signal = None

            port.save()

            # Save historical stats
            try:
                SwitchPortStats.objects.create(
                    port=port,
                    octets_in=int(rx) if rx else 0,
                    octets_out=int(tx) if tx else 0,
                    timestamp=now()
                )
            except Exception as stat_err:
                print(f"⚠️ Failed to save stats for port {port}: {stat_err}")

        except Exception as port_err:
            print(f"❌ Error processing port index {index}: {port_err}")