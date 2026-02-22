import logging
import re
from typing import Dict, Optional

from django.db import transaction
from django.utils import timezone

from snmp.models import Device, DeviceNeighbor, Interface

from .normalize import normalize_vendor_model
from .profile_matcher import match_device_profile
from .read_base_snmp import read_base_snmp
from .vendor_profiles.factory import get_vendor_profile

logger = logging.getLogger(__name__)
_MAC_HEX = re.compile(r'[0-9a-fA-F]{2}')
_DIGIT_SUFFIX = re.compile(r'(\d+)$')


def _normalize_mac(value: str) -> str:
    if not value:
        return ''
    text = str(value).strip().lower()
    if text.startswith('0x'):
        text = text[2:]
    chunks = _MAC_HEX.findall(text)
    if len(chunks) >= 6:
        return ':'.join(chunks[:6]).lower()
    compact = ''.join(ch for ch in text if ch in '0123456789abcdef')
    if len(compact) >= 12:
        compact = compact[:12]
        return ':'.join(compact[i : i + 2] for i in range(0, 12, 2))
    return ''


def _parse_port_number(value, fallback=0) -> int:
    if value is None:
        return fallback
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    match = _DIGIT_SUFFIX.search(text)
    if match:
        return int(match.group(1))
    return fallback


def _sync_device_neighbors(device: Device, lldp_neighbors) -> int:
    local_mac = _normalize_mac(device.switch_mac)
    if not local_mac:
        return 0

    remote_macs = {
        _normalize_mac(item.get('remote_chassis_mac', ''))
        for item in (lldp_neighbors or [])
        if item.get('remote_chassis_mac')
    }
    remote_macs = {mac for mac in remote_macs if mac and mac != local_mac}
    remote_devices = {
        _normalize_mac(mac): device_id
        for mac, device_id in Device.objects.exclude(pk=device.pk)
        .exclude(switch_mac__isnull=True)
        .exclude(switch_mac='')
        .filter(switch_mac__in=remote_macs)
        .values_list('switch_mac', 'id')
    }

    DeviceNeighbor.objects.filter(mac1=local_mac).delete()
    neighbors_to_create = []
    for item in lldp_neighbors or []:
        remote_mac = _normalize_mac(item.get('remote_chassis_mac', ''))
        if remote_mac not in remote_devices:
            continue
        port1 = _parse_port_number(item.get('local_port'), fallback=0)
        if port1 <= 0:
            continue
        port2 = _parse_port_number(item.get('remote_port'), fallback=0)
        if port2 <= 0:
            port2 = _parse_port_number(item.get('remote_port_id'), fallback=0)
        if port2 <= 0:
            continue
        neighbors_to_create.append(
            DeviceNeighbor(mac1=local_mac, port1=port1, mac2=remote_mac, port2=port2)
        )
    if neighbors_to_create:
        DeviceNeighbor.objects.bulk_create(neighbors_to_create, ignore_conflicts=True)
    return len(neighbors_to_create)


def run_device_discovery(
    ip: str,
    community: str,
    managed_device: Optional[Device] = None,
    switch: Optional[Device] = None,  # legacy alias
    timeout: int = 2,
    retries: int = 1,
) -> Dict[str, object]:
    if managed_device is None:
        managed_device = switch
    base = read_base_snmp(ip=ip, community=community, timeout=timeout, retries=retries)
    normalized = normalize_vendor_model(base.get('sys_object_id', ''), base.get('sys_descr', ''))
    vendor_profile = get_vendor_profile(
        vendor=normalized.get('vendor', ''),
        model=normalized.get('model', ''),
        firmware=normalized.get('firmware', ''),
        sys_object_id=base.get('sys_object_id', ''),
        sys_descr=base.get('sys_descr', ''),
    )
    enriched_interfaces = vendor_profile.enrich_interfaces(base.get('interfaces', []))

    profile = match_device_profile(
        vendor=normalized.get('vendor', ''),
        model=normalized.get('model', ''),
        firmware=normalized.get('firmware', ''),
    )
    if profile is None:
        profile = match_device_profile(vendor='generic', model='', firmware='')

    with transaction.atomic():
        device, _ = Device.objects.update_or_create(
            ip=ip,
            defaults={
                'hostname': managed_device.hostname if managed_device and managed_device.hostname else '',
                'vendor': normalized.get('vendor', ''),
                'model': normalized.get('model', ''),
                'firmware': normalized.get('firmware', ''),
                'sys_object_id': base.get('sys_object_id', ''),
                'switch_mac': _normalize_mac(base.get('switch_mac', '')) or (
                    managed_device.switch_mac if managed_device else ''
                ),
                'profile': profile,
                'last_discovered_at': timezone.now(),
                'status': True,
            },
        )

        seen_indexes = set()
        for item in enriched_interfaces:
            if_index = item['if_index']
            seen_indexes.add(if_index)
            Interface.objects.update_or_create(
                device=device,
                if_index=if_index,
                defaults={
                    'if_name': item.get('if_name', ''),
                    'if_alias': item.get('if_alias', ''),
                    'if_type': item.get('if_type', ''),
                    'is_optical': item.get('is_optical', False),
                    'admin_up': item.get('admin_up'),
                    'oper_up': item.get('oper_up'),
                },
            )
        
        # Cleanup stale interfaces that were not found in this latest discovery run
        if seen_indexes:
            Interface.objects.filter(device=device).exclude(if_index__in=seen_indexes).delete()
            
        neighbors_count = _sync_device_neighbors(device=device, lldp_neighbors=base.get('lldp_neighbors', []))

    logger.info(
        'discovery completed',
        extra={
            'ip': ip,
            'device_id': device.id,
            'profile_id': profile.id if profile else None,
            'interfaces_count': len(enriched_interfaces),
            'vendor_profile': vendor_profile.name,
            'neighbors_count': neighbors_count,
            'warnings': 0,
        },
    )

    return {
        'device_id': device.id,
        'profile_id': profile.id if profile else 0,
        'interfaces_count': len(seen_indexes),
        'neighbors_count': neighbors_count,
        'vendor': normalized.get('vendor', ''),
        'model': normalized.get('model', ''),
        'firmware': normalized.get('firmware', ''),
        'sys_object_id': base.get('sys_object_id', ''),
        'profile': str(profile) if profile else '',
    }
