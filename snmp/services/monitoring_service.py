"""
Service layer for monitoring and alerting.
"""
import time
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from datetime import timedelta

from ..models import Switch, Branch
from .base_service import BaseService
from .snmp_service import SNMPService


class MonitoringService(BaseService):
    """
    Service for monitoring switches and generating alerts.
    """
    
    def __init__(self):
        super().__init__()
        self.snmp_service = SNMPService()
        
        # Alert thresholds
        self.high_signal_threshold = -15  # dBm
        self.low_signal_threshold = -25   # dBm
        self.offline_alert_threshold = 300  # 5 minutes
        
    def check_switch_health(self, switch: Switch) -> Dict[str, Any]:
        """
        Comprehensive health check for a single switch.
        """
        start_time = time.time()
        
        health_report = {
            'switch_id': switch.id,
            'hostname': switch.hostname,
            'ip': switch.ip,
            'timestamp': timezone.now(),
            'checks': {
                'connectivity': {'status': 'unknown', 'details': {}},
                'optical_signals': {'status': 'unknown', 'details': {}},
                'uptime': {'status': 'unknown', 'details': {}},
                'performance': {'status': 'unknown', 'details': {}}
            },
            'overall_status': 'unknown',
            'alerts': [],
            'execution_time': 0
        }
        
        try:
            # Connectivity check
            connectivity = self._check_connectivity(switch)
            health_report['checks']['connectivity'] = connectivity
            
            if connectivity['status'] == 'healthy':
                # Optical signals check
                optical = self._check_optical_signals(switch)
                health_report['checks']['optical_signals'] = optical
                
                # Uptime check
                uptime = self._check_uptime(switch)
                health_report['checks']['uptime'] = uptime
                
                # Performance check
                performance = self._check_performance(switch)
                health_report['checks']['performance'] = performance
            
            # Determine overall status and alerts
            health_report = self._analyze_health_report(health_report)
            
            # Update switch status
            self._update_switch_status(switch, health_report)
            
        except Exception as e:
            self.log_error(f"Error during health check for switch {switch.id}: {e}")
            health_report['overall_status'] = 'error'
            health_report['alerts'].append({
                'level': 'critical',
                'message': f"Health check failed: {e}"
            })
        
        finally:
            health_report['execution_time'] = round(time.time() - start_time, 2)
            
        return health_report
    
    def _check_connectivity(self, switch: Switch) -> Dict[str, Any]:
        """Check switch connectivity (ping + SNMP)."""
        result = {
            'status': 'unhealthy',
            'details': {
                'ping_success': False,
                'ping_time': None,
                'snmp_success': False,
                'last_check': timezone.now()
            }
        }
        
        try:
            # Test connectivity
            connectivity_test = self.snmp_service.test_connectivity(
                switch.ip, 
                switch.snmp_community_ro
            )
            
            result['details'].update(connectivity_test)
            
            if connectivity_test['ping_success'] and connectivity_test['snmp_success']:
                result['status'] = 'healthy'
            elif connectivity_test['ping_success']:
                result['status'] = 'warning'  # Ping OK but SNMP failed
            else:
                result['status'] = 'unhealthy'
                
        except Exception as e:
            self.log_error(f"Connectivity check failed for switch {switch.id}: {e}")
            result['details']['error'] = str(e)
        
        return result
    
    def _check_optical_signals(self, switch: Switch) -> Dict[str, Any]:
        """Check optical signal levels."""
        result = {
            'status': 'healthy',
            'details': {
                'rx_signal': None,
                'tx_signal': None,
                'rx_status': 'unknown',
                'tx_status': 'unknown',
                'last_check': timezone.now()
            }
        }
        
        try:
            if not switch.model or not (switch.model.rx_oid or switch.model.tx_oid):
                result['status'] = 'skipped'
                result['details']['message'] = 'No optical OIDs configured'
                return result
            
            snmp_client = self.snmp_service.get_snmp_client(
                switch.ip, 
                switch.snmp_community_ro
            )
            
            if snmp_client:
                signals = self.snmp_service.get_optical_signal_levels(
                    snmp_client,
                    switch.model.rx_oid,
                    switch.model.tx_oid
                )
                
                result['details'].update(signals)
                
                # Analyze signal levels
                rx_status = self._analyze_signal_level(signals['rx_signal'], 'RX')
                tx_status = self._analyze_signal_level(signals['tx_signal'], 'TX')
                
                result['details']['rx_status'] = rx_status
                result['details']['tx_status'] = tx_status
                
                # Overall optical status
                if rx_status == 'critical' or tx_status == 'critical':
                    result['status'] = 'unhealthy'
                elif rx_status == 'warning' or tx_status == 'warning':
                    result['status'] = 'warning'
                else:
                    result['status'] = 'healthy'
            
        except Exception as e:
            self.log_error(f"Optical signal check failed for switch {switch.id}: {e}")
            result['status'] = 'error'
            result['details']['error'] = str(e)
        
        return result
    
    def _analyze_signal_level(self, signal_level: Optional[float], signal_type: str) -> str:
        """Analyze signal level and return status."""
        if signal_level is None:
            return 'unknown'
        
        if signal_level > self.high_signal_threshold:
            return 'critical'  # Signal too high
        elif signal_level < self.low_signal_threshold:
            return 'critical'  # Signal too low
        elif signal_level > (self.high_signal_threshold - 5):
            return 'warning'   # Getting close to high threshold
        else:
            return 'healthy'
    
    def _check_uptime(self, switch: Switch) -> Dict[str, Any]:
        """Check switch uptime."""
        result = {
            'status': 'healthy',
            'details': {
                'uptime': None,
                'uptime_seconds': None,
                'last_check': timezone.now()
            }
        }
        
        try:
            snmp_client = self.snmp_service.get_snmp_client(
                switch.ip, 
                switch.snmp_community_ro
            )
            
            if snmp_client:
                uptime = self.snmp_service.get_system_uptime(snmp_client)
                if uptime:
                    result['details']['uptime'] = uptime
                    
                    # Extract seconds from uptime (simplified)
                    # You may need more sophisticated parsing
                    if 'd' in uptime:
                        days = int(uptime.split('d')[0])
                        result['details']['uptime_seconds'] = days * 86400
                    
                    # Check if uptime is suspiciously low (recent reboot)
                    if result['details']['uptime_seconds'] and result['details']['uptime_seconds'] < 3600:
                        result['status'] = 'warning'
                        result['details']['message'] = 'Recent reboot detected'
            
        except Exception as e:
            self.log_error(f"Uptime check failed for switch {switch.id}: {e}")
            result['status'] = 'error'
            result['details']['error'] = str(e)
        
        return result
    
    def _check_performance(self, switch: Switch) -> Dict[str, Any]:
        """Check switch performance metrics."""
        result = {
            'status': 'healthy',
            'details': {
                'response_time': None,
                'last_update_age': None,
                'last_check': timezone.now()
            }
        }
        
        try:
            # Check last update age
            if switch.last_update:
                age_seconds = (timezone.now() - switch.last_update).total_seconds()
                result['details']['last_update_age'] = age_seconds
                
                # Alert if data is stale (older than 1 hour)
                if age_seconds > 3600:
                    result['status'] = 'warning'
                    result['details']['message'] = f'Data is {age_seconds/60:.0f} minutes old'
                elif age_seconds > 7200:  # 2 hours
                    result['status'] = 'unhealthy'
                    result['details']['message'] = f'Data is {age_seconds/3600:.1f} hours old'
            
        except Exception as e:
            self.log_error(f"Performance check failed for switch {switch.id}: {e}")
            result['status'] = 'error'
            result['details']['error'] = str(e)
        
        return result
    
    def _analyze_health_report(self, health_report: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze health report and generate alerts."""
        checks = health_report['checks']
        alerts = []
        
        # Connectivity alerts
        if checks['connectivity']['status'] == 'unhealthy':
            alerts.append({
                'level': 'critical',
                'category': 'connectivity',
                'message': 'Switch is unreachable'
            })
        elif checks['connectivity']['status'] == 'warning':
            alerts.append({
                'level': 'warning',
                'category': 'connectivity',
                'message': 'SNMP connection failed but ping successful'
            })
        
        # Optical signal alerts
        optical = checks['optical_signals']
        if optical['status'] == 'unhealthy':
            if optical['details'].get('rx_status') == 'critical':
                alerts.append({
                    'level': 'critical',
                    'category': 'optical',
                    'message': f"RX signal critical: {optical['details'].get('rx_signal')} dBm"
                })
            if optical['details'].get('tx_status') == 'critical':
                alerts.append({
                    'level': 'critical',
                    'category': 'optical',
                    'message': f"TX signal critical: {optical['details'].get('tx_signal')} dBm"
                })
        elif optical['status'] == 'warning':
            alerts.append({
                'level': 'warning',
                'category': 'optical',
                'message': 'Optical signal levels approaching thresholds'
            })
        
        # Performance alerts
        if checks['performance']['status'] == 'warning':
            alerts.append({
                'level': 'warning',
                'category': 'performance',
                'message': checks['performance']['details'].get('message', 'Performance issue')
            })
        
        health_report['alerts'] = alerts
        
        # Determine overall status
        statuses = [check['status'] for check in checks.values()]
        if 'unhealthy' in statuses or 'error' in statuses:
            health_report['overall_status'] = 'unhealthy'
        elif 'warning' in statuses:
            health_report['overall_status'] = 'warning'
        else:
            health_report['overall_status'] = 'healthy'
        
        return health_report
    
    def _update_switch_status(self, switch: Switch, health_report: Dict[str, Any]):
        """Update switch status based on health report."""
        try:
            is_online = health_report['overall_status'] in ['healthy', 'warning']
            
            # Update optical signal levels if available
            optical_details = health_report['checks']['optical_signals']['details']
            
            update_data = {
                'status': is_online,
                'last_update': timezone.now()
            }
            
            if optical_details.get('rx_signal') is not None:
                update_data['rx_signal'] = optical_details['rx_signal']
            
            if optical_details.get('tx_signal') is not None:
                update_data['tx_signal'] = optical_details['tx_signal']
            
            # Update uptime if available
            uptime_details = health_report['checks']['uptime']['details']
            if uptime_details.get('uptime'):
                update_data['uptime'] = uptime_details['uptime']
            
            # Update switch
            for key, value in update_data.items():
                setattr(switch, key, value)
            switch.save()
            
            # Cache health report
            cache.set(f'health_report_{switch.id}', health_report, 300)  # 5 minutes
            
        except Exception as e:
            self.log_error(f"Error updating switch {switch.id} status: {e}")
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get system-wide monitoring overview."""
        try:
            overview = {
                'timestamp': timezone.now(),
                'switches': {
                    'total': Switch.objects.count(),
                    'online': Switch.objects.filter(status=True).count(),
                    'offline': Switch.objects.filter(status=False).count(),
                    'with_high_signals': Switch.objects.filter(
                        Q(rx_signal__gt=self.high_signal_threshold) | 
                        Q(tx_signal__gt=self.high_signal_threshold)
                    ).count(),
                    'stale_data': Switch.objects.filter(
                        last_update__lt=timezone.now() - timedelta(hours=1)
                    ).count()
                },
                'branches': {},
                'recent_alerts': [],
                'performance': {
                    'avg_response_time': 0,
                    'health_check_duration': 0
                }
            }
            
            # Calculate percentages
            total = overview['switches']['total']
            if total > 0:
                overview['switches']['online_percentage'] = round(
                    (overview['switches']['online'] / total) * 100, 2
                )
                overview['switches']['offline_percentage'] = round(
                    (overview['switches']['offline'] / total) * 100, 2
                )
            
            # Branch statistics
            branches = Branch.objects.all()
            for branch in branches:
                branch_switches = Switch.objects.filter(branch=branch)
                overview['branches'][branch.name] = {
                    'total': branch_switches.count(),
                    'online': branch_switches.filter(status=True).count(),
                    'offline': branch_switches.filter(status=False).count()
                }
            
            return overview
            
        except Exception as e:
            self.log_error(f"Error getting system overview: {e}")
            return {
                'timestamp': timezone.now(),
                'error': str(e),
                'switches': {'total': 0, 'online': 0, 'offline': 0}
            }
    
    def generate_alert_notifications(self, health_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate and send alert notifications based on health reports."""
        try:
            critical_alerts = []
            warning_alerts = []
            
            for report in health_reports:
                for alert in report.get('alerts', []):
                    alert_data = {
                        'switch_id': report['switch_id'],
                        'hostname': report['hostname'],
                        'ip': report['ip'],
                        'timestamp': report['timestamp'],
                        'level': alert['level'],
                        'category': alert['category'],
                        'message': alert['message']
                    }
                    
                    if alert['level'] == 'critical':
                        critical_alerts.append(alert_data)
                    else:
                        warning_alerts.append(alert_data)
            
            # Send notifications if configured
            notifications_sent = {
                'email_sent': False,
                'critical_count': len(critical_alerts),
                'warning_count': len(warning_alerts),
                'total_alerts': len(critical_alerts) + len(warning_alerts)
            }
            
            if critical_alerts and hasattr(settings, 'ALERT_EMAIL_RECIPIENTS'):
                self._send_email_alerts(critical_alerts, 'critical')
                notifications_sent['email_sent'] = True
            
            return notifications_sent
            
        except Exception as e:
            self.log_error(f"Error generating alert notifications: {e}")
            return {'error': str(e), 'email_sent': False}
    
    def _send_email_alerts(self, alerts: List[Dict[str, Any]], level: str):
        """Send email alerts for critical issues."""
        try:
            if not hasattr(settings, 'ALERT_EMAIL_RECIPIENTS'):
                return
            
            subject = f"[SNMP Monitor] {level.upper()} Alert - {len(alerts)} issues detected"
            
            message_lines = [
                f"SNMP Monitor Alert Report - {timezone.now()}",
                f"Alert Level: {level.upper()}",
                f"Total Issues: {len(alerts)}",
                "",
                "Issues:"
            ]
            
            for alert in alerts:
                message_lines.append(
                    f"- {alert['hostname']} ({alert['ip']}): {alert['message']}"
                )
            
            message = "\n".join(message_lines)
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.ALERT_EMAIL_RECIPIENTS,
                fail_silently=False
            )
            
            self.log_info(f"Alert email sent for {len(alerts)} {level} alerts")
            
        except Exception as e:
            self.log_error(f"Error sending email alerts: {e}")