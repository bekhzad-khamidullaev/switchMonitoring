"""snmp.api.serializers

Serializers aligned with the existing project models in `snmp.models`.

Important: this project uses the legacy/normalized schema:
- Ats (not ATS)
- Switch fields: hostname, ip, switch_mac, created, last_update, status (bool)
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
    SwitchModel,
    Switch,
    Interface,
    InterfaceOptics,
    NeighborLink,
    InterfaceBandwidthSample,
)


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


class SwitchModelSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        source='vendor',
        queryset=Vendor.objects.all(),
        write_only=True,
        required=True,
    )

    class Meta:
        model = SwitchModel
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


# -------------------------
# Switch / Interface serializers
# -------------------------


class SwitchListSerializer(serializers.ModelSerializer):
    ats = AtsSerializer(read_only=True)
    model = SwitchModelSerializer(read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Switch
        fields = [
            "id",
            "hostname",
            "ip",
            "switch_mac",
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
    switch_hostname = serializers.CharField(source="switch.hostname", read_only=True)
    switch_ip = serializers.CharField(source="switch.ip", read_only=True)
    optics = InterfaceOpticsSerializer(read_only=True)

    class Meta:
        model = Interface
        fields = [
            "id",
            "switch",
            "switch_hostname",
            "switch_ip",
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
    local_switch_hostname = serializers.CharField(source="local_switch.hostname", read_only=True)
    local_switch_ip = serializers.CharField(source="local_switch.ip", read_only=True)
    local_interface_name = serializers.CharField(source="local_interface.name", read_only=True)

    class Meta:
        model = NeighborLink
        fields = [
            "id",
            "local_switch",
            "local_switch_hostname",
            "local_switch_ip",
            "local_interface",
            "local_interface_name",
            "remote_mac",
            "remote_port",
            "last_seen",
        ]


class SwitchDetailSerializer(serializers.ModelSerializer):
    ats = AtsSerializer(read_only=True)
    model = SwitchModelSerializer(read_only=True)
    group = HostGroupSerializer(read_only=True)
    interfaces = InterfaceSerializer(many=True, read_only=True)
    neighbor_links = NeighborLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Switch
        fields = [
            "id",
            "hostname",
            "ip",
            "switch_mac",
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


class SwitchCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Switch
        fields = [
            "id",
            "hostname",
            "ip",
            "switch_mac",
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


# -------------------------
# Bandwidth
# -------------------------


class InterfaceBandwidthSampleSerializer(serializers.ModelSerializer):
    interface_name = serializers.CharField(source="interface.name", read_only=True)
    switch_id = serializers.IntegerField(source="interface.switch_id", read_only=True)

    class Meta:
        model = InterfaceBandwidthSample
        fields = [
            "id",
            "interface",
            "interface_name",
            "switch_id",
            "ts",
            "in_bps",
            "out_bps",
            "interval_sec",
            "in_octets",
            "out_octets",
        ]


class DashboardStatsSerializer(serializers.Serializer):
    total_switches = serializers.IntegerField()
    online_switches = serializers.IntegerField()
    offline_switches = serializers.IntegerField()
    total_ports = serializers.IntegerField()
    active_ports = serializers.IntegerField()
    total_branches = serializers.IntegerField()
    total_ats = serializers.IntegerField()
    uptime_percentage = serializers.FloatField()
    last_updated = serializers.DateTimeField()
