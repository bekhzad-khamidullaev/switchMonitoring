"""snmp.api.serializers

Serializers aligned with the existing project models in `snmp.models`.

Important: this project uses the normalized schema:
- Ats (not ATS)
- Device fields: hostname, ip, device_mac, created, last_update, status (bool)
- Interface (not SwitchPort)
- NeighborLink (not SwitchNeighbor)
- InterfaceBandwidthSample (not BandwidthSample)

These serializers are intentionally pragmatic: they cover the fields actually
present in the DB schema and used by the Flowbite frontend.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from snmp.models import (
    Ats,
    Branch,
    HostGroup,
    Vendor,
    DeviceModel,
    Device,
    Interface,
    InterfaceOptics,
    NeighborLink,
    InterfaceBandwidthSample,
)

# Backward compatibility aliases
SwitchModel = DeviceModel
Switch = Device


User = get_user_model()


# -------------------------
# Reference serializers
# -------------------------


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name"]


class AtsSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)

    class Meta:
        model = Ats
        fields = ["id", "name", "subnet", "branch"]


class HostGroupSerializer(serializers.ModelSerializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    parent = serializers.PrimaryKeyRelatedField(
        queryset=HostGroup.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )

    class Meta:
        model = HostGroup
        fields = ["id", "branch", "parent", "name", "sort_order"]

    def validate(self, attrs):
        # Default missing parent to None
        if 'parent' not in attrs:
            attrs['parent'] = None

        branch = attrs.get('branch')
        parent = attrs.get('parent')
        name = attrs.get('name')

        if branch and name:
            qs = HostGroup.objects.filter(branch=branch, parent=parent, name=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': ['Group with this (branch, parent, name) already exists.']
                })

        return attrs


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name"]


class DeviceModelSerializer(serializers.ModelSerializer):
    """Serializer for DeviceModel (switch/router model types)."""
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        source='vendor',
        queryset=Vendor.objects.all(),
        write_only=True,
        required=True,
    )

    class Meta:
        model = DeviceModel
        fields = [
            "id",
            "vendor",
            "vendor_id",
            "device_model",
            "rx_oid",
            "tx_oid",
            "part_num_oid",
            "sfp_vendor",
            "port_num_oid",
            "max_ports_oid",
            "description_oid",
            "speed_oid",
            "duplex_oid",
            "admin_state_oid",
            "oper_state_oid",
            "required_mibs",
            "ddm_index_type",
            "rx_power_object",
            "tx_power_object",
            "temperature_object",
            "voltage_object",
            "sfp_vendor_object",
            "part_num_object",
            "serial_num_object",
            "power_unit",
            "temperature_unit",
        ]


# Backward compatibility alias
SwitchModelSerializer = DeviceModelSerializer


# -------------------------
# Device / Interface serializers
# -------------------------


class DeviceListSerializer(serializers.ModelSerializer):
    """Serializer for device list views."""
    ats = AtsSerializer(read_only=True)
    model = DeviceModelSerializer(read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "hostname",
            "ip",
            "device_mac",
            "status",
            "created",
            "last_update",
            "uptime",
            "serial_number",
            "soft_version",
            "ats",
            "model",
            "group_name",
        ]


# Backward compatibility alias
SwitchListSerializer = DeviceListSerializer


class InterfaceOpticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterfaceOptics
        fields = [
            "rx_dbm",
            "tx_dbm",
            "temperature_c",
            "voltage_v",
            "sfp_vendor",
            "part_number",
            "serial_number",
            "polled_at",
        ]


class InterfaceSerializer(serializers.ModelSerializer):
    device_id = serializers.IntegerField(source="device.id", read_only=True)
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)
    device_ip = serializers.CharField(source="device.ip", read_only=True)
    # Backward compatibility
    switch_hostname = serializers.CharField(source="device.hostname", read_only=True)
    switch_ip = serializers.CharField(source="device.ip", read_only=True)
    optics = InterfaceOpticsSerializer(read_only=True)

    class Meta:
        model = Interface
        fields = [
            "id",
            "device_id",
            "device_hostname",
            "device_ip",
            "switch_hostname",  # deprecated alias
            "switch_ip",  # deprecated alias
            "ifindex",
            "name",
            "description",
            "alias",
            "iftype",
            "speed",
            "duplex",
            "admin",
            "oper",
            "lastchange",
            "discards_in",
            "discards_out",
            "polled_at",
            "optics",
        ]


class NeighborLinkSerializer(serializers.ModelSerializer):
    local_device_id = serializers.IntegerField(source="local_device.id", read_only=True)
    local_device_hostname = serializers.CharField(source="local_device.hostname", read_only=True)
    local_device_ip = serializers.CharField(source="local_device.ip", read_only=True)
    local_interface_name = serializers.CharField(source="local_interface.name", read_only=True)
    # Backward compatibility aliases
    local_switch_hostname = serializers.CharField(source="local_device.hostname", read_only=True)
    local_switch_ip = serializers.CharField(source="local_device.ip", read_only=True)

    class Meta:
        model = NeighborLink
        fields = [
            "id",
            "local_device_id",
            "local_device_hostname",
            "local_device_ip",
            "local_switch_hostname",  # deprecated
            "local_switch_ip",  # deprecated
            "local_interface",
            "local_interface_name",
            "remote_mac",
            "remote_port",
            "last_seen",
        ]


class DeviceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single device view."""
    ats = AtsSerializer(read_only=True)
    model = DeviceModelSerializer(read_only=True)
    group = HostGroupSerializer(read_only=True)
    interfaces = InterfaceSerializer(many=True, read_only=True)
    neighbor_links = NeighborLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "hostname",
            "ip",
            "device_mac",
            "status",
            "created",
            "last_update",
            "uptime",
            "serial_number",
            "soft_version",
            "snmp_community_ro",
            "snmp_community_rw",
            "ats",
            "model",
            "group",
            "interfaces",
            "neighbor_links",
        ]
        extra_kwargs = {
            "snmp_community_ro": {"write_only": True},
            "snmp_community_rw": {"write_only": True},
        }


# Backward compatibility alias
SwitchDetailSerializer = DeviceDetailSerializer


class DeviceCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating devices."""
    class Meta:
        model = Device
        fields = [
            "id",
            "hostname",
            "ip",
            "device_mac",
            "status",
            "ats",
            "group",
            "model",
            "snmp_community_ro",
            "snmp_community_rw",
            "soft_version",
            "serial_number",
            "uptime",
        ]
        extra_kwargs = {
            "snmp_community_ro": {"write_only": True, "required": False},
            "snmp_community_rw": {"write_only": True, "required": False},
        }


# Backward compatibility alias
SwitchCreateUpdateSerializer = DeviceCreateUpdateSerializer


# -------------------------
# Bandwidth
# -------------------------


class InterfaceBandwidthSampleSerializer(serializers.ModelSerializer):
    interface_name = serializers.CharField(source="interface.name", read_only=True)
    device_id = serializers.IntegerField(source="interface.device_id", read_only=True)
    switch_id = serializers.IntegerField(source="interface.device_id", read_only=True)  # deprecated

    class Meta:
        model = InterfaceBandwidthSample
        fields = [
            "id",
            "interface",
            "interface_name",
            "device_id",
            "switch_id",  # deprecated alias
            "ts",
            "in_bps",
            "out_bps",
            "interval_sec",
            "in_octets",
            "out_octets",
        ]


class DashboardStatsSerializer(serializers.Serializer):
    total_devices = serializers.IntegerField()
    online_devices = serializers.IntegerField()
    offline_devices = serializers.IntegerField()
    # Backward compatibility aliases
    total_switches = serializers.IntegerField(source='total_devices', read_only=True)
    online_switches = serializers.IntegerField(source='online_devices', read_only=True)
    offline_switches = serializers.IntegerField(source='offline_devices', read_only=True)
    total_ports = serializers.IntegerField()
    active_ports = serializers.IntegerField()
    total_branches = serializers.IntegerField()
    total_ats = serializers.IntegerField()
    uptime_percentage = serializers.FloatField()
    last_updated = serializers.DateTimeField()


# -------------------------
# Optical Signal Monitoring
# -------------------------


class OpticalInterfaceSerializer(serializers.ModelSerializer):
    """Serializer for interfaces with optical data for monitoring views."""

    switch_id = serializers.IntegerField(source="switch.id", read_only=True)
    switch_hostname = serializers.CharField(source="switch.hostname", read_only=True)
    switch_ip = serializers.CharField(source="switch.ip", read_only=True)
    branch_name = serializers.SerializerMethodField()
    ats_name = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()

    # Optics data flattened
    rx_dbm = serializers.FloatField(source="optics.rx_dbm", read_only=True, allow_null=True)
    tx_dbm = serializers.FloatField(source="optics.tx_dbm", read_only=True, allow_null=True)
    temperature_c = serializers.FloatField(source="optics.temperature_c", read_only=True, allow_null=True)
    voltage_v = serializers.FloatField(source="optics.voltage_v", read_only=True, allow_null=True)
    sfp_vendor = serializers.CharField(source="optics.sfp_vendor", read_only=True, allow_null=True)
    part_number = serializers.CharField(source="optics.part_number", read_only=True, allow_null=True)
    serial_number = serializers.CharField(source="optics.serial_number", read_only=True, allow_null=True)
    optics_polled_at = serializers.DateTimeField(source="optics.polled_at", read_only=True, allow_null=True)

    # Signal status classification
    signal_status = serializers.SerializerMethodField()

    class Meta:
        model = Interface
        fields = [
            "id",
            "switch_id",
            "switch_hostname",
            "switch_ip",
            "branch_name",
            "ats_name",
            "model_name",
            "ifindex",
            "name",
            "description",
            "alias",
            "iftype",
            "speed",
            "admin",
            "oper",
            "polled_at",
            # Optics
            "rx_dbm",
            "tx_dbm",
            "temperature_c",
            "voltage_v",
            "sfp_vendor",
            "part_number",
            "serial_number",
            "optics_polled_at",
            "signal_status",
        ]

    def get_branch_name(self, obj):
        if obj.switch and obj.switch.ats and obj.switch.ats.branch:
            return obj.switch.ats.branch.name
        return None

    def get_ats_name(self, obj):
        if obj.switch and obj.switch.ats:
            return obj.switch.ats.name
        return None

    def get_model_name(self, obj):
        if obj.switch and obj.switch.model:
            return obj.switch.model.device_model
        return None

    def get_signal_status(self, obj):
        """Classify signal level: critical / warning / normal / unknown."""
        optics = getattr(obj, 'optics', None)
        if not optics:
            return "unknown"

        rx = optics.rx_dbm
        if rx is None:
            return "unknown"

        # Thresholds (configurable in future)
        if rx <= -25:
            return "critical"
        elif rx <= -20:
            return "warning"
        else:
            return "normal"


class OpticalSummarySerializer(serializers.Serializer):
    """Summary statistics for optical monitoring dashboard."""

    total_optical_ports = serializers.IntegerField()
    ports_with_signal = serializers.IntegerField()
    critical_ports = serializers.IntegerField()
    warning_ports = serializers.IntegerField()
    normal_ports = serializers.IntegerField()
    unknown_ports = serializers.IntegerField()
    avg_rx_dbm = serializers.FloatField(allow_null=True)
    min_rx_dbm = serializers.FloatField(allow_null=True)
    max_rx_dbm = serializers.FloatField(allow_null=True)
    last_updated = serializers.DateTimeField()


class OpticsHistorySampleSerializer(serializers.ModelSerializer):
    """Serializer for optical signal history samples."""

    class Meta:
        from snmp.models import OpticsHistorySample
        model = OpticsHistorySample
        fields = ['id', 'interface', 'ts', 'rx_dbm', 'tx_dbm', 'temperature_c', 'voltage_v']


class OpticsAlertSerializer(serializers.ModelSerializer):
    """Serializer for optical alerts."""
    
    device_hostname = serializers.CharField(source='interface.device.hostname', read_only=True)
    device_ip = serializers.CharField(source='interface.device.ip', read_only=True)
    interface_name = serializers.CharField(source='interface.name', read_only=True)

    class Meta:
        from snmp.models import OpticsAlert
        model = OpticsAlert
        fields = [
            'id', 'interface', 'device_hostname', 'device_ip', 'interface_name',
            'severity', 'status', 'rx_dbm', 'threshold', 'message',
            'created_at', 'acknowledged_at', 'resolved_at', 'acknowledged_by'
        ]
        read_only_fields = ['created_at']


class TaskStatusSerializer(serializers.Serializer):
    """Serializer for Celery task status response."""
    
    task_id = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()
    started_at = serializers.DateTimeField()


class OpticsHistoryChartSerializer(serializers.Serializer):
    """Serializer for chart data points."""
    
    ts = serializers.DateTimeField()
    rx_dbm = serializers.FloatField(allow_null=True)
    tx_dbm = serializers.FloatField(allow_null=True)
    temperature_c = serializers.FloatField(allow_null=True)
