"""
Service layer for Switch-related business logic.
Handles switch operations, validation, and complex queries.
"""
from django.db import transaction
from django.db.models import Q, Count, Avg, Max, F
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

from snmp.models import (
    Switch, 
    Interface as SwitchPort, 
    NeighborLink as SwitchNeighbor, 
    InterfaceBandwidthSample as BandwidthSample
)
from snmp.api.exceptions import (
    SNMPConnectionError, InvalidDeviceConfiguration,
    DeviceNotReachable, PollingInProgress
)

logger = logging.getLogger(__name__)


class SwitchService:
    """Service for managing switches and their operations."""
    
    @staticmethod
    def create_switch(data, user=None):
        """
        Create a new switch with validation.
        
        Args:
            data: Dictionary with switch data
            user: User creating the switch
            
        Returns:
            Created Switch instance
        """
        with transaction.atomic():
            # Validate IP uniqueness
            if Switch.objects.filter(ip_address=data.get('ip_address')).exists():
                raise InvalidDeviceConfiguration(
                    f"Switch with IP {data.get('ip_address')} already exists"
                )
            
            switch = Switch.objects.create(**data)
            logger.info(f"Switch {switch.name} created by {user}")
            
            # Invalidate cache
            cache.delete_pattern('switch_*')
            
            return switch
    
    @staticmethod
    def update_switch(switch_id, data, user=None):
        """
        Update switch with validation.
        
        Args:
            switch_id: ID of switch to update
            data: Dictionary with updated data
            user: User updating the switch
            
        Returns:
            Updated Switch instance
        """
        with transaction.atomic():
            switch = Switch.objects.select_for_update().get(id=switch_id)
            
            # Update fields
            for key, value in data.items():
                if hasattr(switch, key):
                    setattr(switch, key, value)
            
            switch.save()
            logger.info(f"Switch {switch.name} updated by {user}")
            
            # Invalidate cache
            cache.delete(f'switch_detail_{switch_id}')
            cache.delete_pattern('switch_list_*')
            
            return switch
    
    @staticmethod
    def delete_switch(switch_id, user=None):
        """
        Delete switch and related data.
        
        Args:
            switch_id: ID of switch to delete
            user: User deleting the switch
        """
        with transaction.atomic():
            switch = Switch.objects.get(id=switch_id)
            switch_name = switch.name
            
            # Delete related data
            switch.switchport_set.all().delete()
            switch.switchneighbor_set.all().delete()
            BandwidthSample.objects.filter(switch=switch).delete()
            
            switch.delete()
            logger.info(f"Switch {switch_name} deleted by {user}")
            
            # Invalidate cache
            cache.delete(f'switch_detail_{switch_id}')
            cache.delete_pattern('switch_*')
    
    @staticmethod
    def bulk_update_switches(switch_ids, updates, user=None):
        """
        Bulk update multiple switches.
        
        Args:
            switch_ids: List of switch IDs
            updates: Dictionary of fields to update
            user: User performing the update
            
        Returns:
            Number of updated switches
        """
        with transaction.atomic():
            count = Switch.objects.filter(id__in=switch_ids).update(**updates)
            logger.info(f"Bulk updated {count} switches by {user}")
            
            # Invalidate cache
            cache.delete_pattern('switch_*')
            
            return count
    
    @staticmethod
    def get_switch_status(switch_id):
        """
        Get detailed status of a switch.
        
        Args:
            switch_id: ID of the switch
            
        Returns:
            Dictionary with status information
        """
        cache_key = f'switch_status_{switch_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        switch = Switch.objects.select_related(
            'ats', 'branch', 'host_group', 'device_model'
        ).prefetch_related('switchport_set').get(id=switch_id)
        
        ports = switch.switchport_set.all()
        
        status = {
            'id': switch.id,
            'name': switch.name,
            'ip_address': switch.ip_address,
            'status': switch.status,
            'last_seen': switch.last_seen,
            'uptime': switch.uptime,
            'cpu_usage': switch.cpu_usage,
            'memory_usage': switch.memory_usage,
            'temperature': switch.temperature,
            'fan_status': switch.fan_status,
            'power_supply_status': switch.power_supply_status,
            'ports': {
                'total': ports.count(),
                'up': ports.filter(status='up').count(),
                'down': ports.filter(status='down').count(),
                'testing': ports.filter(status='testing').count(),
            },
            'health': SwitchService._calculate_health(switch, ports),
        }
        
        cache.set(cache_key, status, 60)  # Cache for 1 minute
        return status
    
    @staticmethod
    def _calculate_health(switch, ports):
        """Calculate overall health score of a switch."""
        score = 100
        
        # Status check
        if switch.status == 'offline':
            score -= 50
        elif switch.status == 'error':
            score -= 30
        
        # CPU usage
        if switch.cpu_usage and switch.cpu_usage > 90:
            score -= 15
        elif switch.cpu_usage and switch.cpu_usage > 80:
            score -= 10
        
        # Memory usage
        if switch.memory_usage and switch.memory_usage > 90:
            score -= 15
        elif switch.memory_usage and switch.memory_usage > 80:
            score -= 10
        
        # Temperature
        if switch.temperature and switch.temperature > 80:
            score -= 15
        elif switch.temperature and switch.temperature > 70:
            score -= 10
        
        # Port errors
        total_ports = ports.count()
        if total_ports > 0:
            down_ports = ports.filter(status='down').count()
            error_ports = ports.filter(Q(in_errors__gt=100) | Q(out_errors__gt=100)).count()
            
            if down_ports > total_ports * 0.5:
                score -= 20
            elif down_ports > total_ports * 0.3:
                score -= 10
            
            if error_ports > 0:
                score -= 5
        
        return max(0, min(100, score))
    
    @staticmethod
    def get_switches_by_status(status=None):
        """
        Get switches filtered by status.
        
        Args:
            status: Status to filter by (online, offline, error, unknown)
            
        Returns:
            QuerySet of switches
        """
        queryset = Switch.objects.select_related(
            'ats', 'branch', 'host_group', 'device_model'
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    @staticmethod
    def get_switches_with_issues():
        """
        Get switches that have issues (high CPU, memory, temp, or offline).
        
        Returns:
            QuerySet of switches with issues
        """
        return Switch.objects.filter(
            Q(status__in=['offline', 'error']) |
            Q(cpu_usage__gte=80) |
            Q(memory_usage__gte=80) |
            Q(temperature__gte=70)
        ).select_related('ats', 'branch', 'host_group', 'device_model')
    
    @staticmethod
    def search_switches(query):
        """
        Search switches by multiple fields.
        
        Args:
            query: Search query string
            
        Returns:
            QuerySet of matching switches
        """
        return Switch.objects.filter(
            Q(name__icontains=query) |
            Q(ip_address__icontains=query) |
            Q(mac_address__icontains=query) |
            Q(serial_number__icontains=query) |
            Q(location__icontains=query) |
            Q(description__icontains=query)
        ).select_related('ats', 'branch', 'host_group', 'device_model')
    
    @staticmethod
    def get_switch_statistics(switch_id=None, group_by=None):
        """
        Get statistics for switches.
        
        Args:
            switch_id: Optional specific switch ID
            group_by: Optional field to group by (ats, branch, model, etc.)
            
        Returns:
            Dictionary with statistics
        """
        if switch_id:
            switch = Switch.objects.get(id=switch_id)
            ports = switch.switchport_set.all()
            
            return {
                'total_ports': ports.count(),
                'active_ports': ports.filter(status='up').count(),
                'uplink_ports': ports.filter(port_type='uplink').count(),
                'access_ports': ports.filter(port_type='access').count(),
                'trunk_ports': ports.filter(port_type='trunk').count(),
                'sfp_ports': ports.filter(port_type='sfp').count(),
                'avg_port_utilization': ports.aggregate(
                    Avg('in_octets'), Avg('out_octets')
                ),
            }
        
        queryset = Switch.objects.all()
        
        if group_by == 'ats':
            return list(queryset.values('ats__name').annotate(
                total=Count('id'),
                online=Count('id', filter=Q(status='online')),
                offline=Count('id', filter=Q(status='offline'))
            ))
        elif group_by == 'branch':
            return list(queryset.values('branch__name').annotate(
                total=Count('id'),
                online=Count('id', filter=Q(status='online')),
                offline=Count('id', filter=Q(status='offline'))
            ))
        elif group_by == 'model':
            return list(queryset.values('device_model__model').annotate(
                total=Count('id'),
                online=Count('id', filter=Q(status='online')),
                offline=Count('id', filter=Q(status='offline'))
            ))
        
        # Overall statistics
        return {
            'total': queryset.count(),
            'online': queryset.filter(status='online').count(),
            'offline': queryset.filter(status='offline').count(),
            'error': queryset.filter(status='error').count(),
            'unknown': queryset.filter(status='unknown').count(),
            'monitored': queryset.filter(is_monitored=True).count(),
            'avg_cpu': queryset.aggregate(Avg('cpu_usage'))['cpu_usage__avg'],
            'avg_memory': queryset.aggregate(Avg('memory_usage'))['memory_usage__avg'],
            'avg_temperature': queryset.aggregate(Avg('temperature'))['temperature__avg'],
        }
    
    @staticmethod
    def check_switch_reachability(ip_address, timeout=2):
        """
        Check if switch is reachable via ping.
        
        Args:
            ip_address: IP address to check
            timeout: Timeout in seconds
            
        Returns:
            Boolean indicating reachability
        """
        import subprocess
        import platform
        
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-W', str(timeout), ip_address]
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout + 1
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking reachability for {ip_address}: {e}")
            return False
    
    @staticmethod
    def validate_switch_credentials(switch):
        """
        Validate SNMP credentials for a switch.
        
        Args:
            switch: Switch instance
            
        Returns:
            Boolean indicating if credentials are valid
        """
        from snmp.services.snmp_client import SNMPClient
        
        try:
            client = SNMPClient(
                switch.ip_address,
                switch.snmp_community_ro,
                version=switch.snmp_version,
                port=switch.snmp_port
            )
            # Try to get sysDescr
            result = client.get('1.3.6.1.2.1.1.1.0')
            return result is not None
        except Exception as e:
            logger.error(f"Failed to validate credentials for {switch.name}: {e}")
            return False
