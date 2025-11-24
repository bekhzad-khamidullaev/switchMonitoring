"""
Celery tasks for automated network device monitoring and discovery.
Production-ready tasks with error handling and monitoring.
"""
import logging
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from django.core.cache import cache

from .models import Switch
from .services import (
    DeviceDiscoveryService,
    UplinkMonitoringService, 
    MonitoringService
)

logger = logging.getLogger('snmp.tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def update_switch_status_task(self):
    """Update status of all switches."""
    try:
        logger.info("Starting switch status update task")
        call_command('update_switch_status')
        logger.info("Switch status update task completed successfully")
    except Exception as exc:
        logger.error(f"Switch status update failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def update_optical_info_task(self):
    """Update optical information for all switches."""
    try:
        logger.info("Starting optical info update task")
        call_command('update_optical_info')
        logger.info("Optical info update task completed successfully")
    except Exception as exc:
        logger.error(f"Optical info update failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def update_switch_inventory_task(self):
    """Update switch inventory information."""
    try:
        logger.info("Starting switch inventory update task")
        call_command('update_switch_inventory')
        logger.info("Switch inventory update task completed successfully")
    except Exception as exc:
        logger.error(f"Switch inventory update failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=1800)
def subnet_discovery_task(self):
    """Discover new devices on network subnets."""
    try:
        logger.info("Starting subnet discovery task")
        call_command('subnet_discovery')
        logger.info("Subnet discovery task completed successfully")
    except Exception as exc:
        logger.error(f"Subnet discovery failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def auto_discover_devices_task(self, update_existing=True, monitor_uplinks=True):
    """
    Automatically discover and update device information.
    
    Args:
        update_existing: Whether to update existing devices
        monitor_uplinks: Whether to monitor uplink ports
    """
    try:
        logger.info("Starting auto device discovery task")
        
        discovery_service = DeviceDiscoveryService()
        switches = Switch.objects.all()
        
        discovered_count = 0
        updated_count = 0
        
        for switch in switches:
            try:
                # Discover device information
                device_info = discovery_service.discover_device(
                    switch.ip, 
                    switch.snmp_community_ro
                )
                
                if device_info:
                    # Update device in database
                    if discovery_service.auto_update_device_in_db(switch):
                        if switch.model:
                            updated_count += 1
                        else:
                            discovered_count += 1
                        
                        logger.info(f"Updated device: {switch.hostname} - {device_info.vendor} {device_info.model}")
                    
                    # Monitor uplinks if enabled
                    if monitor_uplinks:
                        uplink_service = UplinkMonitoringService()
                        uplinks = uplink_service.monitor_switch_uplinks(switch)
                        logger.debug(f"Monitored {len(uplinks)} uplinks for {switch.hostname}")
                
            except Exception as e:
                logger.error(f"Error processing switch {switch.hostname}: {e}")
                continue
        
        # Cache results
        cache.set('auto_discovery_stats', {
            'last_run': timezone.now().isoformat(),
            'discovered_count': discovered_count,
            'updated_count': updated_count,
            'total_processed': switches.count()
        }, 3600)
        
        logger.info(f"Auto discovery completed: {discovered_count} discovered, {updated_count} updated")
        
    except Exception as exc:
        logger.error(f"Auto device discovery failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def monitor_all_uplinks_task(self, send_alerts=True, parallel=True):
    """
    Monitor all uplink ports and optical signals.
    
    Args:
        send_alerts: Whether to send alert notifications
        parallel: Whether to run monitoring in parallel
    """
    try:
        logger.info("Starting comprehensive uplink monitoring task")
        
        uplink_service = UplinkMonitoringService()
        
        # Run uplink monitoring
        report = uplink_service.monitor_all_uplinks(
            parallel=parallel,
            max_workers=10
        )
        
        # Send notifications if there are issues and alerts enabled
        if send_alerts and (report.critical_uplinks > 0 or report.warning_uplinks > 0):
            notifications_sent = uplink_service._send_notifications(report)
            report.notifications_sent = notifications_sent
        
        # Cache monitoring report
        from dataclasses import asdict
        report_dict = asdict(report)
        report_dict['timestamp'] = report.timestamp.isoformat()
        
        for uplink in report_dict['uplink_statuses']:
            if uplink['last_update']:
                uplink['last_update'] = uplink['last_update'].isoformat()
        
        cache.set('uplink_monitoring_report', report_dict, 3600)
        
        logger.info(
            f"Uplink monitoring completed: {report.total_uplinks_monitored} uplinks, "
            f"{report.critical_uplinks} critical, {report.warning_uplinks} warnings"
        )
        
        return {
            'total_uplinks': report.total_uplinks_monitored,
            'critical': report.critical_uplinks,
            'warnings': report.warning_uplinks,
            'execution_time': report.execution_time
        }
        
    except Exception as exc:
        logger.error(f"Uplink monitoring task failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def comprehensive_health_check_task(self, send_alerts=False):
    """
    Run comprehensive health checks on all switches.
    
    Args:
        send_alerts: Whether to send alert notifications
    """
    try:
        logger.info("Starting comprehensive health check task")
        
        monitoring_service = MonitoringService()
        
        # Get all active switches
        switches = Switch.objects.filter(status=True)
        health_reports = []
        
        for switch in switches:
            try:
                health_report = monitoring_service.check_switch_health(switch)
                health_reports.append(health_report)
            except Exception as e:
                logger.error(f"Health check failed for switch {switch.hostname}: {e}")
                continue
        
        # Generate notifications if requested
        if send_alerts and health_reports:
            notifications = monitoring_service.generate_alert_notifications(health_reports)
            logger.info(f"Sent {notifications.get('total_alerts', 0)} health check alerts")
        
        # Generate summary
        total_switches = len(health_reports)
        healthy_switches = sum(1 for r in health_reports if r['overall_status'] == 'healthy')
        warning_switches = sum(1 for r in health_reports if r['overall_status'] == 'warning')
        critical_switches = sum(1 for r in health_reports if r['overall_status'] == 'unhealthy')
        
        # Cache health check summary
        cache.set('health_check_summary', {
            'last_run': timezone.now().isoformat(),
            'total_switches': total_switches,
            'healthy': healthy_switches,
            'warning': warning_switches,
            'critical': critical_switches,
        }, 1800)  # Cache for 30 minutes
        
        logger.info(
            f"Health check completed: {total_switches} switches, "
            f"{healthy_switches} healthy, {warning_switches} warnings, {critical_switches} critical"
        )
        
        return {
            'total_switches': total_switches,
            'healthy': healthy_switches,
            'warnings': warning_switches,
            'critical': critical_switches
        }
        
    except Exception as exc:
        logger.error(f"Comprehensive health check failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def cleanup_old_data_task():
    """Clean up old monitoring data and logs."""
    try:
        logger.info("Starting data cleanup task")
        
        from django.db import connection
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Clean up old switch ports data
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM switches_ports WHERE data < %s", 
                [cutoff_date]
            )
            deleted_ports = cursor.rowcount
        
        # Clean up old MAC history (if exists)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM mac WHERE data < %s", 
                    [cutoff_date]
                )
                deleted_macs = cursor.rowcount
        except:
            deleted_macs = 0
        
        logger.info(f"Cleanup completed: {deleted_ports} old port records, {deleted_macs} old MAC records")
        
    except Exception as exc:
        logger.error(f"Data cleanup failed: {exc}")


@shared_task
def generate_daily_report_task():
    """Generate daily monitoring report."""
    try:
        logger.info("Generating daily monitoring report")
        
        # Get monitoring statistics
        total_switches = Switch.objects.count()
        online_switches = Switch.objects.filter(status=True).count()
        
        # Get recent uplink monitoring data
        uplink_report = cache.get('uplink_monitoring_report', {})
        health_summary = cache.get('health_check_summary', {})
        
        daily_stats = {
            'date': timezone.now().date().isoformat(),
            'total_switches': total_switches,
            'online_switches': online_switches,
            'offline_switches': total_switches - online_switches,
            'uplink_stats': {
                'total_uplinks': uplink_report.get('total_uplinks_monitored', 0),
                'critical_uplinks': uplink_report.get('critical_uplinks', 0),
                'warning_uplinks': uplink_report.get('warning_uplinks', 0),
            },
            'health_stats': health_summary,
        }
        
        # Cache daily report
        cache.set(f'daily_report_{timezone.now().date()}', daily_stats, 86400 * 7)  # Keep for a week
        
        logger.info("Daily report generated successfully")
        
    except Exception as exc:
        logger.error(f"Daily report generation failed: {exc}")


# Periodic task to check task health
@shared_task
def task_health_check():
    """Monitor the health of Celery tasks."""
    try:
        from celery import current_app
        
        # Get task statistics
        inspect = current_app.control.inspect()
        
        stats = {
            'timestamp': timezone.now().isoformat(),
            'active_tasks': len(inspect.active() or {}),
            'scheduled_tasks': len(inspect.scheduled() or {}),
            'reserved_tasks': len(inspect.reserved() or {}),
        }
        
        # Cache task health stats
        cache.set('celery_health_stats', stats, 300)  # Cache for 5 minutes
        
        logger.info(f"Task health check completed: {stats}")
        
    except Exception as exc:
        logger.warning(f"Task health check failed: {exc}")
