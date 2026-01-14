"""
Service for monitoring switches and ports.
Handles polling, status updates, and health checks.
"""
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import logging

from snmp.models import (
    Switch, 
    Interface as SwitchPort, 
    InterfaceBandwidthSample as BandwidthSample
)
from snmp.services.snmp_client import SnmpClient as SNMPClient
from snmp.api.exceptions import SNMPConnectionError, SNMPTimeoutError

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service for monitoring network devices."""
    
    @staticmethod
    def poll_switch(switch_id):
        """
        Poll a switch for current status and metrics.
        
        Args:
            switch_id: ID of switch to poll
            
        Returns:
            Dictionary with poll results
        """
        try:
            switch = Switch.objects.get(id=switch_id)
            
            # Create SNMP client
            client = SNMPClient(
                switch.ip_address,
                switch.snmp_community_ro,
                version=switch.snmp_version,
                port=switch.snmp_port,
                timeout=5
            )
            
            results = {}
            
            # Get system information
            results['sysDescr'] = client.get('1.3.6.1.2.1.1.1.0')
            results['sysUpTime'] = client.get('1.3.6.1.2.1.1.3.0')
            results['sysName'] = client.get('1.3.6.1.2.1.1.5.0')
            
            # Update switch status
            with transaction.atomic():
                switch.status = 'online'
                switch.last_seen = timezone.now()
                switch.last_polled = timezone.now()
                
                if results.get('sysUpTime'):
                    switch.uptime = int(results['sysUpTime']) / 100  # Convert to seconds
                
                if results.get('sysName'):
                    # Update name if different
                    if not switch.name or switch.name == switch.ip_address:
                        switch.name = results['sysName']
                
                switch.save()
            
            # Poll ports
            MonitoringService._poll_ports(switch, client)
            
            logger.info(f"Successfully polled switch {switch.name}")
            return results
            
        except Switch.DoesNotExist:
            logger.error(f"Switch {switch_id} not found")
            raise
        except Exception as e:
            logger.error(f"Failed to poll switch {switch_id}: {e}")
            # Update switch status to offline
            try:
                switch = Switch.objects.get(id=switch_id)
                switch.status = 'offline'
                switch.save()
            except:
                pass
            raise SNMPConnectionError(f"Failed to poll switch: {str(e)}")
    
    @staticmethod
    def _poll_ports(switch, client):
        """
        Poll all ports for a switch.
        
        Args:
            switch: Switch instance
            client: SNMPClient instance
        """
        try:
            # Get port count
            if_number = client.get('1.3.6.1.2.1.2.1.0')
            if not if_number:
                return
            
            if_number = int(if_number)
            
            # Get interface table data
            if_indices = client.walk('1.3.6.1.2.1.2.2.1.1')  # ifIndex
            if_descr = client.walk('1.3.6.1.2.1.2.2.1.2')    # ifDescr
            if_type = client.walk('1.3.6.1.2.1.2.2.1.3')     # ifType
            if_speed = client.walk('1.3.6.1.2.1.2.2.1.5')    # ifSpeed
            if_admin_status = client.walk('1.3.6.1.2.1.2.2.1.7')  # ifAdminStatus
            if_oper_status = client.walk('1.3.6.1.2.1.2.2.1.8')   # ifOperStatus
            
            # Process each interface
            for i, index in enumerate(if_indices):
                try:
                    port_index = int(index)
                    port_name = if_descr[i] if i < len(if_descr) else f"Port {port_index}"
                    
                    # Get or create port
                    port, created = SwitchPort.objects.get_or_create(
                        switch=switch,
                        port_index=port_index,
                        defaults={'port_name': port_name}
                    )
                    
                    # Update port data
                    port.port_name = port_name
                    
                    if i < len(if_speed):
                        port.speed = int(if_speed[i]) // 1000000  # Convert to Mbps
                    
                    if i < len(if_admin_status):
                        admin_status_map = {1: 'up', 2: 'down', 3: 'testing'}
                        port.admin_status = admin_status_map.get(int(if_admin_status[i]), 'unknown')
                    
                    if i < len(if_oper_status):
                        oper_status_map = {
                            1: 'up', 2: 'down', 3: 'testing',
                            4: 'unknown', 5: 'dormant', 6: 'notPresent', 7: 'lowerLayerDown'
                        }
                        port.status = oper_status_map.get(int(if_oper_status[i]), 'unknown')
                    
                    port.save()
                    
                except Exception as e:
                    logger.error(f"Error processing port {i} for switch {switch.name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to poll ports for switch {switch.name}: {e}")
    
    @staticmethod
    def poll_port_statistics(port_id):
        """
        Poll detailed statistics for a specific port.
        
        Args:
            port_id: ID of port to poll
            
        Returns:
            Dictionary with port statistics
        """
        try:
            port = SwitchPort.objects.select_related('switch').get(id=port_id)
            switch = port.switch
            
            client = SNMPClient(
                switch.ip_address,
                switch.snmp_community_ro,
                version=switch.snmp_version,
                port=switch.snmp_port
            )
            
            # Get interface statistics
            base_oid = f'1.3.6.1.2.1.2.2.1'
            
            stats = {
                'in_octets': client.get(f'{base_oid}.10.{port.port_index}'),
                'out_octets': client.get(f'{base_oid}.16.{port.port_index}'),
                'in_errors': client.get(f'{base_oid}.14.{port.port_index}'),
                'out_errors': client.get(f'{base_oid}.20.{port.port_index}'),
                'in_discards': client.get(f'{base_oid}.13.{port.port_index}'),
                'out_discards': client.get(f'{base_oid}.19.{port.port_index}'),
            }
            
            # Update port with statistics
            with transaction.atomic():
                if stats['in_octets']:
                    port.in_octets = int(stats['in_octets'])
                if stats['out_octets']:
                    port.out_octets = int(stats['out_octets'])
                if stats['in_errors']:
                    port.in_errors = int(stats['in_errors'])
                if stats['out_errors']:
                    port.out_errors = int(stats['out_errors'])
                if stats['in_discards']:
                    port.in_discards = int(stats['in_discards'])
                if stats['out_discards']:
                    port.out_discards = int(stats['out_discards'])
                
                port.save()
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to poll port statistics for port {port_id}: {e}")
            raise
    
    @staticmethod
    def check_all_switches_status():
        """
        Check status of all monitored switches.
        
        Returns:
            Dictionary with results
        """
        switches = Switch.objects.filter(is_monitored=True, is_active=True)
        
        results = {
            'total': 0,
            'checked': 0,
            'online': 0,
            'offline': 0,
            'errors': []
        }
        
        for switch in switches:
            results['total'] += 1
            try:
                MonitoringService.poll_switch(switch.id)
                results['checked'] += 1
                if switch.status == 'online':
                    results['online'] += 1
                else:
                    results['offline'] += 1
            except Exception as e:
                results['errors'].append({
                    'switch_id': switch.id,
                    'switch_name': switch.name,
                    'error': str(e)
                })
                results['offline'] += 1
        
        return results
    
    @staticmethod
    def get_switch_health_report(switch_id):
        """
        Generate detailed health report for a switch.
        
        Args:
            switch_id: ID of switch
            
        Returns:
            Dictionary with health report
        """
        switch = Switch.objects.prefetch_related('switchport_set').get(id=switch_id)
        ports = switch.switchport_set.all()
        
        report = {
            'switch_id': switch.id,
            'switch_name': switch.name,
            'status': switch.status,
            'last_seen': switch.last_seen,
            'uptime_hours': switch.uptime / 3600 if switch.uptime else 0,
            'issues': [],
            'warnings': [],
            'metrics': {
                'cpu_usage': switch.cpu_usage,
                'memory_usage': switch.memory_usage,
                'temperature': switch.temperature,
            },
            'ports': {
                'total': ports.count(),
                'up': ports.filter(status='up').count(),
                'down': ports.filter(status='down').count(),
                'with_errors': ports.filter(
                    in_errors__gt=0
                ).count() + ports.filter(out_errors__gt=0).count(),
            }
        }
        
        # Check for issues
        if switch.status == 'offline':
            report['issues'].append('Switch is offline')
        
        if switch.cpu_usage and switch.cpu_usage > 90:
            report['issues'].append(f'Critical CPU usage: {switch.cpu_usage}%')
        elif switch.cpu_usage and switch.cpu_usage > 80:
            report['warnings'].append(f'High CPU usage: {switch.cpu_usage}%')
        
        if switch.memory_usage and switch.memory_usage > 90:
            report['issues'].append(f'Critical memory usage: {switch.memory_usage}%')
        elif switch.memory_usage and switch.memory_usage > 80:
            report['warnings'].append(f'High memory usage: {switch.memory_usage}%')
        
        if switch.temperature and switch.temperature > 80:
            report['issues'].append(f'Critical temperature: {switch.temperature}°C')
        elif switch.temperature and switch.temperature > 70:
            report['warnings'].append(f'High temperature: {switch.temperature}°C')
        
        # Check port errors
        error_ports = ports.filter(in_errors__gt=100).count() + ports.filter(out_errors__gt=100).count()
        if error_ports > 0:
            report['warnings'].append(f'{error_ports} ports with significant errors')
        
        # Last seen check
        if switch.last_seen:
            hours_since_seen = (timezone.now() - switch.last_seen).total_seconds() / 3600
            if hours_since_seen > 24:
                report['issues'].append(f'Not seen for {int(hours_since_seen)} hours')
            elif hours_since_seen > 1:
                report['warnings'].append(f'Last seen {int(hours_since_seen)} hours ago')
        
        report['health_score'] = MonitoringService._calculate_health_score(report)
        
        return report
    
    @staticmethod
    def _calculate_health_score(report):
        """Calculate health score from report."""
        score = 100
        
        # Deduct for issues
        score -= len(report['issues']) * 15
        score -= len(report['warnings']) * 5
        
        # Deduct for status
        if report['status'] == 'offline':
            score -= 30
        
        # Deduct for port problems
        if report['ports']['total'] > 0:
            down_ratio = report['ports']['down'] / report['ports']['total']
            score -= int(down_ratio * 20)
        
        return max(0, min(100, score))
    
    @staticmethod
    def get_switches_requiring_attention():
        """
        Get list of switches that require attention.
        
        Returns:
            QuerySet of switches with issues
        """
        from django.db.models import Q
        
        # Switches that are offline or haven't been seen recently
        threshold_time = timezone.now() - timedelta(hours=2)
        
        return Switch.objects.filter(
            Q(status='offline') |
            Q(status='error') |
            Q(last_seen__lt=threshold_time) |
            Q(cpu_usage__gte=80) |
            Q(memory_usage__gte=80) |
            Q(temperature__gte=70)
        ).select_related('ats', 'branch', 'host_group')
