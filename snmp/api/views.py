"""snmp.api.views

ViewSets aligned with the existing project models.

This project uses a legacy/normalized schema (see `snmp.models`).
The Flowbite frontend relies mainly on:
- /api/v1/dashboard/statistics/
- /api/v1/switches/
- /api/v1/switches/{id}/
- /api/v1/switches/{id}/ports/

All endpoints here are implemented to be consistent with those models.
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from snmp.api.filters import (
    ATSFilter,
    BandwidthSampleFilter,
    BranchFilter,
    HostGroupFilter,
    SwitchFilter,
    SwitchModelFilter,
    SwitchNeighborFilter,
    SwitchPortFilter,
)
from snmp.api.permissions import CanManageNetwork, CanManageSwitches, IsAdminOrReadOnly, ReadOnlyPermission
from snmp.api.serializers import (
    AtsSerializer,
    BranchSerializer,
    DashboardStatsSerializer,
    HostGroupSerializer,
    InterfaceBandwidthSampleSerializer,
    InterfaceSerializer,
    NeighborLinkSerializer,
    SwitchCreateUpdateSerializer,
    SwitchDetailSerializer,
    SwitchListSerializer,
    SwitchModelSerializer,
    VendorSerializer,
)
from snmp.models import (
    Ats,
    Branch,
    HostGroup,
    Interface,
    InterfaceBandwidthSample,
    NeighborLink,
    Switch,
    SwitchModel,
    Vendor,
)


# -------------------------
# Reference data
# -------------------------


class ATSViewSet(viewsets.ModelViewSet):
    queryset = Ats.objects.select_related("branch").all()
    serializer_class = AtsSerializer
    permission_classes = [CanManageNetwork]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ATSFilter
    search_fields = ["name", "subnet"]
    ordering_fields = ["name", "subnet", "id"]
    ordering = ["name"]


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [CanManageNetwork]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BranchFilter
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]


class HostGroupViewSet(viewsets.ModelViewSet):
    queryset = HostGroup.objects.select_related("branch", "parent").all()
    serializer_class = HostGroupSerializer
    permission_classes = [CanManageNetwork]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = HostGroupFilter
    search_fields = ["name"]
    ordering_fields = ["branch", "parent", "sort_order", "name", "id"]
    ordering = ["branch", "parent", "sort_order", "name"]


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]


class SwitchModelViewSet(viewsets.ModelViewSet):
    queryset = SwitchModel.objects.select_related("vendor").all()
    serializer_class = SwitchModelSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchModelFilter
    search_fields = ["device_model", "vendor__name"]
    ordering_fields = ["device_model", "id"]
    ordering = ["device_model"]


# -------------------------
# Core: Switches
# -------------------------


class SwitchViewSet(viewsets.ModelViewSet):
    permission_classes = [CanManageSwitches]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchFilter

    # Search fields adapted to existing Switch model
    search_fields = ["hostname", "ip", "switch_mac", "serial_number"]

    ordering_fields = ["hostname", "ip", "status", "last_update", "created", "serial_number", "id"]
    ordering = ["-last_update"]

    def get_queryset(self):
        # Keep it simple and correct
        return Switch.objects.select_related("ats", "model", "group").all()

    def get_serializer_class(self):
        if self.action == "list":
            return SwitchListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return SwitchCreateUpdateSerializer
        return SwitchDetailSerializer

    @action(detail=True, methods=["get"], permission_classes=[ReadOnlyPermission])
    def ports(self, request, pk=None):
        sw = self.get_object()
        qs = sw.interfaces.select_related("optics").all().order_by("ifindex")
        return Response(InterfaceSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["get"], permission_classes=[ReadOnlyPermission])
    def neighbors(self, request, pk=None):
        sw = self.get_object()
        qs = sw.neighbor_links.select_related("local_interface").all().order_by("-last_seen")
        return Response(NeighborLinkSerializer(qs, many=True, context={"request": request}).data)


# -------------------------
# Interfaces
# -------------------------


class InterfaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Interface.objects.select_related("switch", "optics").all()
    serializer_class = InterfaceSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchPortFilter
    search_fields = ["name", "description", "alias", "switch__hostname", "switch__ip"]
    ordering_fields = ["switch", "ifindex", "name", "oper", "admin", "speed", "polled_at"]
    ordering = ["switch", "ifindex"]


class NeighborLinkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NeighborLink.objects.select_related("local_switch", "local_interface").all()
    serializer_class = NeighborLinkSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchNeighborFilter
    search_fields = ["remote_mac", "remote_port", "local_switch__hostname", "local_switch__ip"]
    ordering_fields = ["last_seen", "id"]
    ordering = ["-last_seen"]


class InterfaceBandwidthSampleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InterfaceBandwidthSample.objects.select_related("interface", "interface__switch").all()
    serializer_class = InterfaceBandwidthSampleSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BandwidthSampleFilter
    ordering_fields = ["ts", "in_bps", "out_bps", "id"]
    ordering = ["-ts"]


# -------------------------
# Dashboard
# -------------------------


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        total_switches = Switch.objects.count()
        online_switches = Switch.objects.filter(status=True).count()
        offline_switches = Switch.objects.filter(status=False).count()

        total_ports = Interface.objects.count()
        active_ports = Interface.objects.filter(oper=1).count()

        total_branches = Branch.objects.count()
        total_ats = Ats.objects.count()

        uptime_percentage = (online_switches / total_switches * 100) if total_switches else 0.0

        payload = {
            "total_switches": total_switches,
            "online_switches": online_switches,
            "offline_switches": offline_switches,
            "warning_switches": 0,
            "total_ports": total_ports,
            "active_ports": active_ports,
            "total_branches": total_branches,
            "total_ats": total_ats,
            "uptime_percentage": uptime_percentage,
            "last_updated": timezone.now(),
        }
        return Response(DashboardStatsSerializer(payload).data)
