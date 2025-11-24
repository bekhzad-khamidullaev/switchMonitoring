"""
Service for monitoring uplink ports and optical signal levels.
Production-ready implementation for continuous uplink monitoring.
"""
import time
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from .base_service import BaseService
from .snmp_service import SNMPService
from .device_discovery_service import DeviceDiscoveryService
from ..models import Switch, SwitchesPorts


@dataclass
class UplinkStatus:
    """Uplink interface status information."""
    switch_id: int
    switch_hostname: str
    switch_ip: str
    port_index: int
    port_name: str
    port_description: str
    interface_speed: int
    admin_status: str
    operational_status: str
    rx_power: Optional[float]
    tx_power: Optional[float]
    rx_power_threshold_critical: float = -25.0
    rx_power_threshold_warning: float = -20.0
    tx_power_threshold_critical: float = -25.0
    tx_power_threshold_warning: float = -20.0
    last_update: datetime = None
    status_severity: str = "normal"  # normal, warning, critical
    alerts: List[str] = None
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []
        if self.last_update is None:
            self.last_update = timezone.now()


@dataclass
class UplinkMonitoringReport:
    """Comprehensive uplink monitoring report."""
    timestamp: datetime
    total_uplinks_monitored: int
    healthy_uplinks: int
    warning_uplinks: int
    critical_uplinks: int
    offline_uplinks: int
    switches_with_issues: int
    uplink_statuses: List[UplinkStatus]
    execution_time: float
    alerts_generated: int
    notifications_sent: int


class UplinkMonitoringService(BaseService):
    """
    Production service for monitoring uplink ports and optical signals.
    """
    
    def __init__(self):
        super().__init__()
        self.snmp_service = SNMPService()
        self.discovery_service = DeviceDiscoveryService()
        
        # Optical signal thresholds (dBm)
        self.thresholds = {
            'rx_power': {
                'critical_low': -25.0,
                'warning_low': -20.0,
                'warning_high': -8.0,
                'critical_high': -3.0,
            },
            'tx_power': {
                'critical_low': -25.0,
                'warning_low': -20.0,
                'warning_high': -8.0,
                'critical_high': -3.0,
            }
        }
        
        # Interface status mappings
        self.interface_status = {
            1: 'up',
            2: 'down',
            3: 'testing',
            4: 'unknown',
            5: 'dormant',
            6: 'notPresent',
            7: 'lowerLayerDown'
        }
        
        # Speed thresholds for uplink detection (Mbps)
        self.uplink_speed_threshold = 1000  # 1 Gbps
        
    def monitor_all_uplinks(self, parallel: bool = True, max_workers: int = 10) -> UplinkMonitoringReport:
        """
        Monitor all uplinks across all switches.
        
        Args:
            parallel: Whether to run monitoring in parallel
            max_workers: Maximum number of parallel workers
            
        Returns:
            Comprehensive monitoring report
        """
        start_time = time.time()
        self.log_info("Starting comprehensive uplink monitoring")
        
        try:
            # Get all active switches with models
            switches = Switch.objects.filter(
                status=True,
                model__isnull=False
            ).select_related('model', 'model__vendor')
            
            if not switches.exists():
                self.log_warning("No active switches with models found for monitoring")
                return self._create_empty_report(start_time)
            
            self.log_info(f"Found {switches.count()} switches to monitor")
            
            # Monitor uplinks
            if parallel and switches.count() > 1:
                uplink_statuses = self._monitor_uplinks_parallel(switches, max_workers)
            else:
                uplink_statuses = self._monitor_uplinks_sequential(switches)
            
            # Generate comprehensive report
            report = self._generate_monitoring_report(uplink_statuses, start_time)
            
            # Send notifications if needed
            if report.critical_uplinks > 0 or report.warning_uplinks > 0:
                notifications_sent = self._send_notifications(report)
                report.notifications_sent = notifications_sent
            
            # Cache the report
            cache.set('uplink_monitoring_report', asdict(report), 3600)
            
            self.log_info(f"Uplink monitoring completed: {report.total_uplinks_monitored} uplinks, "
                         f"{report.critical_uplinks} critical, {report.warning_uplinks} warnings")
            
            return report
            
        except Exception as e:
            self.log_error(f"Error during uplink monitoring: {e}")
            return self._create_empty_report(start_time, error=str(e))
    
    def monitor_switch_uplinks(self, switch: Switch) -> List[UplinkStatus]:
        """
        Monitor uplinks for a specific switch.
        
        Args:
            switch: Switch object to monitor
            
        Returns:
            List of uplink statuses
        """
        try:
            self.log_info(f"Monitoring uplinks for switch {switch.hostname}")
            
            # Get uplink interfaces for this switch
            uplinks = self._discover_uplink_interfaces(switch)
            if not uplinks:
                self.log_warning(f"No uplinks discovered for switch {switch.hostname}")
                return []
            
            uplink_statuses = []
            
            for uplink_info in uplinks:
                try:
                    status = self._monitor_uplink_interface(switch, uplink_info)
                    if status:
                        uplink_statuses.append(status)
                except Exception as e:
                    self.log_error(f"Error monitoring uplink {uplink_info.get('index')} "
                                 f"on switch {switch.hostname}: {e}")
                    continue
            
            # Update database with uplink information
            self._update_uplinks_in_database(switch, uplink_statuses)
            
            self.log_info(f"Monitored {len(uplink_statuses)} uplinks for switch {switch.hostname}")
            return uplink_statuses
            
        except Exception as e:
            self.log_error(f"Error monitoring uplinks for switch {switch.hostname}: {e}")
            return []
    
    def _monitor_uplinks_parallel(self, switches, max_workers: int) -> List[UplinkStatus]:
        """Monitor uplinks in parallel using thread pool."""
        all_uplink_statuses = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit monitoring tasks
            future_to_switch = {
                executor.submit(self.monitor_switch_uplinks, switch): switch
                for switch in switches
            }
            
            # Collect results
            for future in future_to_switch:
                switch = future_to_switch[future]
                try:
                    uplink_statuses = future.result(timeout=30)  # 30 second timeout per switch
                    all_uplink_statuses.extend(uplink_statuses)
                except Exception as e:
                    self.log_error(f"Error monitoring switch {switch.hostname}: {e}")
        
        return all_uplink_statuses
    
    def _monitor_uplinks_sequential(self, switches) -> List[UplinkStatus]:
        """Monitor uplinks sequentially."""
        all_uplink_statuses = []
        
        for switch in switches:
            try:
                uplink_statuses = self.monitor_switch_uplinks(switch)
                all_uplink_statuses.extend(uplink_statuses)
            except Exception as e:
                self.log_error(f"Error monitoring switch {switch.hostname}: {e}")
        
        return all_uplink_statuses
    
    def _discover_uplink_interfaces(self, switch: Switch) -> List[Dict[str, Any]]:
        """Discover uplink interfaces for a switch."""
        try:
            # Check cache first
            cache_key = f"uplinks_{switch.id}"
            cached_uplinks = cache.get(cache_key)
            if cached_uplinks:
                return cached_uplinks
            
            # Discover all interfaces
            interfaces = self.discovery_service._discover_interfaces(
                switch.ip, 
                switch.snmp_community_ro
            )
            
            if not interfaces:
                return []
            
            # Identify uplinks
            vendor = switch.model.vendor.name.lower() if switch.model and switch.model.vendor else 'generic'
            uplinks_info = self.discovery_service._identify_uplinks(interfaces, vendor)
            
            # Convert to dict format
            uplinks = []
            for uplink in uplinks_info:
                uplink_dict = {
                    'index': uplink.port_index,
                    'name': uplink.interface_name,
                    'description': uplink.interface_description,
                    'speed': uplink.speed,
                    'type': uplink.interface_type,
                    'admin_status': uplink.admin_status,
                    'oper_status': uplink.operational_status,
                }
                uplinks.append(uplink_dict)
            
            # Cache for 30 minutes
            cache.set(cache_key, uplinks, 1800)
            
            return uplinks
            
        except Exception as e:
            self.log_error(f"Error discovering uplinks for switch {switch.hostname}: {e}")
            return []
    
    def _monitor_uplink_interface(self, switch: Switch, uplink_info: Dict[str, Any]) -> Optional[UplinkStatus]:
        """Monitor a specific uplink interface."""
        try:
            port_index = uplink_info['index']
            
            # Get current interface status
            interface_status = self._get_interface_status(switch, port_index)
            if not interface_status:
                return None
            
            # Get optical signal levels if available
            optical_levels = self._get_optical_signal_levels(switch, port_index)
            
            # Create uplink status
            uplink_status = UplinkStatus(
                switch_id=switch.id,
                switch_hostname=switch.hostname,
                switch_ip=switch.ip,
                port_index=port_index,
                port_name=uplink_info.get('name', ''),
                port_description=uplink_info.get('description', ''),
                interface_speed=uplink_info.get('speed', 0),
                admin_status=interface_status.get('admin_status', 'unknown'),
                operational_status=interface_status.get('oper_status', 'unknown'),
                rx_power=optical_levels.get('rx_power'),
                tx_power=optical_levels.get('tx_power'),
                last_update=timezone.now()
            )
            
            # Analyze status and generate alerts
            self._analyze_uplink_status(uplink_status)
            
            return uplink_status
            
        except Exception as e:
            self.log_error(f"Error monitoring uplink interface {uplink_info.get('index')} "
                         f"on switch {switch.hostname}: {e}")
            return None
    
    def _get_interface_status(self, switch: Switch, port_index: int) -> Optional[Dict[str, Any]]:
        """Get current interface operational status."""
        try:
            base_oids = {
                'admin_status': '1.3.6.1.2.1.2.2.1.7',
                'oper_status': '1.3.6.1.2.1.2.2.1.8',
                'speed': '1.3.6.1.2.1.2.2.1.5',
                'high_speed': '1.3.6.1.2.1.31.1.1.1.15',
                'last_change': '1.3.6.1.2.1.2.2.1.9',
            }
            
            status_info = {}
            
            for status_type, base_oid in base_oids.items():
                oid = f"{base_oid}.{port_index}"
                value = self.snmp_service.snmp_get(
                    switch.ip, 
                    switch.snmp_community_ro, 
                    oid
                )
                
                if value is not None:
                    try:
                        if status_type in ['admin_status', 'oper_status']:
                            status_info[status_type] = self.interface_status.get(int(value), 'unknown')
                        else:
                            status_info[status_type] = int(value)
                    except (ValueError, TypeError):
                        status_info[status_type] = value
            
            return status_info if status_info else None
            
        except Exception as e:
            self.log_error(f"Error getting interface status for port {port_index} "
                         f"on switch {switch.hostname}: {e}")
            return None
    
    def _get_optical_signal_levels(self, switch: Switch, port_index: int) -> Dict[str, Optional[float]]:
        """Get optical signal levels for an interface."""
        optical_levels = {'rx_power': None, 'tx_power': None}
        
        try:
            if not switch.model:
                return optical_levels
            
            # Get vendor-specific optical OIDs
            vendor = switch.model.vendor.name.lower() if switch.model.vendor else None
            if not vendor:
                return optical_levels
            
            # Try model-specific OIDs first
            rx_oid = switch.model.rx_oid
            tx_oid = switch.model.tx_oid
            
            # Fallback to vendor defaults if model OIDs not available
            if not rx_oid or not tx_oid:
                vendor_oids = self.discovery_service._get_optical_oids(vendor)
                rx_oid = rx_oid or vendor_oids.get('rx_power')
                tx_oid = tx_oid or vendor_oids.get('tx_power')
            
            # Get RX power
            if rx_oid:
                rx_oid_full = f"{rx_oid}.{port_index}"
                rx_raw = self.snmp_service.snmp_get(
                    switch.ip,
                    switch.snmp_community_ro,
                    rx_oid_full
                )
                if rx_raw is not None:
                    optical_levels['rx_power'] = self._convert_optical_power(rx_raw, vendor)
            
            # Get TX power
            if tx_oid:
                tx_oid_full = f"{tx_oid}.{port_index}"
                tx_raw = self.snmp_service.snmp_get(
                    switch.ip,
                    switch.snmp_community_ro,
                    tx_oid_full
                )
                if tx_raw is not None:
                    optical_levels['tx_power'] = self._convert_optical_power(tx_raw, vendor)
            
            return optical_levels
            
        except Exception as e:
            self.log_error(f"Error getting optical signal levels for port {port_index} "
                         f"on switch {switch.hostname}: {e}")
            return optical_levels
    
    def _convert_optical_power(self, raw_value: str, vendor: str) -> Optional[float]:
        """Convert vendor-specific optical power value to dBm."""
        try:
            value = float(raw_value)
            
            # Vendor-specific conversions
            if vendor == 'cisco':
                # Cisco usually returns in tenths of dBm
                return round(value / 10.0, 2)
            elif vendor == 'huawei':
                # Huawei might return in hundredths of dBm
                if abs(value) > 1000:
                    return round(value / 100.0, 2)
                else:
                    return round(value, 2)
            elif vendor == 'h3c':
                # H3C similar to Huawei
                if abs(value) > 1000:
                    return round(value / 100.0, 2)
                else:
                    return round(value, 2)
            else:
                # Generic conversion
                if abs(value) > 1000:
                    return round(value / 100.0, 2)
                else:
                    return round(value, 2)
                    
        except (ValueError, TypeError):
            self.log_warning(f"Could not convert optical power value: {raw_value}")
            return None
    
    def _analyze_uplink_status(self, uplink_status: UplinkStatus):
        """Analyze uplink status and generate appropriate alerts."""
        alerts = []
        severity = "normal"
        
        # Check interface operational status
        if uplink_status.operational_status == 'down':
            alerts.append(f"Interface {uplink_status.port_name} is operationally down")
            severity = "critical"
        elif uplink_status.operational_status in ['testing', 'unknown', 'dormant']:
            alerts.append(f"Interface {uplink_status.port_name} has unstable status: {uplink_status.operational_status}")
            if severity == "normal":
                severity = "warning"
        
        # Check admin status
        if uplink_status.admin_status == 'down':
            alerts.append(f"Interface {uplink_status.port_name} is administratively down")
            if severity == "normal":
                severity = "warning"
        
        # Check RX power levels
        if uplink_status.rx_power is not None:
            rx_power = uplink_status.rx_power
            
            if rx_power <= self.thresholds['rx_power']['critical_low']:
                alerts.append(f"Critical low RX power: {rx_power} dBm")
                severity = "critical"
            elif rx_power >= self.thresholds['rx_power']['critical_high']:
                alerts.append(f"Critical high RX power: {rx_power} dBm")
                severity = "critical"
            elif rx_power <= self.thresholds['rx_power']['warning_low']:
                alerts.append(f"Low RX power warning: {rx_power} dBm")
                if severity == "normal":
                    severity = "warning"
            elif rx_power >= self.thresholds['rx_power']['warning_high']:
                alerts.append(f"High RX power warning: {rx_power} dBm")
                if severity == "normal":
                    severity = "warning"
        
        # Check TX power levels
        if uplink_status.tx_power is not None:
            tx_power = uplink_status.tx_power
            
            if tx_power <= self.thresholds['tx_power']['critical_low']:
                alerts.append(f"Critical low TX power: {tx_power} dBm")
                severity = "critical"
            elif tx_power >= self.thresholds['tx_power']['critical_high']:
                alerts.append(f"Critical high TX power: {tx_power} dBm")
                severity = "critical"
            elif tx_power <= self.thresholds['tx_power']['warning_low']:
                alerts.append(f"Low TX power warning: {tx_power} dBm")
                if severity == "normal":
                    severity = "warning"
            elif tx_power >= self.thresholds['tx_power']['warning_high']:
                alerts.append(f"High TX power warning: {tx_power} dBm")
                if severity == "normal":
                    severity = "warning"
        
        # Update uplink status
        uplink_status.alerts = alerts
        uplink_status.status_severity = severity
    
    def _update_uplinks_in_database(self, switch: Switch, uplink_statuses: List[UplinkStatus]):
        """Update uplink information in the database."""
        try:
            with transaction.atomic():
                for uplink_status in uplink_statuses:
                    # Update or create SwitchesPorts record
                    ports_data = {
                        'switch': switch,
                        'port': uplink_status.port_index,
                        'description': uplink_status.port_description,
                        'name': uplink_status.port_name,
                        'speed': uplink_status.interface_speed or 0,
                        'admin': 1 if uplink_status.admin_status == 'up' else 2,
                        'oper': 1 if uplink_status.operational_status == 'up' else 2,
                        'rx_signal': uplink_status.rx_power,
                        'tx_signal': uplink_status.tx_power,
                        'data': uplink_status.last_update,
                    }
                    
                    # Update defaults for required fields
                    ports_defaults = {
                        'duplex': 1,
                        'lastchange': 0,
                        'discards_in': 0,
                        'discards_out': 0,
                        'mac_count': 0,
                        'pvid': 1,
                        'port_tagged': '',
                        'port_untagged': '1',
                        'alias': uplink_status.port_description,
                        'oct_in': 0,
                        'oct_out': 0,
                        'sfp_vendor': '',
                        'part_number': '',
                        'mac_on_port_id': 1,  # Default value
                    }
                    ports_data.update(ports_defaults)
                    
                    SwitchesPorts.objects.update_or_create(
                        switch=switch,
                        port=uplink_status.port_index,
                        defaults=ports_data
                    )
                
                # Update switch optical levels (for main uplink)
                if uplink_statuses:
                    main_uplink = uplink_statuses[0]  # Use first uplink as main
                    if main_uplink.rx_power is not None:
                        switch.rx_signal = main_uplink.rx_power
                    if main_uplink.tx_power is not None:
                        switch.tx_signal = main_uplink.tx_power
                    switch.last_update = timezone.now()
                    switch.save()
            
            self.log_info(f"Updated {len(uplink_statuses)} uplinks in database for switch {switch.hostname}")
            
        except Exception as e:
            self.log_error(f"Error updating uplinks in database for switch {switch.hostname}: {e}")
    
    def _generate_monitoring_report(self, uplink_statuses: List[UplinkStatus], start_time: float) -> UplinkMonitoringReport:
        """Generate comprehensive monitoring report."""
        execution_time = time.time() - start_time
        
        # Count statuses
        healthy_count = sum(1 for status in uplink_statuses if status.status_severity == "normal")
        warning_count = sum(1 for status in uplink_statuses if status.status_severity == "warning")
        critical_count = sum(1 for status in uplink_statuses if status.status_severity == "critical")
        offline_count = sum(1 for status in uplink_statuses if status.operational_status == "down")
        
        # Count switches with issues
        switches_with_issues = len(set(
            status.switch_id for status in uplink_statuses 
            if status.status_severity in ["warning", "critical"] or status.operational_status == "down"
        ))
        
        # Count alerts
        total_alerts = sum(len(status.alerts) for status in uplink_statuses)
        
        report = UplinkMonitoringReport(
            timestamp=timezone.now(),
            total_uplinks_monitored=len(uplink_statuses),
            healthy_uplinks=healthy_count,
            warning_uplinks=warning_count,
            critical_uplinks=critical_count,
            offline_uplinks=offline_count,
            switches_with_issues=switches_with_issues,
            uplink_statuses=uplink_statuses,
            execution_time=round(execution_time, 2),
            alerts_generated=total_alerts,
            notifications_sent=0  # Will be updated if notifications are sent
        )
        
        return report
    
    def _create_empty_report(self, start_time: float, error: str = None) -> UplinkMonitoringReport:
        """Create empty report for error cases."""
        execution_time = time.time() - start_time
        
        return UplinkMonitoringReport(
            timestamp=timezone.now(),
            total_uplinks_monitored=0,
            healthy_uplinks=0,
            warning_uplinks=0,
            critical_uplinks=0,
            offline_uplinks=0,
            switches_with_issues=0,
            uplink_statuses=[],
            execution_time=round(execution_time, 2),
            alerts_generated=0,
            notifications_sent=0
        )
    
    def _send_notifications(self, report: UplinkMonitoringReport) -> int:
        """Send notifications for critical/warning issues."""
        try:
            if not hasattr(settings, 'ALERT_EMAIL_RECIPIENTS'):
                return 0
            
            # Prepare notification content
            critical_uplinks = [status for status in report.uplink_statuses if status.status_severity == "critical"]
            warning_uplinks = [status for status in report.uplink_statuses if status.status_severity == "warning"]
            
            if not critical_uplinks and not warning_uplinks:
                return 0
            
            # Compose email
            subject = f"[SNMP Monitor] Uplink Alert - {len(critical_uplinks)} Critical, {len(warning_uplinks)} Warnings"
            
            message_lines = [
                f"Uplink Monitoring Alert Report",
                f"Timestamp: {report.timestamp}",
                f"",
                f"Summary:",
                f"- Total uplinks monitored: {report.total_uplinks_monitored}",
                f"- Critical issues: {len(critical_uplinks)}",
                f"- Warning issues: {len(warning_uplinks)}",
                f"- Switches affected: {report.switches_with_issues}",
                f"",
            ]
            
            # Critical issues
            if critical_uplinks:
                message_lines.append("CRITICAL ISSUES:")
                for uplink in critical_uplinks:
                    message_lines.append(
                        f"- {uplink.switch_hostname} ({uplink.switch_ip}) - "
                        f"Port {uplink.port_name}: {', '.join(uplink.alerts)}"
                    )
                message_lines.append("")
            
            # Warning issues
            if warning_uplinks:
                message_lines.append("WARNING ISSUES:")
                for uplink in warning_uplinks[:10]:  # Limit to first 10 warnings
                    message_lines.append(
                        f"- {uplink.switch_hostname} ({uplink.switch_ip}) - "
                        f"Port {uplink.port_name}: {', '.join(uplink.alerts)}"
                    )
                if len(warning_uplinks) > 10:
                    message_lines.append(f"... and {len(warning_uplinks) - 10} more warnings")
                message_lines.append("")
            
            message_lines.append(f"Monitoring completed in {report.execution_time}s")
            
            message = "\n".join(message_lines)
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.ALERT_EMAIL_RECIPIENTS,
                fail_silently=False
            )
            
            self.log_info(f"Sent uplink monitoring notification email")
            return 1
            
        except Exception as e:
            self.log_error(f"Error sending uplink monitoring notifications: {e}")
            return 0
    
    def get_uplink_summary(self, switch_id: Optional[int] = None) -> Dict[str, Any]:
        """Get uplink monitoring summary."""
        try:
            # Get cached report
            cached_report = cache.get('uplink_monitoring_report')
            if not cached_report:
                return {"error": "No recent monitoring data available"}
            
            report_data = cached_report
            
            # Filter by switch if specified
            if switch_id:
                uplink_statuses = [
                    status for status in report_data.get('uplink_statuses', [])
                    if status.get('switch_id') == switch_id
                ]
            else:
                uplink_statuses = report_data.get('uplink_statuses', [])
            
            # Generate summary
            summary = {
                'last_update': report_data.get('timestamp'),
                'total_uplinks': len(uplink_statuses),
                'healthy': sum(1 for s in uplink_statuses if s.get('status_severity') == 'normal'),
                'warning': sum(1 for s in uplink_statuses if s.get('status_severity') == 'warning'),
                'critical': sum(1 for s in uplink_statuses if s.get('status_severity') == 'critical'),
                'offline': sum(1 for s in uplink_statuses if s.get('operational_status') == 'down'),
                'execution_time': report_data.get('execution_time', 0),
                'switches_monitored': len(set(s.get('switch_id') for s in uplink_statuses)),
            }
            
            return summary
            
        except Exception as e:
            self.log_error(f"Error generating uplink summary: {e}")
            return {"error": str(e)}