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
    # This function creates custom permissions for each branch after migration

    # Get the content type for the Branch model
    content_type = ContentType.objects.get_for_model(Branch)

    # Define the branches for which you want to create permissions
    branches = Branch.objects.all()

    # Create a permission for each branch
    for branch in branches:
        codename = f'view_{branch.name.lower().replace(" ", "_")}'
        name = f'Can view switches in {branch.name}'
        permission, created = Permission.objects.get_or_create(
            codename=codename,
            name=name,
            content_type=content_type,
        )

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

    switch = models.ForeignKey('Switch', on_delete=models.CASCADE)
    ifindex = models.PositiveIntegerField()
    last_in_octets = models.BigIntegerField(default=0)
    last_out_octets = models.BigIntegerField(default=0)
    last_ts = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'interface_counter_state'
        unique_together = (('switch', 'ifindex'),)


class InterfaceBandwidthSample(models.Model):
    """Bandwidth sample computed from SNMP counters (bps)."""

    switch = models.ForeignKey('Switch', on_delete=models.CASCADE)
    ifindex = models.PositiveIntegerField()
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

