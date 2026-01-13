import asyncio

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.models import Min

from snmp.models import Switch, Interface, InterfaceOptics, MacEntry, InterfaceBandwidthSample
from snmp.views.qoshimcha import get_permitted_branches


class MonitoringConsumer(AsyncJsonWebsocketConsumer):
    """Realtime feed via server-side polling.

    Uses session auth (same as normal Django login). On connect, periodically
    pushes snapshots: switches status, optics summary, bandwidth latest.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return

        await self.accept()
        self._task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, code):
        task = getattr(self, '_task', None)
        if task:
            task.cancel()

    async def _poll_loop(self):
        while True:
            try:
                payload = await self._build_snapshot()
                await self.send_json(payload)
            except Exception:
                # Don't kill the socket on transient errors
                pass
            await asyncio.sleep(5)

    @sync_to_async
    def _build_snapshot(self):
        branches = get_permitted_branches(self.scope['user'])
        qs = (
            Switch.objects
            .select_related('ats', 'ats__branch')
            .filter(ats__branch__in=branches)
            .annotate(min_rx=Min('interfaces__optics__rx_dbm'), min_tx=Min('interfaces__optics__tx_dbm'))
        )

        switches = [
            {
                'id': s.id,
                'hostname': s.hostname,
                'ip': str(s.ip) if s.ip else None,
                'status': bool(s.status),
                'uptime': s.uptime,
                'min_rx': s.min_rx,
                'min_tx': s.min_tx,
            }
            for s in qs.order_by('hostname')[:500]
        ]

        # Lightweight counters
        mac_count = MacEntry.objects.filter(switch__ats__branch__in=branches).count()
        iface_count = Interface.objects.filter(switch__ats__branch__in=branches).count()
        optics_count = InterfaceOptics.objects.filter(interface__switch__ats__branch__in=branches).count()

        latest_bw = (
            InterfaceBandwidthSample.objects
            .select_related('interface', 'interface__switch')
            .filter(interface__switch__ats__branch__in=branches)
            .order_by('-ts')
            .values('interface_id', 'ts', 'in_bps', 'out_bps')[:200]
        )

        return {
            'type': 'snapshot',
            'switches': switches,
            'counts': {
                'interfaces': iface_count,
                'optics': optics_count,
                'mac_entries': mac_count,
            },
            'bandwidth_latest': list(latest_bw),
        }
