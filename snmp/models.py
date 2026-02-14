from django.db import models
from simple_history.models import HistoricalRecords
from django.utils import timezone
from django.conf import settings
from ipaddress import ip_address, IPv4Network
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.db.models import Q

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
    snmp_community_ro = models.CharField(max_length=20, default=settings.SNMP_DEFAULT_COMMUNITY_RO, null=True, blank=True)
    snmp_community_rw = models.CharField(max_length=20, default=settings.SNMP_DEFAULT_COMMUNITY_RW, null=True, blank=True)
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
    mac_on_port = models.ForeignKey("Mac", models.DO_NOTHING, blank=False, null=False, default=0)
    
    class Meta:
        managed = True
        db_table = 'switches_ports'
        unique_together = (('switch', 'port'),)
        
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


class DeviceProfile(models.Model):
    vendor = models.CharField(max_length=120)
    model_pattern = models.CharField(max_length=255)
    firmware_pattern = models.CharField(max_length=255, blank=True, default="")
    priority = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        managed = True
        db_table = 'device_profile'
        indexes = [
            models.Index(fields=['active', 'priority']),
            models.Index(fields=['vendor']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['vendor', 'model_pattern', 'firmware_pattern'],
                name='uq_device_profile_vendor_model_fw',
            ),
        ]

    def __str__(self):
        return f"{self.vendor}::{self.model_pattern}"


class MetricDefinition(models.Model):
    class ValueType(models.TextChoices):
        FLOAT = 'float', 'Float'
        INTEGER = 'int', 'Integer'
        BOOLEAN = 'bool', 'Boolean'
        TEXT = 'text', 'Text'
        ENUM = 'enum', 'Enum'

    key = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    unit = models.CharField(max_length=32, blank=True, default="")
    value_type = models.CharField(max_length=10, choices=ValueType.choices, default=ValueType.FLOAT)
    default_interval_sec = models.PositiveIntegerField(default=300)

    class Meta:
        managed = True
        db_table = 'metric_definition'
        indexes = [
            models.Index(fields=['key']),
        ]

    def __str__(self):
        return self.key


class Device(models.Model):
    class SnmpVersion(models.TextChoices):
        V1 = '1', 'SNMPv1'
        V2C = '2c', 'SNMPv2c'
        V3 = '3', 'SNMPv3'

    switch = models.OneToOneField(
        'Switch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='device',
    )
    ip = models.GenericIPAddressField(protocol='both', unique=True)
    hostname = models.CharField(max_length=200, blank=True, default="")
    vendor = models.CharField(max_length=120, blank=True, default="")
    model = models.CharField(max_length=160, blank=True, default="")
    firmware = models.CharField(max_length=160, blank=True, default="")
    sys_object_id = models.CharField(max_length=180, blank=True, default="")
    snmp_version = models.CharField(max_length=4, choices=SnmpVersion.choices, default=SnmpVersion.V2C)
    auth_profile = models.CharField(max_length=120, blank=True, default="")
    status = models.BooleanField(default=False)
    profile = models.ForeignKey('DeviceProfile', on_delete=models.SET_NULL, null=True, blank=True)
    last_discovered_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'device'
        indexes = [
            models.Index(fields=['vendor', 'model']),
            models.Index(fields=['status', 'updated']),
        ]

    def __str__(self):
        return self.hostname or str(self.ip)


class MetricBinding(models.Model):
    class IndexStrategy(models.TextChoices):
        IF_INDEX = 'if_index', 'IfIndex'
        FIXED = 'fixed', 'Fixed'
        VENDOR_MAP = 'vendor_map', 'Vendor Map'

    class Converter(models.TextChoices):
        IDENTITY = 'identity', 'Identity'
        DIV100 = 'div100', 'Divide by 100'
        DIV1000 = 'div1000', 'Divide by 1000'
        MW_TO_DBM = 'mw_to_dbm', 'mW to dBm'
        ENUM_MAP = 'enum_map', 'Enum map'

    profile = models.ForeignKey('DeviceProfile', on_delete=models.CASCADE, related_name='metric_bindings')
    metric = models.ForeignKey('MetricDefinition', on_delete=models.CASCADE, related_name='bindings')
    oid_template = models.CharField(max_length=255)
    index_strategy = models.CharField(max_length=20, choices=IndexStrategy.choices, default=IndexStrategy.IF_INDEX)
    converter = models.CharField(max_length=20, choices=Converter.choices, default=Converter.IDENTITY)
    binding_params = models.JSONField(default=dict, blank=True)
    scale = models.FloatField(default=1.0)
    enabled_by_default = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)

    class Meta:
        managed = True
        db_table = 'metric_binding'
        indexes = [
            models.Index(fields=['profile', 'enabled_by_default']),
            models.Index(fields=['metric', 'priority']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'metric', 'oid_template', 'index_strategy'],
                name='uq_metric_binding_profile_metric_oid_index',
            ),
        ]

    def __str__(self):
        return f"{self.profile}::{self.metric.key}"


class Interface(models.Model):
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='interfaces')
    if_index = models.PositiveIntegerField()
    if_name = models.CharField(max_length=128, blank=True, default="")
    if_alias = models.CharField(max_length=255, blank=True, default="")
    if_type = models.CharField(max_length=80, blank=True, default="")
    is_optical = models.BooleanField(default=False)
    admin_up = models.BooleanField(null=True, blank=True)
    oper_up = models.BooleanField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'device_interface'
        indexes = [
            models.Index(fields=['device', 'is_optical']),
            models.Index(fields=['device', 'if_index']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['device', 'if_index'], name='uq_interface_device_ifindex'),
        ]

    def __str__(self):
        return f"{self.device}:{self.if_index}"


class MetricSubscription(models.Model):
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='subscriptions')
    interface = models.ForeignKey('Interface', on_delete=models.CASCADE, null=True, blank=True, related_name='subscriptions')
    metric = models.ForeignKey('MetricDefinition', on_delete=models.CASCADE, related_name='subscriptions')
    binding = models.ForeignKey('MetricBinding', on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    enabled = models.BooleanField(default=True)
    warn_threshold = models.FloatField(null=True, blank=True)
    crit_threshold = models.FloatField(null=True, blank=True)
    poll_interval_sec = models.PositiveIntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'metric_subscription'
        indexes = [
            models.Index(fields=['device', 'enabled']),
            models.Index(fields=['metric', 'enabled']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'metric'],
                condition=Q(interface__isnull=True),
                name='uq_subscription_device_metric_no_interface',
            ),
            models.UniqueConstraint(
                fields=['interface', 'metric'],
                condition=Q(interface__isnull=False),
                name='uq_subscription_interface_metric',
            ),
        ]

    def __str__(self):
        if self.interface_id:
            return f"{self.device}:{self.interface.if_index}:{self.metric.key}"
        return f"{self.device}:{self.metric.key}"


class MetricSample(models.Model):
    class Quality(models.TextChoices):
        GOOD = 'good', 'Good'
        BAD = 'bad', 'Bad'
        UNKNOWN = 'unknown', 'Unknown'

    subscription = models.ForeignKey('MetricSubscription', on_delete=models.CASCADE, related_name='samples')
    ts = models.DateTimeField(default=timezone.now, db_index=True)
    value_float = models.FloatField(null=True, blank=True)
    value_text = models.TextField(blank=True, default="")
    quality = models.CharField(max_length=10, choices=Quality.choices, default=Quality.UNKNOWN)
    raw_value = models.TextField(blank=True, default="")

    class Meta:
        managed = True
        db_table = 'metric_sample'
        indexes = [
            models.Index(fields=['subscription', 'ts']),
            models.Index(fields=['quality', 'ts']),
        ]

    def __str__(self):
        return f"{self.subscription_id}@{self.ts}"


class AlertRule(models.Model):
    class Severity(models.TextChoices):
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    class Direction(models.TextChoices):
        LOWER_IS_WORSE = 'lower_is_worse', 'Lower is worse'
        HIGHER_IS_WORSE = 'higher_is_worse', 'Higher is worse'

    name = models.CharField(max_length=120)
    metric = models.ForeignKey('MetricDefinition', on_delete=models.CASCADE, related_name='alert_rules')
    device = models.ForeignKey('Device', on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    profile = models.ForeignKey('DeviceProfile', on_delete=models.CASCADE, null=True, blank=True, related_name='alert_rules')
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING)
    direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.LOWER_IS_WORSE)
    threshold = models.FloatField()
    hysteresis = models.FloatField(default=0.0)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'alert_rule'
        indexes = [
            models.Index(fields=['active', 'severity']),
            models.Index(fields=['metric', 'active']),
        ]

    def __str__(self):
        return f'{self.name}:{self.metric.key}:{self.severity}'


class AlertEvent(models.Model):
    class State(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    subscription = models.ForeignKey('MetricSubscription', on_delete=models.CASCADE, related_name='alert_events')
    rule = models.ForeignKey('AlertRule', on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    severity = models.CharField(max_length=10, choices=AlertRule.Severity.choices)
    state = models.CharField(max_length=10, choices=State.choices, default=State.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_value = models.FloatField(null=True, blank=True)
    message = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        managed = True
        db_table = 'alert_event'
        indexes = [
            models.Index(fields=['state', 'severity']),
            models.Index(fields=['subscription', 'state']),
        ]

    def __str__(self):
        return f'{self.subscription_id}:{self.severity}:{self.state}'
