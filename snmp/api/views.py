from django.db.models import Min
from rest_framework import permissions, viewsets

from snmp.api.serializers import (
    SwitchSerializer,
    InterfaceSerializer,
    MacEntrySerializer,
    BandwidthSampleSerializer,
)
from snmp.models import Switch, Interface, MacEntry, InterfaceBandwidthSample
from snmp.views.qoshimcha import get_permitted_branches


class BranchPermissionMixin:
    permission_classes = [permissions.IsAuthenticated]

    def permitted_branches(self):
        return get_permitted_branches(self.request.user)


class SwitchViewSet(BranchPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = SwitchSerializer

    def get_queryset(self):
        branches = self.permitted_branches()
        return (
            Switch.objects
            .select_related('ats', 'ats__branch', 'model', 'model__vendor')
            .filter(ats__branch__in=branches)
            .annotate(min_rx=Min('interfaces__optics__rx_dbm'), min_tx=Min('interfaces__optics__tx_dbm'))
            .order_by('hostname')
        )


class InterfaceViewSet(BranchPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = InterfaceSerializer

    def get_queryset(self):
        branches = self.permitted_branches()
        qs = (
            Interface.objects
            .select_related('switch', 'switch__ats', 'switch__ats__branch', 'optics', 'l2')
            .filter(switch__ats__branch__in=branches)
        )
        switch_id = self.request.query_params.get('switch_id')
        if switch_id:
            qs = qs.filter(switch_id=switch_id)
        return qs.order_by('ifindex')


class MacEntryViewSet(BranchPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = MacEntrySerializer

    def get_queryset(self):
        branches = self.permitted_branches()
        qs = (
            MacEntry.objects
            .select_related('switch', 'interface', 'switch__ats', 'switch__ats__branch')
            .filter(switch__ats__branch__in=branches)
        )
        switch_id = self.request.query_params.get('switch_id')
        if switch_id:
            qs = qs.filter(switch_id=switch_id)
        return qs.order_by('-last_seen')


class BandwidthSampleViewSet(BranchPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = BandwidthSampleSerializer

    def get_queryset(self):
        branches = self.permitted_branches()
        qs = (
            InterfaceBandwidthSample.objects
            .select_related('interface', 'interface__switch', 'interface__switch__ats', 'interface__switch__ats__branch')
            .filter(interface__switch__ats__branch__in=branches)
        )
        interface_id = self.request.query_params.get('interface_id')
        if interface_id:
            qs = qs.filter(interface_id=interface_id)
        return qs.order_by('-ts')[:500]
