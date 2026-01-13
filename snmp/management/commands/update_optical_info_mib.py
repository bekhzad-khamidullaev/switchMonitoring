import logging
from typing import Any, Dict, Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from snmp.models import Switch, Interface, InterfaceOptics
from snmp.services.interface_classification import is_virtual_interface
from snmp.services.snmp_client import SnmpClient, SnmpTarget


logger = logging.getLogger("SNMP_OPTICAL_MIB")


# Standard IF-MIB columns
IF_DESCR = 'IF-MIB::ifDescr'
IF_TYPE = 'IF-MIB::ifType'
IF_ALIAS = 'IF-MIB::ifAlias'
IF_ADMIN_STATUS = 'IF-MIB::ifAdminStatus'
IF_OPER_STATUS = 'IF-MIB::ifOperStatus'
IF_LAST_CHANGE = 'IF-MIB::ifLastChange'
IF_SPEED = 'IF-MIB::ifSpeed'


def _suffix_ifindex(oid_str: str) -> Optional[int]:
    try:
        return int(oid_str.split('.')[-1])
    except Exception:
        return None


def _normalize_numeric_oid(oid_str: str) -> str:
    v = (oid_str or '').strip()
    if v.startswith('iso.'):
        v = '1' + v[len('iso'):]
    if v.startswith('.'):
        v = v[1:]
    return v


def _is_numeric_oid(oid_str: str) -> bool:
    v = _normalize_numeric_oid(oid_str)
    parts = v.split('.')
    return len(parts) > 2 and all(p.isdigit() for p in parts)


class Command(BaseCommand):
    help = 'Update optical port DDM/DOM info using MIB symbolic names (sync implementation).'

    def add_arguments(self, parser):
        parser.add_argument('--switch-id', type=int, help='Poll only switch with this DB ID.')
        parser.add_argument('--ip', type=str, help='Poll only switch with this IP address.')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of switches (0=no limit).')
        parser.add_argument('--community', type=str, help='Override SNMP community string.')
        parser.add_argument('--timeout', type=int, default=5, help='SNMP timeout seconds.')
        parser.add_argument('--retries', type=int, default=1, help='SNMP retries.')
        parser.add_argument('--workers', type=int, default=10, help='(unused in sync impl)')
        parser.add_argument('--run-once', action='store_true', help='Run once and exit.')
        parser.add_argument('--sleep', type=int, default=300, help='(unused in sync impl)')

    def handle(self, *args, **options):
        limit = int(options.get('limit') or 0)
        qs = Switch.objects.filter(status=True).exclude(ip__isnull=True)
        if options.get('switch_id'):
            qs = qs.filter(pk=options['switch_id'])
        elif options.get('ip'):
            qs = qs.filter(ip=options['ip'])
        if limit > 0:
            qs = qs[:limit]

        switches = list(qs)
        if not switches:
            self.stdout.write(self.style.WARNING('No active switches found to poll.'))
            return

        for sw in switches:
            try:
                self.poll_switch(sw, options)
            except Exception as e:
                logger.exception('Optical poll failed for %s: %s', sw.ip, e)

    def poll_switch(self, sw: Switch, options: Dict[str, Any]):
        community = options.get('community') or sw.snmp_community_ro or 'public'
        client = SnmpClient(
            SnmpTarget(host=str(sw.ip), community=community, timeout=int(options['timeout']), retries=int(options['retries']))
        )

        # Walk IF table columns
        descr = client.walk(IF_DESCR)
        iftype = client.walk(IF_TYPE)
        alias = client.walk(IF_ALIAS)
        admin = client.walk(IF_ADMIN_STATUS)
        oper = client.walk(IF_OPER_STATUS)
        lastchg = client.walk(IF_LAST_CHANGE)
        speed = client.walk(IF_SPEED)

        now = timezone.now()

        # Model-specific optics objects (symbolic or numeric base)
        sm = sw.model
        rx_obj = getattr(sm, 'rx_power_object', None) if sm else None
        tx_obj = getattr(sm, 'tx_power_object', None) if sm else None
        vendor_obj = getattr(sm, 'sfp_vendor_object', None) if sm else None
        part_obj = getattr(sm, 'part_num_object', None) if sm else None
        serial_obj = getattr(sm, 'serial_num_object', None) if sm else None

        def _get_indexed(obj: Optional[str], idx: int):
            if not obj:
                return None
            if '::' in obj:
                return client.get_one(f'{obj}.{idx}')
            if _is_numeric_oid(obj):
                return client.get_one(f'{_normalize_numeric_oid(obj)}.{idx}')
            return client.get_one(f'{obj}.{idx}')

        updated = 0
        created = 0

        with transaction.atomic():
            for oid, descr_val in descr.items():
                ifindex = _suffix_ifindex(oid)
                if ifindex is None:
                    continue

                name = None
                description = str(descr_val)
                alias_val = alias.get(f'{IF_ALIAS}.{ifindex}')
                iftype_val = iftype.get(f'{IF_TYPE}.{ifindex}')

                try:
                    iftype_int = int(iftype_val) if iftype_val is not None else None
                except Exception:
                    iftype_int = None

                is_virtual, _ = is_virtual_interface(iftype_int, name, description, str(alias_val) if alias_val else None)
                if is_virtual:
                    continue

                iface_defaults = {
                    'description': description,
                    'alias': str(alias_val) if alias_val is not None else '',
                    'iftype': iftype_int,
                    'admin': int(admin.get(f'{IF_ADMIN_STATUS}.{ifindex}', 0) or 0),
                    'oper': int(oper.get(f'{IF_OPER_STATUS}.{ifindex}', 0) or 0),
                    'lastchange': int(lastchg.get(f'{IF_LAST_CHANGE}.{ifindex}', 0) or 0),
                    'speed': int(speed.get(f'{IF_SPEED}.{ifindex}', 0) or 0),
                    'polled_at': now,
                }

                iface, was_created = Interface.objects.update_or_create(
                    switch=sw, ifindex=ifindex, defaults=iface_defaults
                )
                created += int(was_created)
                updated += int(not was_created)

                optics_defaults = {
                    'rx_dbm': None,
                    'tx_dbm': None,
                    'sfp_vendor': None,
                    'part_number': None,
                    'serial_number': None,
                    'polled_at': now,
                }

                rx = _get_indexed(rx_obj, ifindex)
                tx = _get_indexed(tx_obj, ifindex)
                if rx is not None:
                    try:
                        optics_defaults['rx_dbm'] = float(rx)
                    except Exception:
                        pass
                if tx is not None:
                    try:
                        optics_defaults['tx_dbm'] = float(tx)
                    except Exception:
                        pass

                v = _get_indexed(vendor_obj, ifindex)
                p = _get_indexed(part_obj, ifindex)
                s = _get_indexed(serial_obj, ifindex)
                optics_defaults['sfp_vendor'] = str(v) if v is not None else None
                optics_defaults['part_number'] = str(p) if p is not None else None
                optics_defaults['serial_number'] = str(s) if s is not None else None

                InterfaceOptics.objects.update_or_create(interface=iface, defaults=optics_defaults)

        logger.info('[%s] interfaces created=%s updated=%s', sw.ip, created, updated)
