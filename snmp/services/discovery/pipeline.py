import logging
from typing import Dict, Optional

from django.db import transaction
from django.utils import timezone

from snmp.models import Device, Interface, Device
from .normalize import normalize_vendor_model
from .profile_matcher import match_device_profile
from .read_base_snmp import read_base_snmp

logger = logging.getLogger(__name__)


def run_device_discovery(
    ip: str,
    community: str,
    managed_device: Optional[Device] = None,
    switch: Optional[Device] = None,  # legacy alias
    timeout: int = 2,
    retries: int = 1,
) -> Dict[str, int]:
    if managed_device is None:
        managed_device = switch
    base = read_base_snmp(ip=ip, community=community, timeout=timeout, retries=retries)
    normalized = normalize_vendor_model(base.get('sys_object_id', ''), base.get('sys_descr', ''))

    profile = match_device_profile(
        vendor=normalized.get('vendor', ''),
        model=normalized.get('model', ''),
        firmware=normalized.get('firmware', ''),
    )

    with transaction.atomic():
        device, _ = Device.objects.update_or_create(
            ip=ip,
            defaults={
                'managed_device': managed_device,
                'hostname': managed_device.hostname if managed_device and managed_device.hostname else '',
                'vendor': normalized.get('vendor', ''),
                'model': normalized.get('model', ''),
                'firmware': normalized.get('firmware', ''),
                'sys_object_id': base.get('sys_object_id', ''),
                'profile': profile,
                'last_discovered_at': timezone.now(),
                'status': True,
            },
        )

        seen_indexes = set()
        for item in base.get('interfaces', []):
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

    logger.info(
        'discovery completed',
        extra={
            'ip': ip,
            'device_id': device.id,
            'profile_id': profile.id if profile else None,
            'interfaces_count': len(base.get('interfaces', [])),
            'warnings': 0,
        },
    )

    return {
        'device_id': device.id,
        'profile_id': profile.id if profile else 0,
        'interfaces_count': len(seen_indexes),
    }
