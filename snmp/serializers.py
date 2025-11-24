"""
Django REST Framework serializers for SNMP monitoring system.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Switch, Branch, SwitchModel, Vendor, Ats, SwitchesPorts


class VendorSerializer(serializers.ModelSerializer):
    """Serializer for Vendor model."""
    
    class Meta:
        model = Vendor
        fields = ['id', 'name']


class SwitchModelSerializer(serializers.ModelSerializer):
    """Serializer for SwitchModel model."""
    
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = SwitchModel
        fields = [
            'id', 'vendor', 'vendor_id', 'device_model',
            'rx_oid', 'tx_oid', 'part_num_oid', 'sfp_vendor',
            'port_num_oid', 'max_ports_oid', 'description_oid',
            'speed_oid', 'duplex_oid', 'admin_state_oid', 'oper_state_oid'
        ]
        read_only_fields = ['id']


class BranchSerializer(serializers.ModelSerializer):
    """Serializer for Branch model."""
    
    switch_count = serializers.SerializerMethodField()
    online_switches = serializers.SerializerMethodField()
    offline_switches = serializers.SerializerMethodField()
    
    class Meta:
        model = Branch
        fields = ['id', 'name', 'switch_count', 'online_switches', 'offline_switches']
        read_only_fields = ['id', 'switch_count', 'online_switches', 'offline_switches']
    
    def get_switch_count(self, obj):
        """Get total number of switches in branch."""
        return obj.switch_set.count()
    
    def get_online_switches(self, obj):
        """Get number of online switches in branch."""
        return obj.switch_set.filter(status=True).count()
    
    def get_offline_switches(self, obj):
        """Get number of offline switches in branch."""
        return obj.switch_set.filter(status=False).count()


class AtsSerializer(serializers.ModelSerializer):
    """Serializer for ATS model."""
    
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Ats
        fields = ['id', 'name', 'subnet', 'branch', 'branch_id']
        read_only_fields = ['id']


class SwitchesPortsSerializer(serializers.ModelSerializer):
    """Serializer for SwitchesPorts model."""
    
    class Meta:
        model = SwitchesPorts
        fields = [
            'id', 'port', 'description', 'speed', 'duplex',
            'admin', 'oper', 'lastchange', 'discards_in',
            'discards_out', 'mac_count', 'pvid', 'port_tagged',
            'port_untagged', 'data', 'name', 'alias',
            'oct_in', 'oct_out', 'rx_signal', 'tx_signal',
            'sfp_vendor', 'part_number'
        ]
        read_only_fields = ['id', 'data']


class SwitchSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for Switch model with nested relationships.
    """
    
    # Nested relationships (read-only)
    model = SwitchModelSerializer(read_only=True)
    branch = BranchSerializer(read_only=True)
    ats = AtsSerializer(read_only=True)
    
    # Write-only fields for relationships
    model_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    branch_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    ats_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    # Computed fields
    status_display = serializers.SerializerMethodField()
    signal_status = serializers.SerializerMethodField()
    last_update_ago = serializers.SerializerMethodField()
    health_status = serializers.SerializerMethodField()
    
    # Port information
    ports = SwitchesPortsSerializer(source='switch_ports_reverse', many=True, read_only=True)
    port_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Switch
        fields = [
            # Basic fields
            'id', 'created', 'hostname', 'ip', 'switch_mac',
            'snmp_community_ro', 'snmp_community_rw', 'status',
            'uptime', 'last_update', 'soft_version', 'serial_number',
            
            # Signal fields
            'rx_signal', 'tx_signal', 'sfp_vendor', 'part_number',
            
            # Relationships
            'model', 'branch', 'ats',
            'model_id', 'branch_id', 'ats_id',
            
            # Computed fields
            'status_display', 'signal_status', 'last_update_ago',
            'health_status', 'ports', 'port_count'
        ]
        read_only_fields = [
            'id', 'created', 'last_update', 'switch_mac', 'serial_number',
            'uptime', 'rx_signal', 'tx_signal', 'sfp_vendor', 'part_number',
            'status_display', 'signal_status', 'last_update_ago',
            'health_status', 'ports', 'port_count'
        ]
        extra_kwargs = {
            'snmp_community_ro': {'write_only': True},
            'snmp_community_rw': {'write_only': True},
        }
    
    def get_status_display(self, obj):
        """Get human-readable status."""
        return 'Online' if obj.status else 'Offline'
    
    def get_signal_status(self, obj):
        """Get signal quality status."""
        rx_signal = obj.rx_signal
        tx_signal = obj.tx_signal
        
        if rx_signal is None and tx_signal is None:
            return 'unknown'
        
        # Define thresholds
        high_threshold = -15
        low_threshold = -25
        
        rx_status = 'unknown'
        tx_status = 'unknown'
        
        if rx_signal is not None:
            if rx_signal > high_threshold:
                rx_status = 'high'
            elif rx_signal < low_threshold:
                rx_status = 'low'
            else:
                rx_status = 'normal'
        
        if tx_signal is not None:
            if tx_signal > high_threshold:
                tx_status = 'high'
            elif tx_signal < low_threshold:
                tx_status = 'low'
            else:
                tx_status = 'normal'
        
        # Overall status
        if rx_status == 'high' or tx_status == 'high':
            return 'high'
        elif rx_status == 'low' or tx_status == 'low':
            return 'low'
        elif rx_status == 'normal' or tx_status == 'normal':
            return 'normal'
        else:
            return 'unknown'
    
    def get_last_update_ago(self, obj):
        """Get time since last update in human-readable format."""
        if not obj.last_update:
            return None
        
        from django.utils import timezone
        now = timezone.now()
        delta = now - obj.last_update
        
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())}s ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() // 60)}m ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() // 3600)}h ago"
        else:
            return f"{int(delta.total_seconds() // 86400)}d ago"
    
    def get_health_status(self, obj):
        """Get overall health status based on multiple factors."""
        from django.core.cache import cache
        
        # Try to get cached health report
        cached_report = cache.get(f'health_report_{obj.id}')
        if cached_report:
            return cached_report.get('overall_status', 'unknown')
        
        # Simple health assessment based on available data
        if not obj.status:
            return 'unhealthy'
        
        # Check if data is stale
        if obj.last_update:
            from django.utils import timezone
            age_hours = (timezone.now() - obj.last_update).total_seconds() / 3600
            if age_hours > 2:
                return 'warning'
        
        # Check signal levels
        signal_status = self.get_signal_status(obj)
        if signal_status in ['high', 'low']:
            return 'warning'
        
        return 'healthy'
    
    def get_port_count(self, obj):
        """Get number of ports for this switch."""
        return obj.switch_ports_reverse.count()
    
    def validate_ip(self, value):
        """Validate IP address format."""
        if value:
            import ipaddress
            try:
                ipaddress.ip_address(value)
            except ValueError:
                raise serializers.ValidationError("Invalid IP address format")
        return value
    
    def validate_hostname(self, value):
        """Validate hostname."""
        if value and len(value) > 200:
            raise serializers.ValidationError("Hostname too long (max 200 characters)")
        return value
    
    def validate(self, data):
        """Cross-field validation."""
        # Ensure either IP or hostname is provided
        ip = data.get('ip')
        hostname = data.get('hostname')
        
        if not ip and not hostname:
            raise serializers.ValidationError("Either IP address or hostname must be provided")
        
        # Check for duplicates when creating
        if not self.instance:  # Creating new instance
            from django.db.models import Q
            
            existing = Switch.objects.filter(
                Q(ip=ip) | Q(hostname=hostname)
            ).first()
            
            if existing:
                raise serializers.ValidationError(
                    f"Switch with IP {ip} or hostname {hostname} already exists"
                )
        
        return data


class SwitchCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating switches.
    """
    
    class Meta:
        model = Switch
        fields = ['hostname', 'ip', 'model_id', 'branch_id', 'ats_id',
                 'snmp_community_ro', 'snmp_community_rw']
        extra_kwargs = {
            'hostname': {'required': True},
            'ip': {'required': True},
        }
    
    def validate_ip(self, value):
        """Validate IP address."""
        if value:
            import ipaddress
            try:
                ipaddress.ip_address(value)
            except ValueError:
                raise serializers.ValidationError("Invalid IP address format")
        return value


class SwitchUpdateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for updating switches.
    """
    
    class Meta:
        model = Switch
        fields = ['hostname', 'ip', 'model_id', 'branch_id', 'ats_id',
                 'snmp_community_ro', 'snmp_community_rw']
        extra_kwargs = {
            'hostname': {'required': False},
            'ip': {'required': False},
        }


class SwitchStatsSerializer(serializers.Serializer):
    """
    Serializer for switch statistics.
    """
    total_switches = serializers.IntegerField()
    online_switches = serializers.IntegerField()
    offline_switches = serializers.IntegerField()
    offline_percentage = serializers.FloatField()
    high_signal_switches = serializers.IntegerField()
    recent_updates = serializers.IntegerField()
    by_vendor = serializers.DictField()
    by_branch = serializers.DictField()


class HealthReportSerializer(serializers.Serializer):
    """
    Serializer for health check reports.
    """
    switch_id = serializers.IntegerField()
    hostname = serializers.CharField()
    ip = serializers.IPAddressField()
    timestamp = serializers.DateTimeField()
    overall_status = serializers.ChoiceField(
        choices=['healthy', 'warning', 'unhealthy', 'error', 'unknown']
    )
    execution_time = serializers.FloatField()
    
    # Nested check results
    checks = serializers.DictField()
    alerts = serializers.ListField(child=serializers.DictField())


class SystemOverviewSerializer(serializers.Serializer):
    """
    Serializer for system monitoring overview.
    """
    timestamp = serializers.DateTimeField()
    switches = serializers.DictField()
    branches = serializers.DictField()
    recent_alerts = serializers.ListField()
    performance = serializers.DictField()