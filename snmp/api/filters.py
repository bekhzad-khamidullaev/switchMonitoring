"""
Custom filters for SNMP API endpoints.
Provides advanced filtering capabilities using django-filter.
"""
import django_filters
from django.db.models import Q
from snmp.models import (
    Ats as ATS,  # Alias для совместимости
    Branch, 
    HostGroup, 
    Switch, 
    Interface as SwitchPort,  # Используем Interface вместо SwitchPort
    NeighborLink as SwitchNeighbor,  # Используем NeighborLink вместо SwitchNeighbor
    SwitchModel, 
    InterfaceBandwidthSample as BandwidthSample  # Используем InterfaceBandwidthSample
)


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


class SwitchFilter(django_filters.FilterSet):
    """Advanced filter for Switch model."""
    # Basic text filters
    name = django_filters.CharFilter(lookup_expr='icontains')
    ip_address = django_filters.CharFilter(lookup_expr='icontains')
    mac_address = django_filters.CharFilter(lookup_expr='icontains')
    serial_number = django_filters.CharFilter(lookup_expr='icontains')
    location = django_filters.CharFilter(lookup_expr='icontains')
    
    # Status filters (Switch.status is BooleanField in existing model)
    status = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()
    is_monitored = django_filters.BooleanFilter()
    
    # Relationship filters
    ats = django_filters.NumberFilter(field_name='ats__id')
    ats_name = django_filters.CharFilter(field_name='ats__name', lookup_expr='icontains')
    branch = django_filters.NumberFilter(field_name='branch__id')
    branch_name = django_filters.CharFilter(field_name='branch__name', lookup_expr='icontains')
    host_group = django_filters.NumberFilter(field_name='host_group__id')
    host_group_name = django_filters.CharFilter(field_name='host_group__name', lookup_expr='icontains')
    device_model = django_filters.NumberFilter(field_name='device_model__id')
    device_model_name = django_filters.CharFilter(field_name='device_model__model', lookup_expr='icontains')
    
    # Date filters
    last_seen_after = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='gte')
    last_seen_before = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='lte')
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Numeric range filters
    cpu_usage_gte = django_filters.NumberFilter(field_name='cpu_usage', lookup_expr='gte')
    cpu_usage_lte = django_filters.NumberFilter(field_name='cpu_usage', lookup_expr='lte')
    memory_usage_gte = django_filters.NumberFilter(field_name='memory_usage', lookup_expr='gte')
    memory_usage_lte = django_filters.NumberFilter(field_name='memory_usage', lookup_expr='lte')
    temperature_gte = django_filters.NumberFilter(field_name='temperature', lookup_expr='gte')
    temperature_lte = django_filters.NumberFilter(field_name='temperature', lookup_expr='lte')
    
    # SNMP filters
    snmp_version = django_filters.ChoiceFilter(choices=[('1', 'v1'), ('2c', 'v2c'), ('3', 'v3')])
    
    # Custom filters
    search = django_filters.CharFilter(method='search_filter')
    has_issues = django_filters.BooleanFilter(method='filter_has_issues')
    online = django_filters.BooleanFilter(method='filter_online')
    
    class Meta:
        model = Switch
        fields = [
            'name', 'ip_address', 'status', 'ats', 'branch',
            'host_group', 'device_model', 'is_active', 'is_monitored'
        ]
    
    def search_filter(self, queryset, name, value):
        """Global search across multiple fields."""
        return queryset.filter(
            Q(name__icontains=value) |
            Q(ip_address__icontains=value) |
            Q(mac_address__icontains=value) |
            Q(serial_number__icontains=value) |
            Q(location__icontains=value) |
            Q(description__icontains=value)
        )
    
    def filter_has_issues(self, queryset, name, value):
        """Filter switches with issues (high CPU, memory, temperature)."""
        if value:
            return queryset.filter(
                Q(cpu_usage__gte=80) |
                Q(memory_usage__gte=80) |
                Q(temperature__gte=70) |
                Q(status='error')
            )
        return queryset.exclude(
            Q(cpu_usage__gte=80) |
            Q(memory_usage__gte=80) |
            Q(temperature__gte=70) |
            Q(status='error')
        )
    
    def filter_online(self, queryset, name, value):
        """Filter online/offline switches."""
        if value:
            return queryset.filter(status='online')
        return queryset.exclude(status='online')


class SwitchPortFilter(django_filters.FilterSet):
    """Filter for SwitchPort model."""
    switch = django_filters.NumberFilter(field_name='switch__id')
    switch_name = django_filters.CharFilter(field_name='switch__name', lookup_expr='icontains')
    switch_ip = django_filters.CharFilter(field_name='switch__ip_address', lookup_expr='icontains')
    
    port_name = django_filters.CharFilter(lookup_expr='icontains')
    iftype = django_filters.NumberFilter()
    # Status filters (Interface uses numeric fields)
    oper = django_filters.NumberFilter()
    admin = django_filters.NumberFilter()
    
    speed = django_filters.NumberFilter()
    speed_gte = django_filters.NumberFilter(field_name='speed', lookup_expr='gte')
    speed_lte = django_filters.NumberFilter(field_name='speed', lookup_expr='lte')
    
    vlan = django_filters.NumberFilter()
    description = django_filters.CharFilter(lookup_expr='icontains')
    mac_address = django_filters.CharFilter(lookup_expr='icontains')
    
    # POE filters
    poe_enabled = django_filters.BooleanFilter()
    poe_power_gte = django_filters.NumberFilter(field_name='poe_power', lookup_expr='gte')
    
    # Optical filters
    has_optical = django_filters.BooleanFilter(method='filter_has_optical')
    optical_weak_signal = django_filters.BooleanFilter(method='filter_optical_weak_signal')
    
    # Status filters
    has_errors = django_filters.BooleanFilter(method='filter_has_errors')
    is_uplink = django_filters.BooleanFilter(method='filter_is_uplink')
    
    class Meta:
        model = SwitchPort
        fields = ['switch', 'iftype', 'oper', 'admin']
    
    def filter_has_optical(self, queryset, name, value):
        """Filter ports with optical information."""
        if value:
            return queryset.filter(
                port_type='sfp',
                optical_tx_power__isnull=False
            )
        return queryset.exclude(
            port_type='sfp',
            optical_tx_power__isnull=False
        )
    
    def filter_optical_weak_signal(self, queryset, name, value):
        """Filter ports with weak optical signal."""
        if value:
            return queryset.filter(
                port_type='sfp',
                optical_rx_power__lt=-20
            )
        return queryset
    
    def filter_has_errors(self, queryset, name, value):
        """Filter ports with errors."""
        if value:
            return queryset.filter(
                Q(in_errors__gt=0) | Q(out_errors__gt=0)
            )
        return queryset.filter(in_errors=0, out_errors=0)
    
    def filter_is_uplink(self, queryset, name, value):
        """Filter uplink ports."""
        if value:
            return queryset.filter(port_type='uplink')
        return queryset.exclude(port_type='uplink')


class SwitchNeighborFilter(django_filters.FilterSet):
    """Filter for SwitchNeighbor model."""
    switch = django_filters.NumberFilter(field_name='switch__id')
    switch_name = django_filters.CharFilter(field_name='switch__name', lookup_expr='icontains')
    port = django_filters.NumberFilter(field_name='port__id')
    
    neighbor_system_name = django_filters.CharFilter(lookup_expr='icontains')
    neighbor_device_id = django_filters.CharFilter(lookup_expr='icontains')
    # No protocol field in NeighborLink model, remove this filter
    
    discovered_after = django_filters.DateTimeFilter(field_name='discovered_at', lookup_expr='gte')
    discovered_before = django_filters.DateTimeFilter(field_name='discovered_at', lookup_expr='lte')
    last_seen_after = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='gte')
    last_seen_before = django_filters.DateTimeFilter(field_name='last_seen', lookup_expr='lte')
    
    class Meta:
        model = SwitchNeighbor
        fields = ['local_switch']


class BandwidthSampleFilter(django_filters.FilterSet):
    """Filter for BandwidthSample model."""
    switch = django_filters.NumberFilter(field_name='switch__id')
    switch_name = django_filters.CharFilter(field_name='switch__name', lookup_expr='icontains')
    port = django_filters.NumberFilter(field_name='port__id')
    port_name = django_filters.CharFilter(field_name='port__port_name', lookup_expr='icontains')
    
    timestamp_after = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_before = django_filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    
    in_bps_gte = django_filters.NumberFilter(field_name='in_bps', lookup_expr='gte')
    out_bps_gte = django_filters.NumberFilter(field_name='out_bps', lookup_expr='gte')
    
    in_utilization_gte = django_filters.NumberFilter(field_name='in_utilization', lookup_expr='gte')
    out_utilization_gte = django_filters.NumberFilter(field_name='out_utilization', lookup_expr='gte')
    
    high_utilization = django_filters.BooleanFilter(method='filter_high_utilization')
    
    class Meta:
        model = BandwidthSample
        fields = ['interface']  # InterfaceBandwidthSample uses 'interface' and 'ts'
    
    def filter_high_utilization(self, queryset, name, value):
        """Filter samples with high utilization (>80%)."""
        if value:
            return queryset.filter(
                Q(in_utilization__gte=80) | Q(out_utilization__gte=80)
            )
        return queryset.filter(
            in_utilization__lt=80, out_utilization__lt=80
        )
