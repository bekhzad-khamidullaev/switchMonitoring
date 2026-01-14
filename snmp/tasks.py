"""
Celery tasks for SNMP monitoring operations.

Tasks are designed to be run periodically via celery beat
or triggered manually through the admin/API.
"""
import logging
from datetime import timedelta
from celery import shared_task, group
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# -------------------------
# Device Status Tasks
# -------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_device_status_task(self):
    """Update online/offline status for all devices."""
    try:
        call_command('update_switch_status')
    except Exception as exc:
        logger.error(f"Device status update failed: {exc}")
        raise self.retry(exc=exc)


# Backward compatibility alias
update_switch_status_task = update_device_status_task


# -------------------------
# Optical Signal Tasks
# -------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def update_optical_info_task(self):
    """Update optical signal info for all devices using MIB collector."""
    try:
        call_command('update_optical_info_mib')
    except Exception as exc:
        logger.error(f"Optical info update failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def update_optical_single_device_task(self, device_id: int):
    """Update optical info for a single device."""
    try:
        call_command('update_optical_info_mib', switch_id=device_id)
        logger.info(f"Optical info updated for device {device_id}")
    except Exception as exc:
        logger.error(f"Optical update failed for device {device_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def update_optical_batch_task(device_ids: list):
    """
    Update optical info for a batch of devices in parallel.
    
    Usage:
        update_optical_batch_task.delay([1, 2, 3, 4, 5])
    """
    job = group(
        update_optical_single_device_task.s(device_id) 
        for device_id in device_ids
    )
    result = job.apply_async()
    return f"Started optical update for {len(device_ids)} devices"


@shared_task
def update_optical_critical_task():
    """
    Priority task: Update optical info only for devices with critical/warning signals.
    Runs more frequently to catch signal degradation faster.
    """
    from snmp.models import Device, InterfaceOptics
    
    # Find devices with critical or warning signal levels
    critical_device_ids = list(
        InterfaceOptics.objects
        .filter(rx_dbm__lte=-20)  # Warning and critical
        .values_list('interface__device_id', flat=True)
        .distinct()
    )
    
    if not critical_device_ids:
        logger.info("No devices with critical/warning optical signals")
        return "No critical devices to update"
    
    logger.info(f"Updating optical for {len(critical_device_ids)} critical/warning devices")
    
    # Update in parallel
    job = group(
        update_optical_single_device_task.s(device_id) 
        for device_id in critical_device_ids[:50]  # Limit batch size
    )
    job.apply_async()
    return f"Started critical optical update for {len(critical_device_ids)} devices"


# -------------------------
# Inventory Tasks
# -------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def update_device_inventory_task(self):
    """Update device inventory (model, serial, software version)."""
    try:
        call_command('update_switch_inventory')
    except Exception as exc:
        logger.error(f"Inventory update failed: {exc}")
        raise self.retry(exc=exc)


# Backward compatibility alias
update_switch_inventory_task = update_device_inventory_task


# -------------------------
# Discovery Tasks
# -------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def subnet_discovery_task(self):
    """Discover new devices on configured subnets."""
    try:
        call_command('subnet_discovery')
    except Exception as exc:
        logger.error(f"Subnet discovery failed: {exc}")
        raise self.retry(exc=exc)


# -------------------------
# Bandwidth Tasks
# -------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def poll_bandwidth_task(self):
    """Poll bandwidth counters for all interfaces."""
    try:
        call_command('poll_bandwidth')
    except Exception as exc:
        logger.error(f"Bandwidth poll failed: {exc}")
        raise self.retry(exc=exc)


@shared_task
def cleanup_bandwidth_samples_task():
    """Clean up old bandwidth samples to manage database size."""
    try:
        call_command('cleanup_bandwidth_samples')
        logger.info("Bandwidth samples cleanup completed")
    except Exception as exc:
        logger.error(f"Bandwidth cleanup failed: {exc}")


# -------------------------
# Alerting Tasks
# -------------------------

@shared_task
def check_optical_alerts_task():
    """
    Check for critical optical signal levels and generate alerts.
    Can be extended to send notifications via email, Telegram, etc.
    """
    from snmp.models import Interface, InterfaceOptics
    
    # Find critical signals (RX <= -25 dBm)
    critical = (
        InterfaceOptics.objects
        .filter(rx_dbm__lte=-25)
        .select_related('interface', 'interface__device')
        .order_by('rx_dbm')
    )
    
    critical_count = critical.count()
    
    if critical_count > 0:
        logger.warning(f"ALERT: {critical_count} interfaces with critical optical signal!")
        
        # Log top 10 worst signals
        for optics in critical[:10]:
            iface = optics.interface
            device = iface.device
            logger.warning(
                f"  Critical: {device.hostname} ({device.ip}) - "
                f"{iface.name}: RX={optics.rx_dbm} dBm"
            )
    
    # Find newly degraded signals (warning level)
    warning = (
        InterfaceOptics.objects
        .filter(rx_dbm__gt=-25, rx_dbm__lte=-20)
        .count()
    )
    
    return {
        'critical': critical_count,
        'warning': warning,
        'checked_at': timezone.now().isoformat()
    }


@shared_task
def generate_optical_report_task():
    """
    Generate daily optical signal report.
    Can be extended to save to file or send via email.
    """
    from snmp.models import Interface, InterfaceOptics
    from django.db.models import Avg, Min, Max, Count
    
    stats = InterfaceOptics.objects.exclude(rx_dbm__isnull=True).aggregate(
        total=Count('id'),
        avg_rx=Avg('rx_dbm'),
        min_rx=Min('rx_dbm'),
        max_rx=Max('rx_dbm'),
    )
    
    critical = InterfaceOptics.objects.filter(rx_dbm__lte=-25).count()
    warning = InterfaceOptics.objects.filter(rx_dbm__gt=-25, rx_dbm__lte=-20).count()
    normal = InterfaceOptics.objects.filter(rx_dbm__gt=-20).count()
    
    report = {
        'date': timezone.now().date().isoformat(),
        'total_optical_ports': stats['total'],
        'avg_rx_dbm': round(stats['avg_rx'], 2) if stats['avg_rx'] else None,
        'min_rx_dbm': stats['min_rx'],
        'max_rx_dbm': stats['max_rx'],
        'critical_count': critical,
        'warning_count': warning,
        'normal_count': normal,
    }
    
    logger.info(f"Daily Optical Report: {report}")
    return report


@shared_task
def record_optics_history_task():
    """
    Record current optical readings to history table for trending.
    Should run after each optical poll to capture time-series data.
    """
    from snmp.models import Interface, InterfaceOptics, OpticsHistorySample
    
    now = timezone.now()
    recorded = 0
    
    # Get all interfaces with optics data
    optics_data = InterfaceOptics.objects.filter(
        rx_dbm__isnull=False
    ).select_related('interface')
    
    samples_to_create = []
    for optics in optics_data:
        samples_to_create.append(OpticsHistorySample(
            interface=optics.interface,
            ts=now,
            rx_dbm=optics.rx_dbm,
            tx_dbm=optics.tx_dbm,
            temperature_c=optics.temperature_c,
            voltage_v=optics.voltage_v,
        ))
    
    # Bulk create for efficiency
    if samples_to_create:
        OpticsHistorySample.objects.bulk_create(samples_to_create, batch_size=500)
        recorded = len(samples_to_create)
    
    logger.info(f"Recorded {recorded} optical history samples")
    return recorded


@shared_task
def cleanup_optics_history_task(days_to_keep=30):
    """
    Clean up old optical history samples to manage database size.
    Default: keep 30 days of history.
    """
    from snmp.models import OpticsHistorySample
    
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    deleted, _ = OpticsHistorySample.objects.filter(ts__lt=cutoff).delete()
    
    logger.info(f"Deleted {deleted} old optical history samples (older than {days_to_keep} days)")
    return deleted


@shared_task
def create_optics_alerts_task():
    """
    Check current optical levels and create alerts for threshold violations.
    """
    from snmp.models import InterfaceOptics, OpticsAlert
    
    now = timezone.now()
    created_alerts = 0
    resolved_alerts = 0
    
    # Critical threshold: RX <= -25 dBm
    critical_optics = InterfaceOptics.objects.filter(rx_dbm__lte=-25).select_related('interface')
    
    for optics in critical_optics:
        # Check if active alert already exists
        existing = OpticsAlert.objects.filter(
            interface=optics.interface,
            status=OpticsAlert.STATUS_ACTIVE
        ).first()
        
        if not existing:
            OpticsAlert.objects.create(
                interface=optics.interface,
                severity=OpticsAlert.SEVERITY_CRITICAL,
                status=OpticsAlert.STATUS_ACTIVE,
                rx_dbm=optics.rx_dbm,
                threshold=-25.0,
                message=f"Critical optical signal: {optics.rx_dbm} dBm (threshold: -25 dBm)"
            )
            created_alerts += 1
    
    # Warning threshold: -25 < RX <= -20 dBm
    warning_optics = InterfaceOptics.objects.filter(
        rx_dbm__gt=-25, rx_dbm__lte=-20
    ).select_related('interface')
    
    for optics in warning_optics:
        existing = OpticsAlert.objects.filter(
            interface=optics.interface,
            status=OpticsAlert.STATUS_ACTIVE
        ).first()
        
        if not existing:
            OpticsAlert.objects.create(
                interface=optics.interface,
                severity=OpticsAlert.SEVERITY_WARNING,
                status=OpticsAlert.STATUS_ACTIVE,
                rx_dbm=optics.rx_dbm,
                threshold=-20.0,
                message=f"Warning optical signal: {optics.rx_dbm} dBm (threshold: -20 dBm)"
            )
            created_alerts += 1
    
    # Auto-resolve alerts where signal is now normal
    normal_interface_ids = list(
        InterfaceOptics.objects.filter(rx_dbm__gt=-20)
        .values_list('interface_id', flat=True)
    )
    
    resolved = OpticsAlert.objects.filter(
        interface_id__in=normal_interface_ids,
        status=OpticsAlert.STATUS_ACTIVE
    ).update(
        status=OpticsAlert.STATUS_RESOLVED,
        resolved_at=now
    )
    resolved_alerts = resolved
    
    logger.info(f"Optics alerts: created={created_alerts}, resolved={resolved_alerts}")
    return {'created': created_alerts, 'resolved': resolved_alerts}
