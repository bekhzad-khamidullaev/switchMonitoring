from django.db import migrations

def migrate_switch_to_device(apps, schema_editor):
    Switch = apps.get_model('snmp', 'Switch')
    Device = apps.get_model('snmp', 'Device')
    SwitchesPorts = apps.get_model('snmp', 'SwitchesPorts')
    Mac = apps.get_model('snmp', 'Mac')

    for switch in Switch.objects.all():
        if not switch.ip:
            print(f"Skipping switch {switch.id} ({switch.hostname}) - NO IP")
            continue

        # Get or create device by IP
        device, created = Device.objects.get_or_create(
            ip=switch.ip,
            defaults={
                'hostname': switch.hostname or "",
                'status': bool(switch.status),
            }
        )
        
        # Update device with switch fields (prefer non-empty values)
        if switch.hostname:
            device.hostname = switch.hostname
        
        device.uptime = switch.uptime or device.uptime
        device.switch_mac = switch.switch_mac or device.switch_mac
        device.snmp_community_ro = switch.snmp_community_ro or device.snmp_community_ro
        device.snmp_community_rw = switch.snmp_community_rw or device.snmp_community_rw
        device.status = switch.status if switch.status is not None else device.status
        device.neighbor = switch.neighbor or device.neighbor
        device.parent_port = switch.port or device.parent_port
        device.branch = switch.branch or device.branch
        device.ats = switch.ats or device.ats
        device.soft_version = switch.soft_version or device.soft_version
        device.serial_number = switch.serial_number or device.serial_number
        device.rx_signal = switch.rx_signal if switch.rx_signal is not None else device.rx_signal
        device.tx_signal = switch.tx_signal if switch.tx_signal is not None else device.tx_signal
        device.sfp_vendor = switch.sfp_vendor or device.sfp_vendor
        device.part_number = switch.part_number or device.part_number
        device.device_type = switch.model or device.device_type
        device.save()

        # Update related models
        SwitchesPorts.objects.filter(managed_device_id=switch.id).update(managed_device_id=device.id)
        Mac.objects.filter(managed_device_id=switch.id).update(managed_device_id=device.id)

class Migration(migrations.Migration):
    dependencies = [
        ('snmp', '0034_add_switch_fields_to_device'),
    ]

    operations = [
        migrations.RunPython(migrate_switch_to_device),
    ]
