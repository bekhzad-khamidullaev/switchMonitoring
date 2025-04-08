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
SFP_RX_SIGNAL_OID = 'IF-MIB', 'ifInUcastPkts'  # OID для уровня RX сигнала (пример)
SFP_TX_SIGNAL_OID = 'IF-MIB', 'ifOutUcastPkts'  # OID для уровня TX сигнала (пример)

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
    rx_signal_table = snmp_walk(ip, community, *SFP_RX_SIGNAL_OID)
    tx_signal_table = snmp_walk(ip, community, *SFP_TX_SIGNAL_OID)

    filtered_descr_table = [(k, v) for k, v in descr_table if not FILTER_REGEX.search(v)]

    descr_map = {k.split('.')[-1]: v for k, v in filtered_descr_table}
    admin_map = {k.split('.')[-1]: v for k, v in admin_table}
    oper_map = {k.split('.')[-1]: v for k, v in oper_table}
    speed_map = {k.split('.')[-1]: v for k, v in speed_table}
    pvid_map = {k.split('.')[-1]: v for k, v in pvid_table}
    rx_map = {k.split('.')[-1]: v for k, v in rx_table}
    tx_map = {k.split('.')[-1]: v for k, v in tx_table}
    rx_signal_map = {k.split('.')[-1]: v for k, v in rx_signal_table}
    tx_signal_map = {k.split('.')[-1]: v for k, v in tx_signal_table}

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

            rx_signal = rx_signal_map.get(index)
            tx_signal = tx_signal_map.get(index)

            if rx_signal and tx_signal:
                try:
                    port.rx_signal = float(rx_signal) / 1e6  # Convert to dBm
                    port.tx_signal = float(tx_signal) / 1e6  # Convert to dBm
                except ValueError:
                    port.rx_signal = None
                    port.tx_signal = None

            port.save()

            try:
                SwitchPortStats.objects.create(
                    port=port,
                    octets_in=int(rx_map.get(index, 0)),
                    octets_out=int(tx_map.get(index, 0)),
                    timestamp=now()
                )
            except Exception as stat_err:
                print(f"⚠️ Failed to save stats for port {port}: {stat_err}")

        except Exception as port_err:
            print(f"❌ Error processing port index {index}: {port_err}")
