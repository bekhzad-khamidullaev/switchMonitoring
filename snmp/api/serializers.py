from rest_framework import serializers

from snmp.models import (
    Switch,
    SwitchModel,
    Vendor,
    Interface,
    InterfaceOptics,
    InterfaceL2,
    MacEntry,
    InterfaceBandwidthSample,
)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'name']


class SwitchModelSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)

    class Meta:
        model = SwitchModel
        fields = ['id', 'device_model', 'vendor']


class SwitchSerializer(serializers.ModelSerializer):
    model = SwitchModelSerializer(read_only=True)
    ats = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    min_rx = serializers.FloatField(read_only=True)
    min_tx = serializers.FloatField(read_only=True)

    class Meta:
        model = Switch
        fields = ['id', 'hostname', 'ip', 'status', 'uptime', 'model', 'ats', 'branch', 'min_rx', 'min_tx']

    def get_ats(self, obj):
        if not obj.ats_id:
            return None
        return {'id': obj.ats_id, 'name': getattr(obj.ats, 'name', None)}

    def get_branch(self, obj):
        if not obj.ats_id or not getattr(obj.ats, 'branch_id', None):
            return None
        return {'id': obj.ats.branch_id, 'name': getattr(obj.ats.branch, 'name', None)}


class InterfaceOpticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterfaceOptics
        fields = ['rx_dbm', 'tx_dbm', 'sfp_vendor', 'part_number', 'serial_number', 'temperature_c', 'voltage_v', 'polled_at']


class InterfaceL2Serializer(serializers.ModelSerializer):
    class Meta:
        model = InterfaceL2
        fields = ['pvid', 'tagged_vlans', 'untagged_vlans', 'mac_count']


class InterfaceSerializer(serializers.ModelSerializer):
    optics = InterfaceOpticsSerializer(read_only=True)
    l2 = InterfaceL2Serializer(read_only=True)

    class Meta:
        model = Interface
        fields = [
            'id', 'switch', 'ifindex', 'name', 'description', 'alias',
            'iftype', 'speed', 'admin', 'oper', 'lastchange', 'polled_at',
            'optics', 'l2',
        ]


class MacEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MacEntry
        fields = ['id', 'switch', 'interface', 'mac', 'vlan', 'ip', 'first_seen', 'last_seen']


class BandwidthSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterfaceBandwidthSample
        fields = ['id', 'interface', 'ts', 'in_bps', 'out_bps', 'interval_sec', 'in_octets', 'out_octets']
