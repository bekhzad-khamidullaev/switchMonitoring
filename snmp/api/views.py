"""snmp.api.views

ViewSets aligned with the existing project models.

This project uses a normalized schema (see `snmp.models`).
The Flowbite frontend relies mainly on:
- /api/v1/dashboard/statistics/
- /api/v1/devices/ (switches, routers, etc.)
- /api/v1/devices/{id}/
- /api/v1/devices/{id}/ports/

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
    OpticalInterfaceFilter,
    SwitchFilter as DeviceFilter,
    SwitchModelFilter as DeviceModelFilter,
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
    OpticalInterfaceSerializer,
    OpticalSummarySerializer,
    DeviceCreateUpdateSerializer,
    DeviceDetailSerializer,
    DeviceListSerializer,
    DeviceModelSerializer,
    VendorSerializer,
)
from snmp.models import (
    Ats,
    Branch,
    HostGroup,
    Interface,
    InterfaceBandwidthSample,
    InterfaceOptics,
    NeighborLink,
    Device,
    DeviceModel,
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


class DeviceModelViewSet(viewsets.ModelViewSet):
    """ViewSet for device models (switch/router types)."""
    queryset = DeviceModel.objects.select_related("vendor").all()
    serializer_class = DeviceModelSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DeviceModelFilter
    search_fields = ["device_model", "vendor__name"]
    ordering_fields = ["device_model", "id"]
    ordering = ["device_model"]


# Backward compatibility alias
SwitchModelViewSet = DeviceModelViewSet


# -------------------------
# Core: Devices (Switches, Routers, etc.)
# -------------------------


class DeviceViewSet(viewsets.ModelViewSet):
    """ViewSet for network devices (switches, routers, etc.)."""
    permission_classes = [CanManageSwitches]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DeviceFilter

    search_fields = ["hostname", "ip", "device_mac", "serial_number"]
    ordering_fields = ["hostname", "ip", "status", "last_update", "created", "serial_number", "id"]
    ordering = ["-last_update"]

    def get_queryset(self):
        return Device.objects.select_related("ats", "model", "group").all()

    def get_serializer_class(self):
        if self.action == "list":
            return DeviceListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return DeviceCreateUpdateSerializer
        return DeviceDetailSerializer

    @action(detail=True, methods=["get"], permission_classes=[ReadOnlyPermission])
    def ports(self, request, pk=None):
        """Get all interfaces/ports for this device."""
        device = self.get_object()
        qs = device.interfaces.select_related("optics").all().order_by("ifindex")
        return Response(InterfaceSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=True, methods=["get"], permission_classes=[ReadOnlyPermission])
    def neighbors(self, request, pk=None):
        """Get all neighbor links for this device."""
        device = self.get_object()
        qs = device.neighbor_links.select_related("local_interface").all().order_by("-last_seen")
        return Response(NeighborLinkSerializer(qs, many=True, context={"request": request}).data)


# Backward compatibility alias
SwitchViewSet = DeviceViewSet


# -------------------------
# Interfaces
# -------------------------


class InterfaceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Interface.objects.select_related("device", "optics").all()
    serializer_class = InterfaceSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchPortFilter
    search_fields = ["name", "description", "alias", "device__hostname", "device__ip"]
    ordering_fields = ["device", "ifindex", "name", "oper", "admin", "speed", "polled_at"]
    ordering = ["device", "ifindex"]


class NeighborLinkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NeighborLink.objects.select_related("local_device", "local_interface").all()
    serializer_class = NeighborLinkSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SwitchNeighborFilter
    search_fields = ["remote_mac", "remote_port", "local_device__hostname", "local_device__ip"]
    ordering_fields = ["last_seen", "id"]
    ordering = ["-last_seen"]


class InterfaceBandwidthSampleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InterfaceBandwidthSample.objects.select_related("interface", "interface__device").all()
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
        total_devices = Device.objects.count()
        online_devices = Device.objects.filter(status=True).count()
        offline_devices = Device.objects.filter(status=False).count()

        total_ports = Interface.objects.count()
        active_ports = Interface.objects.filter(oper=1).count()

        total_branches = Branch.objects.count()
        total_ats = Ats.objects.count()

        uptime_percentage = (online_devices / total_devices * 100) if total_devices else 0.0

        payload = {
            "total_devices": total_devices,
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "warning_devices": 0,
            "total_ports": total_ports,
            "active_ports": active_ports,
            "total_branches": total_branches,
            "total_ats": total_ats,
            "uptime_percentage": uptime_percentage,
            "last_updated": timezone.now(),
        }
        return Response(DashboardStatsSerializer(payload).data)


# -------------------------
# Optical Signal Monitoring
# -------------------------


class OpticalMonitoringViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for optical signal monitoring.
    
    Provides:
    - GET /optical/ - List all interfaces with optics data
    - GET /optical/{id}/ - Get single interface optics detail
    - GET /optical/summary/ - Get summary statistics
    - GET /optical/critical/ - List interfaces with critical signal
    - GET /optical/warning/ - List interfaces with warning signal
    - GET /optical/by-switch/{switch_id}/ - List optics for specific switch
    """
    
    serializer_class = OpticalInterfaceSerializer
    permission_classes = [ReadOnlyPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = OpticalInterfaceFilter
    search_fields = [
        "name", "description", "alias",
        "device__hostname", "device__ip",
        "optics__sfp_vendor", "optics__part_number",
    ]
    ordering_fields = [
        "device__hostname", "ifindex", "name",
        "optics__rx_dbm", "optics__tx_dbm",
        "optics__polled_at", "polled_at",
    ]
    ordering = ["optics__rx_dbm"]  # Default: worst signal first

    def get_queryset(self):
        return (
            Interface.objects
            .select_related(
                "device",
                "device__ats",
                "device__ats__branch",
                "device__model",
                "optics",
            )
            .filter(optics__isnull=False)  # Only interfaces with optics record
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get summary statistics for optical monitoring dashboard."""
        from django.db.models import Avg, Min, Max

        # Base queryset - interfaces with optics
        qs = Interface.objects.filter(optics__isnull=False)

        total_optical_ports = qs.count()
        ports_with_signal = qs.exclude(optics__rx_dbm__isnull=True).count()

        # Signal status counts
        critical_ports = qs.filter(optics__rx_dbm__lte=-25).count()
        warning_ports = qs.filter(optics__rx_dbm__gt=-25, optics__rx_dbm__lte=-20).count()
        normal_ports = qs.filter(optics__rx_dbm__gt=-20).count()
        unknown_ports = qs.filter(optics__rx_dbm__isnull=True).count()

        # Aggregations
        agg = InterfaceOptics.objects.exclude(rx_dbm__isnull=True).aggregate(
            avg_rx=Avg("rx_dbm"),
            min_rx=Min("rx_dbm"),
            max_rx=Max("rx_dbm"),
        )

        payload = {
            "total_optical_ports": total_optical_ports,
            "ports_with_signal": ports_with_signal,
            "critical_ports": critical_ports,
            "warning_ports": warning_ports,
            "normal_ports": normal_ports,
            "unknown_ports": unknown_ports,
            "avg_rx_dbm": round(agg["avg_rx"], 2) if agg["avg_rx"] else None,
            "min_rx_dbm": agg["min_rx"],
            "max_rx_dbm": agg["max_rx"],
            "last_updated": timezone.now(),
        }
        return Response(OpticalSummarySerializer(payload).data)

    @action(detail=False, methods=["get"])
    def critical(self, request):
        """List interfaces with critical signal level (RX <= -25 dBm)."""
        qs = self.get_queryset().filter(optics__rx_dbm__lte=-25).order_by("optics__rx_dbm")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def warning(self, request):
        """List interfaces with warning signal level (-25 < RX <= -20 dBm)."""
        qs = (
            self.get_queryset()
            .filter(optics__rx_dbm__gt=-25, optics__rx_dbm__lte=-20)
            .order_by("optics__rx_dbm")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-device/(?P<device_id>[^/.]+)")
    def by_device(self, request, device_id=None):
        """List optical interfaces for a specific device."""
        qs = self.get_queryset().filter(device_id=device_id).order_by("ifindex")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-branch/(?P<branch_id>[^/.]+)")
    def by_branch(self, request, branch_id=None):
        """List optical interfaces for a specific branch."""
        qs = (
            self.get_queryset()
            .filter(device__ats__branch_id=branch_id)
            .order_by("optics__rx_dbm")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def export(self, request):
        """Export optical data as JSON (for frontend Excel generation or direct download)."""
        qs = self.filter_queryset(self.get_queryset())[:1000]  # Limit for export
        serializer = self.get_serializer(qs, many=True)
        return Response({
            "count": len(serializer.data),
            "exported_at": timezone.now(),
            "data": serializer.data,
        })
