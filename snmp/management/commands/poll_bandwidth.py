import logging
from typing import Any, Dict

from django.core.management.base import BaseCommand
from django.utils import timezone
from snmp.models import Switch, Interface, InterfaceCounterState, InterfaceBandwidthSample
from snmp.services.snmp_client import SnmpClient, SnmpTarget
from snmp.services.bandwidth import CounterSnapshot, compute_bps
from snmp.services.interface_classification import is_virtual_interface


logger = logging.getLogger(__name__)


IFHC_IN_OCTETS = 'IF-MIB::ifHCInOctets'
IFHC_OUT_OCTETS = 'IF-MIB::ifHCOutOctets'
IF_IN_OCTETS = 'IF-MIB::ifInOctets'
IF_OUT_OCTETS = 'IF-MIB::ifOutOctets'


class Command(BaseCommand):
    help = 'Poll interface counters and store bandwidth samples (bps).'

    def add_arguments(self, parser):
        parser.add_argument('--limit-switches', type=int, default=0)
        parser.add_argument('--oids-per-request', type=int, default=20)

    def handle(self, *args, **options):
        now = timezone.now()
        oids_per_request = int(options.get('oids_per_request') or 20)

        switches_qs = Switch.objects.filter(status=True).exclude(ip__isnull=True)
        limit = int(options.get('limit_switches') or 0)
        if limit > 0:
            switches_qs = switches_qs.order_by('id')[:limit]

        for sw in switches_qs:
            try:
                self.poll_switch(sw, now, oids_per_request=oids_per_request)
            except Exception as e:
                logger.exception("Bandwidth poll failed for %s: %s", sw.ip, e)

    def poll_switch(self, sw: Switch, now, oids_per_request: int = 20):
        # collect candidate interfaces from normalized Interface table
        ports = Interface.objects.filter(switch=sw)
        if not ports.exists():
            return

        # Build list of ifIndex we want to poll
        candidates = []
        iface_by_ifindex = {}
        for p in ports:
            is_virtual, _ = is_virtual_interface(p.iftype, p.name, p.description, p.alias)
            if is_virtual:
                continue
            ifindex = int(p.ifindex)
            candidates.append(ifindex)
            iface_by_ifindex[ifindex] = p

        if not candidates:
            return

        community = sw.snmp_community_ro or 'public'
        ip = str(sw.ip)
        client = SnmpClient(SnmpTarget(host=ip, community=community))

        def _chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i + size]

        # First try 64-bit for all ports
        oids64 = []
        for ifindex in candidates:
            oids64.append(f"{IFHC_IN_OCTETS}.{ifindex}")
            oids64.append(f"{IFHC_OUT_OCTETS}.{ifindex}")

        values: Dict[str, Any] = {}
        counter_bits_by_ifindex = {ifindex: 64 for ifindex in candidates}

        for chunk in _chunks(oids64, oids_per_request):
            try:
                values.update(client.get_many(chunk))
            except Exception as e:
                logger.debug("ifHC counters not available on %s: %s", ip, e)
                values = {}
                counter_bits_by_ifindex = {ifindex: 32 for ifindex in candidates}
                break

        # Fallback to 32-bit for all ports if needed
        if not values:
            oids32 = []
            for ifindex in candidates:
                oids32.append(f"{IF_IN_OCTETS}.{ifindex}")
                oids32.append(f"{IF_OUT_OCTETS}.{ifindex}")
            for chunk in _chunks(oids32, oids_per_request):
                values.update(client.get_many(chunk))

        for ifindex in candidates:
            if counter_bits_by_ifindex.get(ifindex, 64) == 64:
                in_oid = f"{IFHC_IN_OCTETS}.{ifindex}"
                out_oid = f"{IFHC_OUT_OCTETS}.{ifindex}"
                counter_bits = 64
            else:
                in_oid = f"{IF_IN_OCTETS}.{ifindex}"
                out_oid = f"{IF_OUT_OCTETS}.{ifindex}"
                counter_bits = 32

            in_val = int(values.get(in_oid, 0))
            out_val = int(values.get(out_oid, 0))

            iface = iface_by_ifindex.get(ifindex)
            if not iface:
                continue

            state, _ = InterfaceCounterState.objects.get_or_create(
                interface=iface,
                defaults={
                    'last_in_octets': in_val,
                    'last_out_octets': out_val,
                    'last_ts': now,
                },
            )

            if state.last_ts:
                interval_sec = max(1.0, (now - state.last_ts).total_seconds())
                prev = CounterSnapshot(in_octets=state.last_in_octets, out_octets=state.last_out_octets)
                curr = CounterSnapshot(in_octets=in_val, out_octets=out_val)
                bps = compute_bps(prev, curr, interval_sec=interval_sec, counter_bits=counter_bits)
            else:
                interval_sec = None
                bps = None

            # Update state
            state.last_in_octets = in_val
            state.last_out_octets = out_val
            state.last_ts = now
            update_fields = ['last_in_octets', 'last_out_octets', 'last_ts']
            if iface and state.interface_id == iface.id:
                update_fields = update_fields
            elif iface and state.interface_id is None:
                update_fields.append('interface')
            state.save(update_fields=update_fields)

            if bps:
                InterfaceBandwidthSample.objects.create(
                    interface=iface,
                    ts=now,
                    in_bps=bps[0],
                    out_bps=bps[1],
                    interval_sec=int(interval_sec) if interval_sec else None,
                    in_octets=in_val,
                    out_octets=out_val,
                )
