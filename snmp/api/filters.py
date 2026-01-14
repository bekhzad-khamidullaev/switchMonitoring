"""
Custom filters for SNMP API endpoints.
Provides advanced filtering capabilities using django-filter.
"""
import django_filters
from django.db.models import Q
from snmp.models import (
    Ats as ATS,
    Branch, 
    HostGroup, 
    Device,
    Interface,
    NeighborLink,
    DeviceModel,
    InterfaceBandwidthSample as BandwidthSample
)

# Backward compatibility aliases
Switch = Device
SwitchPort = Interface
SwitchNeighbor = NeighborLink
SwitchModel = DeviceModel


class ATSFilter(django_filters.FilterSet):
    """Filter for ATS model."""
    name = django_filters.CharFilter(lookup_expr='icontains')
    code = django_filters.CharFilter(lookup_expr='icontains')
    subnet = django_filters.CharFilter(lookup_expr='icontains')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = ATS
        fields = ['name', 'code', 'subnet']


class BranchFilter(django_filters.FilterSet):
    """Filter for Branch model."""
    name = django_filters.CharFilter(lookup_expr='icontains')
    code = django_filters.CharFilter(lookup_expr='icontains')
    ats = django_filters.NumberFilter(field_name='ats__id')
    ats_name = django_filters.CharFilter(field_name='ats__name', lookup_expr='icontains')
    address = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    has_switches = django_filters.BooleanFilter(method='filter_has_switches')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = Branch
        fields = ['name', 'code', 'ats', 'is_active']
    
    def filter_has_switches(self, queryset, name, value):
        """Filter branches that have switches."""
        if value:
            return queryset.filter(switch__isnull=False).distinct()
        return queryset.filter(switch__isnull=True).distinct()


class HostGroupFilter(django_filters.FilterSet):
    """Filter for HostGroup model."""
    name = django_filters.CharFilter(lookup_expr='icontains')
    parent = django_filters.NumberFilter(field_name='parent__id')
    parent_isnull = django_filters.BooleanFilter(field_name='parent', lookup_expr='isnull')
    level = django_filters.NumberFilter()
    level_gte = django_filters.NumberFilter(field_name='level', lookup_expr='gte')
    level_lte = django_filters.NumberFilter(field_name='level', lookup_expr='lte')
    
    class Meta:
        model = HostGroup
        fields = ['name', 'parent', 'level']


class SwitchModelFilter(django_filters.FilterSet):
    """Filter for SwitchModel."""
    vendor = django_filters.CharFilter(lookup_expr='icontains')
    model = django_filters.CharFilter(lookup_expr='icontains')
    max_ports_gte = django_filters.NumberFilter(field_name='max_ports', lookup_expr='gte')
    max_ports_lte = django_filters.NumberFilter(field_name='max_ports', lookup_expr='lte')
    
    class Meta:
        model = SwitchModel
        fields = ['vendor', 'model']


class DeviceFilter(django_filters.FilterSet):
    """Advanced filter for Device model (switches, routers, etc.)."""
    # Basic text filters
    hostname = django_filters.CharFilter(lookup_expr='icontains')
    ip = django_filters.CharFilter(lookup_expr='icontains')
    device_mac = django_filters.CharFilter(lookup_expr='icontains')
    serial_number = django_filters.CharFilter(lookup_expr='icontains')
    
    # Status filters (Device.status is BooleanField)
    status = django_filters.BooleanFilter()
    
    # Relationship filters
    ats = django_filters.NumberFilter(field_name='ats__id')
    ats_name = django_filters.CharFilter(field_name='ats__name', lookup_expr='icontains')
    branch = django_filters.NumberFilter(field_name='ats__branch__id')
    branch_name = django_filters.CharFilter(field_name='ats__branch__name', lookup_expr='icontains')
    group = django_filters.NumberFilter(field_name='group__id')
    group_name = django_filters.CharFilter(field_name='group__name', lookup_expr='icontains')
    model = django_filters.NumberFilter(field_name='model__id')
    model_name = django_filters.CharFilter(field_name='model__device_model', lookup_expr='icontains')
    
    # Date filters
    last_update_after = django_filters.DateTimeFilter(field_name='last_update', lookup_expr='gte')
    last_update_before = django_filters.DateTimeFilter(field_name='last_update', lookup_expr='lte')
    created_after = django_filters.DateTimeFilter(field_name='created', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created', lookup_expr='lte')
    
    # Custom filters
    search = django_filters.CharFilter(method='search_filter')
    online = django_filters.BooleanFilter(method='filter_online')
    
    class Meta:
        model = Device
        fields = ['hostname', 'ip', 'status', 'ats', 'group', 'model']
    
    def search_filter(self, queryset, name, value):
        """Global search across multiple fields."""
        return queryset.filter(
            Q(hostname__icontains=value) |
            Q(ip__icontains=value) |
            Q(device_mac__icontains=value) |
            Q(serial_number__icontains=value)
        )
    
    def filter_online(self, queryset, name, value):
        """Filter online/offline devices."""
        return queryset.filter(status=value)


# Backward compatibility alias
SwitchFilter = DeviceFilter


class InterfaceFilter(django_filters.FilterSet):
    """Filter for Interface model."""
    device = django_filters.NumberFilter(field_name='device__id')
    device_hostname = django_filters.CharFilter(field_name='device__hostname', lookup_expr='icontains')
    device_ip = django_filters.CharFilter(field_name='device__ip', lookup_expr='icontains')
    
    name = django_filters.CharFilter(lookup_expr='icontains')
    ifindex = django_filters.NumberFilter()
    iftype = django_filters.NumberFilter()
    oper = django_filters.NumberFilter()
    admin = django_filters.NumberFilter()
    
    speed = django_filters.NumberFilter()
    speed_gte = django_filters.NumberFilter(field_name='speed', lookup_expr='gte')
    speed_lte = django_filters.NumberFilter(field_name='speed', lookup_expr='lte')
    
    description = django_filters.CharFilter(lookup_expr='icontains')
    alias = django_filters.CharFilter(lookup_expr='icontains')
    
    # Optical filters
    has_optics = django_filters.BooleanFilter(method='filter_has_optics')
    optical_weak_signal = django_filters.BooleanFilter(method='filter_optical_weak_signal')
    
    # Discards filter
    has_discards = django_filters.BooleanFilter(method='filter_has_discards')
    
    class Meta:
        model = Interface
        fields = ['device', 'ifindex', 'iftype', 'oper', 'admin']
    
    def filter_has_optics(self, queryset, name, value):
        """Filter interfaces with optical information."""
        if value:
            return queryset.filter(optics__isnull=False)
        return queryset.filter(optics__isnull=True)
    
    def filter_optical_weak_signal(self, queryset, name, value):
        """Filter interfaces with weak optical signal."""
        if value:
            return queryset.filter(optics__rx_dbm__lt=-20)
        return queryset
    
    def filter_has_discards(self, queryset, name, value):
        """Filter interfaces with discards."""
        if value:
            return queryset.filter(
                Q(discards_in__gt=0) | Q(discards_out__gt=0)
            )
        return queryset.filter(discards_in=0, discards_out=0)


# Backward compatibility alias
SwitchPortFilter = InterfaceFilter


class NeighborLinkFilter(django_filters.FilterSet):
    """Filter for NeighborLink model."""
    local_device = django_filters.NumberFilter(field_name='local_device__id')
    local_device_hostname = django_filters.CharFilter(field_name='local_device__hostname', lookup_expr='icontains')
    local_interface = django_filters.NumberFilter(field_name='local_interface__id')
    
    remote_mac = django_filters.CharFilter(lookup_expr='icontains')
    remote_port = django_filters.CharFilter(lookup_expr='icontains')
    
    last_seen_after = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='gte')
    last_seen_before = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='lte')
    
    class Meta:
        model = NeighborLink
        fields = ['local_device', 'local_interface']


# Backward compatibility alias
SwitchNeighborFilter = NeighborLinkFilter


class BandwidthSampleFilter(django_filters.FilterSet):
    """Filter for BandwidthSample model."""
    device = django_filters.NumberFilter(field_name='interface__device__id')
    device_hostname = django_filters.CharFilter(field_name='interface__device__hostname', lookup_expr='icontains')
    interface = django_filters.NumberFilter(field_name='interface__id')
    interface_name = django_filters.CharFilter(field_name='interface__name', lookup_expr='icontains')
    
    ts_after = django_filters.DateTimeFilter(field_name='ts', lookup_expr='gte')
    ts_before = django_filters.DateTimeFilter(field_name='ts', lookup_expr='lte')
    
    in_bps_gte = django_filters.NumberFilter(field_name='in_bps', lookup_expr='gte')
    out_bps_gte = django_filters.NumberFilter(field_name='out_bps', lookup_expr='gte')
    
    class Meta:
        model = BandwidthSample
        fields = ['interface']


class OpticalInterfaceFilter(django_filters.FilterSet):
    """Filter for optical interfaces monitoring."""
    
    # Device filters
    device = django_filters.NumberFilter(field_name='device__id')
    device_hostname = django_filters.CharFilter(field_name='device__hostname', lookup_expr='icontains')
    device_ip = django_filters.CharFilter(field_name='device__ip', lookup_expr='icontains')
    
    # Location filters
    branch = django_filters.NumberFilter(field_name='device__ats__branch__id')
    branch_name = django_filters.CharFilter(field_name='device__ats__branch__name', lookup_expr='icontains')
    ats = django_filters.NumberFilter(field_name='device__ats__id')
    ats_name = django_filters.CharFilter(field_name='device__ats__name', lookup_expr='icontains')
    
    # Interface filters
    ifindex = django_filters.NumberFilter()
    name = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    alias = django_filters.CharFilter(lookup_expr='icontains')
    oper = django_filters.NumberFilter()
    admin = django_filters.NumberFilter()
    
    # Optical signal filters
    rx_dbm_lte = django_filters.NumberFilter(field_name='optics__rx_dbm', lookup_expr='lte')
    rx_dbm_gte = django_filters.NumberFilter(field_name='optics__rx_dbm', lookup_expr='gte')
    tx_dbm_lte = django_filters.NumberFilter(field_name='optics__tx_dbm', lookup_expr='lte')
    tx_dbm_gte = django_filters.NumberFilter(field_name='optics__tx_dbm', lookup_expr='gte')
    
    # SFP filters
    sfp_vendor = django_filters.CharFilter(field_name='optics__sfp_vendor', lookup_expr='icontains')
    part_number = django_filters.CharFilter(field_name='optics__part_number', lookup_expr='icontains')
    
    # Status filters
    has_optics = django_filters.BooleanFilter(method='filter_has_optics')
    signal_status = django_filters.CharFilter(method='filter_signal_status')
    only_optical = django_filters.BooleanFilter(method='filter_only_optical')
    
    class Meta:
        model = Interface
        fields = ['device', 'ifindex', 'oper', 'admin']
    
    def filter_has_optics(self, queryset, name, value):
        """Filter interfaces that have optics record."""
        if value:
            return queryset.filter(optics__isnull=False)
        return queryset.filter(optics__isnull=True)
    
    def filter_only_optical(self, queryset, name, value):
        """Filter only interfaces with both RX and TX signal present."""
        if value:
            return queryset.exclude(
                optics__rx_dbm__isnull=True
            ).exclude(
                optics__tx_dbm__isnull=True
            )
        return queryset
    
    def filter_signal_status(self, queryset, name, value):
        """Filter by signal status: critical, warning, normal, unknown."""
        if value == 'critical':
            return queryset.filter(optics__rx_dbm__lte=-25)
        elif value == 'warning':
            return queryset.filter(optics__rx_dbm__gt=-25, optics__rx_dbm__lte=-20)
        elif value == 'normal':
            return queryset.filter(optics__rx_dbm__gt=-20)
        elif value == 'unknown':
            return queryset.filter(Q(optics__isnull=True) | Q(optics__rx_dbm__isnull=True))
        return queryset
