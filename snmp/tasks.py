"""
Celery tasks for SNMP monitoring operations.

Tasks are designed to be run periodically via celery beat
or triggered manually through the admin/API.
"""
import logging
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
