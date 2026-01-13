from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from snmp.services.snmp_client import SnmpClient


DOT1D_BASE_PORT_IFINDEX = 'BRIDGE-MIB::dot1dBasePortIfIndex'
DOT1Q_TP_FDB_PORT = 'Q-BRIDGE-MIB::dot1qTpFdbPort'
DOT1Q_PVID = 'Q-BRIDGE-MIB::dot1qPvid'

# Numeric fallbacks (when MIB modules are not available)
DOT1D_BASE_PORT_IFINDEX_NUM = '1.3.6.1.2.1.17.1.4.1.2'
DOT1Q_TP_FDB_PORT_NUM = '1.3.6.1.2.1.17.7.1.2.2.1.2'
DOT1Q_PVID_NUM = '1.3.6.1.2.1.17.7.1.4.5.1.1'

DOT1D_TP_FDB_PORT = 'BRIDGE-MIB::dot1dTpFdbPort'
DOT1D_TP_FDB_PORT_NUM = '1.3.6.1.2.1.17.4.3.1.2'


def _parse_dot1q_fdb_index(oid_str: str) -> Optional[Tuple[int, str]]:
    """Parse OID like 'Q-BRIDGE-MIB::dot1qTpFdbPort.<vlan>.<mac-bytes...>'

    Returns (vlan, mac_str)
    """
    # oid_str example after resolution:
    # 'Q-BRIDGE-MIB::dot1qTpFdbPort.100.0.17.34.51.68.85'
    parts = oid_str.split('.')
    if len(parts) < 2:
        return None

    # Find vlan and mac bytes from tail; vlan is first numeric component after symbol
    try:
        # last 7 numbers: vlan + 6 mac bytes
        vlan = int(parts[-7])
        mac_bytes = [int(x) for x in parts[-6:]]
    except Exception:
        return None

    mac = ':'.join(f'{b:02x}' for b in mac_bytes)
    return vlan, mac


def build_bridgeport_to_ifindex(client: SnmpClient) -> Dict[int, int]:
    """Map dot1dBasePort -> ifIndex."""
    out: Dict[int, int] = {}
    try:
        rows = client.walk(DOT1D_BASE_PORT_IFINDEX)
    except Exception:
        rows = client.walk(DOT1D_BASE_PORT_IFINDEX_NUM)
    for oid, val in rows.items():
        try:
            bridge_port = int(oid.split('.')[-1])
            out[bridge_port] = int(val)
        except Exception:
            continue
    return out


def collect_mac_table(client: SnmpClient) -> List[Tuple[int, int, str]]:
    """Return list of (vlan, ifIndex, mac)."""
    bridgeport_to_ifindex = build_bridgeport_to_ifindex(client)
    try:
        rows = client.walk(DOT1Q_TP_FDB_PORT)
    except Exception:
        rows = client.walk(DOT1Q_TP_FDB_PORT_NUM)

    out: List[Tuple[int, int, str]] = []
    for oid, val in rows.items():
        parsed = _parse_dot1q_fdb_index(oid)
        if not parsed:
            continue
        vlan, mac = parsed
        try:
            bridge_port = int(val)
            ifindex = bridgeport_to_ifindex.get(bridge_port)
            if not ifindex:
                continue
            out.append((vlan, ifindex, mac))
        except Exception:
            continue

    # If device doesn't expose Q-BRIDGE FDB, fallback to BRIDGE-MIB dot1dTpFdbPort (no VLAN info)
    if not out:
        try:
            fdb = client.walk(DOT1D_TP_FDB_PORT)
        except Exception:
            fdb = client.walk(DOT1D_TP_FDB_PORT_NUM)

        for oid, val in fdb.items():
            parts = oid.split('.')
            if len(parts) < 6:
                continue
            try:
                mac_bytes = [int(x) for x in parts[-6:]]
                mac = ':'.join(f'{b:02x}' for b in mac_bytes)
                bridge_port = int(val)
                ifindex = bridgeport_to_ifindex.get(bridge_port)
                if not ifindex:
                    continue
                out.append((0, ifindex, mac))
            except Exception:
                continue

    return out


def get_pvid(client: SnmpClient, ifindex: int) -> Optional[int]:
    v = client.get_one(f'{DOT1Q_PVID}.{ifindex}')
    if v is None:
        v = client.get_one(f'{DOT1Q_PVID_NUM}.{ifindex}')
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None
