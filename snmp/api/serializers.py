from rest_framework import serializers

from snmp.models import Device, MetricSample, MetricSubscription, Switch


class DeviceOnboardSerializer(serializers.Serializer):
    ip = serializers.IPAddressField(required=False)
    switch_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        ip = attrs.get('ip')
        switch_id = attrs.get('switch_id')
        if not ip and not switch_id:
            raise serializers.ValidationError('Provide ip or switch_id')
        return attrs


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = [
            'id', 'ip', 'hostname', 'vendor', 'model', 'firmware', 'sys_object_id',
            'snmp_version', 'auth_profile', 'status', 'profile_id', 'last_discovered_at',
            'switch_id',
        ]


class MetricSubscriptionSerializer(serializers.ModelSerializer):
    metric_key = serializers.CharField(source='metric.key', read_only=True)
    interface_if_index = serializers.IntegerField(source='interface.if_index', read_only=True)

    class Meta:
        model = MetricSubscription
        fields = [
            'id', 'device_id', 'interface_id', 'interface_if_index', 'metric_id', 'metric_key',
            'binding_id', 'enabled', 'warn_threshold', 'crit_threshold', 'poll_interval_sec',
        ]


class MetricSubscriptionPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetricSubscription
        fields = ['enabled', 'warn_threshold', 'crit_threshold', 'poll_interval_sec']


class MetricSampleSerializer(serializers.ModelSerializer):
    metric_key = serializers.CharField(source='subscription.metric.key', read_only=True)
    interface_if_index = serializers.IntegerField(source='subscription.interface.if_index', read_only=True)

    class Meta:
        model = MetricSample
        fields = ['id', 'subscription_id', 'metric_key', 'interface_if_index', 'ts', 'value_float', 'value_text', 'quality', 'raw_value']
