from django.db import models
from simple_history.models import HistoricalRecords
from django.utils import timezone
from ipaddress import ip_address, IPv4Network
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group

@receiver(post_migrate)
def create_branch_permissions(sender, **kwargs):
    """Create per-branch view permissions.

    IMPORTANT:
    This must only run after *snmp* migrations, otherwise it can break the global
    migrate flow (contenttypes/auth tables may not be ready yet).
    """
    if getattr(sender, 'name', None) != 'snmp':
        return

    try:
        content_type = ContentType.objects.get_for_model(Branch)
    except Exception:
        # During initial migrate or partial states we skip silently.
        return

    for branch in Branch.objects.all():
        if not branch.name:
            continue
        codename = f"view_{branch.name.lower().replace(' ', '_')}"
        name = f"Can view switches in {branch.name}"
        try:
            Permission.objects.get_or_create(
                codename=codename,
                name=name,
                content_type=content_type,
            )
        except Exception:
            continue

        # Optionally, assign the permission to a specific group
        # For example, if you have a group named "Branch Managers"
        # group = Group.objects.get(name='Branch Managers')
        # group.permissions.add(permission)



class Branch(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        managed = True
        db_table = 'branch'

    def __str__(self):
        return self.name



class Ats(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    subnet = models.GenericIPAddressField(unique=True, protocol='both', null=True, blank=True)
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True)
    class Meta:
        managed = True
        db_table = 'ats'
        unique_together = (('name', 'subnet'),)

    def __str__(self):
        return self.name

    def contains_ip(self, address):
        """
        Check if the given IP address falls within the subnet range of this branch.
        """
        if self.subnet and address:
            try:
                subnet = IPv4Network(self.subnet)
                return ip_address(address) in subnet
            except ValueError:
                # Invalid subnet or IP address
                return False
        return False



class Vendor(models.Model):
    name = models.CharField(max_length=200)
    
    class Meta:
        managed = True
        db_table = 'vendor'


    def __str__(self):
        return self.name

class SwitchModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    device_model = models.CharField(max_length=200)

    # Legacy per-model OID config (kept for fallback collectors)
    rx_oid = models.CharField(max_length=200, null=True, blank=True)
    tx_oid = models.CharField(max_length=200, null=True, blank=True)
    part_num_oid = models.CharField(max_length=200, null=True, blank=True)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)
    port_num_oid = models.CharField(max_length=200, null=True, blank=True)
    max_ports_oid = models.CharField(max_length=200, null=True, blank=True)
    description_oid = models.CharField(max_length=200, null=True, blank=True)
    speed_oid = models.CharField(max_length=200, null=True, blank=True)
    duplex_oid = models.CharField(max_length=200, null=True, blank=True)
    admin_state_oid = models.CharField(max_length=200, null=True, blank=True)
    oper_state_oid = models.CharField(max_length=200, null=True, blank=True)

    # Capabilities-driven SNMP config for MIB-based collectors (update_optical_info_mib)
    required_mibs = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Comma-separated list of MIB modules to load (e.g. 'ENTITY-MIB,ENTITY-SENSOR-MIB')",
    )

    DDM_INDEX_IFINDEX = 'ifIndex'
    DDM_INDEX_ENTPHYSICAL = 'entPhysicalIndex'
    DDM_INDEX_CHOICES = (
        (DDM_INDEX_IFINDEX, 'ifIndex'),
        (DDM_INDEX_ENTPHYSICAL, 'entPhysicalIndex'),
    )
    ddm_index_type = models.CharField(
        max_length=32,
        choices=DDM_INDEX_CHOICES,
        default=DDM_INDEX_ENTPHYSICAL,
        help_text='Index type to use for DDM polling.',
    )

    # Symbolic MIB objects in form 'MODULE::objectName'
    rx_power_object = models.CharField(max_length=200, null=True, blank=True)
    tx_power_object = models.CharField(max_length=200, null=True, blank=True)
    temperature_object = models.CharField(max_length=200, null=True, blank=True)
    voltage_object = models.CharField(max_length=200, null=True, blank=True)
    sfp_vendor_object = models.CharField(max_length=200, null=True, blank=True)
    part_num_object = models.CharField(max_length=200, null=True, blank=True)
    serial_num_object = models.CharField(max_length=200, null=True, blank=True)

    # Unit hints for parsers
    POWER_UNIT_DBM = 'dbm'
    POWER_UNIT_MW = 'mw'
    POWER_UNIT_AUTO = 'auto'
    POWER_UNIT_SCALED_DBM_100 = 'scaled_dbm_100'
    POWER_UNIT_SCALED_MW_1000 = 'scaled_mw_1000'
    POWER_UNIT_SCALED_MW_10 = 'scaled_mw_10'
    POWER_UNIT_CHOICES = (
        (POWER_UNIT_AUTO, 'auto'),
        (POWER_UNIT_DBM, 'dBm'),
        (POWER_UNIT_MW, 'mW'),
        (POWER_UNIT_SCALED_DBM_100, 'scaled dBm/100'),
        (POWER_UNIT_SCALED_MW_1000, 'scaled mW/1000 (uW)'),
        (POWER_UNIT_SCALED_MW_10, 'scaled mW/10'),
    )
    power_unit = models.CharField(max_length=32, choices=POWER_UNIT_CHOICES, default=POWER_UNIT_AUTO)

    TEMP_UNIT_CELSIUS = 'celsius'
    TEMP_UNIT_AUTO = 'auto'
    TEMP_UNIT_SCALED_CELSIUS_100 = 'scaled_celsius_100'
    TEMP_UNIT_CHOICES = (
        (TEMP_UNIT_AUTO, 'auto'),
        (TEMP_UNIT_CELSIUS, 'Celsius'),
        (TEMP_UNIT_SCALED_CELSIUS_100, 'scaled Celsius/100'),
    )
    temperature_unit = models.CharField(max_length=32, choices=TEMP_UNIT_CHOICES, default=TEMP_UNIT_AUTO)
    
    class Meta:
        managed = True
        db_table = 'switch_model'
        unique_together = (('vendor', 'device_model'),)
    
    
    def __str__(self):
        return self.device_model


class Switch(models.Model):
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    model = models.ForeignKey(SwitchModel, on_delete=models.SET_NULL, blank=True, null=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    last_update = models.DateTimeField(auto_now=True, null=True, blank=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    switch_mac = models.CharField(unique=True, max_length=17, null=True, blank=True)
    snmp_community_ro = models.CharField(max_length=20, default='eriwpirt', null=True, blank=True)
    snmp_community_rw = models.CharField(max_length=20, default='netman', null=True, blank=True)
    status = models.BooleanField(default=False, null=True, blank=True)
    neighbor = models.ForeignKey("SwitchesNeighbors", on_delete=models.SET_NULL, blank=True, null=True)
    port = models.ForeignKey("SwitchesPorts", on_delete=models.SET_NULL, blank=True, null=True, related_name='switch_ports')
    branch = models.ForeignKey("Branch", on_delete=models.SET_NULL, blank=True, null=True)
    ats = models.ForeignKey('Ats', on_delete=models.SET_NULL, null=True)
    soft_version = models.CharField(max_length=80, blank=True, null=True)
    serial_number = models.CharField(unique=True, max_length=100, null=True, blank=True)
    rx_signal = models.FloatField(null=True, blank=True)
    tx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=50, null=True, blank=True)
    part_number = models.CharField(max_length=50, null=True, blank=True)
    history = HistoricalRecords()

    
    class Meta:
        managed = True
        db_table = 'switches'
        unique_together = (('hostname', 'ip'),)
        indexes = [
            models.Index(fields=['status', 'hostname', 'ip', 'rx_signal', 'tx_signal']),
        ]
    
    def save(self, *args, **kwargs):
        self.last_update = timezone.now()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.hostname
    
    
class SwitchStatus(models.Model):
    switch = models.OneToOneField('Switch', on_delete=models.CASCADE, related_name='status_record')
    is_up = models.BooleanField(default=False)
    uptime = models.CharField(max_length=200, null=True, blank=True)
    last_poll_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'switch_status'


class Interface(models.Model):
    switch = models.ForeignKey('Switch', on_delete=models.CASCADE, related_name='interfaces')
    ifindex = models.PositiveIntegerField()

    name = models.CharField(max_length=64, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    alias = models.CharField(max_length=255, null=True, blank=True)

    iftype = models.PositiveIntegerField(null=True, blank=True)
    speed = models.BigIntegerField(null=True, blank=True)
    duplex = models.SmallIntegerField(null=True, blank=True)
    admin = models.SmallIntegerField(null=True, blank=True)
    oper = models.SmallIntegerField(null=True, blank=True)
    lastchange = models.BigIntegerField(null=True, blank=True)

    discards_in = models.BigIntegerField(null=True, blank=True)
    discards_out = models.BigIntegerField(null=True, blank=True)

    polled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interfaces'
        unique_together = (('switch', 'ifindex'),)
        indexes = [
            models.Index(fields=['switch', 'ifindex']),
        ]


class InterfaceOptics(models.Model):
    interface = models.OneToOneField('Interface', on_delete=models.CASCADE, related_name='optics')
    rx_dbm = models.FloatField(null=True, blank=True)
    tx_dbm = models.FloatField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    voltage_v = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=100, null=True, blank=True)
    part_number = models.CharField(max_length=100, null=True, blank=True)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    polled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interface_optics'


class InterfaceL2(models.Model):
    interface = models.OneToOneField('Interface', on_delete=models.CASCADE, related_name='l2')
    mac_count = models.PositiveIntegerField(null=True, blank=True)
    pvid = models.PositiveIntegerField(null=True, blank=True)
    tagged_vlans = models.CharField(max_length=2000, null=True, blank=True)
    untagged_vlans = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interface_l2'


class MacEntry(models.Model):
    switch = models.ForeignKey('Switch', on_delete=models.CASCADE, related_name='mac_entries')
    interface = models.ForeignKey('Interface', on_delete=models.SET_NULL, null=True, blank=True, related_name='mac_entries')
    mac = models.CharField(max_length=17)
    vlan = models.PositiveIntegerField()
    ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'mac_entries'
        unique_together = (('switch', 'mac', 'vlan'),)
        indexes = [
            models.Index(fields=['mac']),
            models.Index(fields=['switch', 'interface']),
        ]


class NeighborLink(models.Model):
    local_switch = models.ForeignKey('Switch', on_delete=models.CASCADE, related_name='neighbor_links')
    local_interface = models.ForeignKey('Interface', on_delete=models.SET_NULL, null=True, blank=True, related_name='neighbor_links')
    remote_mac = models.CharField(max_length=17)
    remote_port = models.CharField(max_length=64, null=True, blank=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'neighbor_links'
        indexes = [
            models.Index(fields=['local_switch']),
            models.Index(fields=['remote_mac']),
        ]


# Legacy model kept temporarily for data migration; will be removed in cleanup migration.
class SwitchesPorts(models.Model):
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID', default=1)
    switch = models.ForeignKey(Switch, models.DO_NOTHING, blank=False, null=False, default=0, related_name='switch_ports_reverse')
    port = models.SmallIntegerField(blank=False)
    description = models.CharField(max_length=200, default='')
    speed = models.IntegerField()
    duplex = models.SmallIntegerField()
    admin = models.SmallIntegerField()
    oper = models.SmallIntegerField()
    lastchange = models.BigIntegerField()
    discards_in = models.BigIntegerField()
    discards_out = models.BigIntegerField()
    mac_count = models.SmallIntegerField()
    pvid = models.SmallIntegerField()
    port_tagged = models.CharField(max_length=2000)
    port_untagged = models.CharField(max_length=80)
    data = models.DateTimeField()
    name = models.CharField(max_length=30)
    alias = models.CharField(max_length=80)
    oct_in = models.BigIntegerField()
    oct_out = models.BigIntegerField()
    rx_signal = models.FloatField(null=True, blank=True)
    tx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=50, null=True, blank=True)
    part_number = models.CharField(max_length=50, null=True, blank=True)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    mac_on_port = models.ForeignKey("Mac", models.DO_NOTHING, blank=False, null=False, default=0)
    
    class Meta:
        managed = True
        db_table = 'switches_ports'
        unique_together = (('switch', 'port'),)
        
class InterfaceCounterState(models.Model):
    """Stores last counter values to compute bandwidth deltas."""

    # Legacy addressing (will be removed after data migration)
    switch = models.ForeignKey('Switch', on_delete=models.CASCADE)
    ifindex = models.PositiveIntegerField()

    # New normalized FK
    interface = models.OneToOneField('Interface', on_delete=models.CASCADE, related_name='counter_state', null=True, blank=True)

    last_in_octets = models.BigIntegerField(default=0)
    last_out_octets = models.BigIntegerField(default=0)
    last_ts = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interface_counter_state'
        unique_together = (('switch', 'ifindex'),)


class InterfaceBandwidthSample(models.Model):
    """Bandwidth sample computed from SNMP counters (bps)."""

    # Legacy addressing (will be removed after data migration)
    switch = models.ForeignKey('Switch', on_delete=models.CASCADE)
    ifindex = models.PositiveIntegerField()

    # New normalized FK
    interface = models.ForeignKey('Interface', on_delete=models.CASCADE, related_name='bandwidth_samples', null=True, blank=True)

    ts = models.DateTimeField(db_index=True)
    in_bps = models.BigIntegerField(null=True, blank=True)
    out_bps = models.BigIntegerField(null=True, blank=True)
    interval_sec = models.PositiveIntegerField(null=True, blank=True)
    in_octets = models.BigIntegerField(null=True, blank=True)
    out_octets = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interface_bandwidth_sample'
        indexes = [
            models.Index(fields=['switch', 'ifindex', 'ts']),
            models.Index(fields=['interface', 'ts']),
        ]


class SwitchesNeighbors(models.Model):
    mac1 = models.CharField(max_length=17)
    port1 = models.SmallIntegerField()
    mac2 = models.CharField(max_length=17)
    port2 = models.SmallIntegerField()

    class Meta:
        managed = True
        db_table = 'switches_neighbors'
        unique_together = (('mac1', 'port1', 'mac2'),)

class Mac(models.Model):
    switch = models.ForeignKey('Switch', models.DO_NOTHING, blank=False, null=False, default=0)
    mac = models.CharField(max_length=17, default='', blank=False, null=False)
    port = models.ForeignKey("SwitchesPorts", models.DO_NOTHING, blank=False, null=False, default=0)
    vlan = models.SmallIntegerField()
    ip =  models.GenericIPAddressField(protocol='both', null=True, blank=True)
    data = models.DateTimeField(auto_now_add=True, blank=False)

    class Meta:
        managed = True
        db_table = 'mac'
        unique_together = (('switch', 'mac', 'vlan'),)

class ListMacHistory(models.Model):
    """
    Read-only class. The mat_listMacHistory is a materialized view to speed up searches upon mac history
    """
    switch = models.ForeignKey('Switch', models.DO_NOTHING, blank=False, null=False, default=0, related_name='hist_switch')
    mac = models.CharField(max_length=17, default='', blank=False, null=False)
    port = models.SmallIntegerField()
    vlan = models.SmallIntegerField()
    ip = models.CharField(max_length=15, blank=True, null=True)
    data = models.DateTimeField(primary_key=True)

    def save(self, *args, **kwargs):
        return

    def delete(self, *args, **kwargs):
        return

    class Meta:
        managed = False
        db_table = 'mat_listmachistory'

