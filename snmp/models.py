from functools import cached_property
from ipaddress import IPv4Network, ip_address

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Coalesce, Lower, Trim
from django.db.models.signals import post_migrate, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from simple_history.models import HistoricalRecords


def _is_unknown_text(value: str) -> bool:
    return (value or '').strip().lower() in {'', 'unknown', 'n/a', 'na', '-', 'none', 'null'}


class DeviceQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=True)

    def with_group(self, group_id):
        return self.filter(group_id=group_id)

    def with_branch(self, group_id):
        return self.with_group(group_id)


class DeviceManager(models.Manager.from_queryset(DeviceQuerySet)):
    pass


def _branch_permission_codename(branch_name):
    if not branch_name:
        return None
    return f'view_{branch_name.lower().replace(" ", "_")}'


def _group_permission_codename(group_name):
    return _branch_permission_codename(group_name)



class Branch(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class Meta:
        managed = True
        db_table = 'branch'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('name')),
                Coalesce('parent_id', models.Value(0)),
                condition=Q(name__isnull=False),
                name='uq_branch_parent_norm_name',
            ),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name



def _sync_branch_permission(branch):
    codename = _branch_permission_codename(branch.name)
    if not codename:
        return
    content_type = ContentType.objects.get_for_model(Branch)
    Permission.objects.update_or_create(
        codename=codename,
        content_type=content_type,
        defaults={
            'name': f'Can view devices in {branch.name}',
        },
    )


def _delete_branch_permission(branch_name):
    codename = _branch_permission_codename(branch_name)
    if not codename:
        return
    content_type = ContentType.objects.get_for_model(Branch)
    Permission.objects.filter(codename=codename, content_type=content_type).delete()


@receiver(post_migrate)
def create_branch_permissions(sender, **kwargs):
    active_codenames = set()
    for branch in Branch.objects.all():
        _sync_branch_permission(branch)
        codename = _branch_permission_codename(branch.name)
        if codename:
            active_codenames.add(codename)

    content_type = ContentType.objects.get_for_model(Branch)
    stale_permissions = Permission.objects.filter(content_type=content_type, codename__startswith='view_')
    stale_permissions = stale_permissions.exclude(codename__in=active_codenames)
    stale_permissions.delete()


@receiver(pre_save, sender=Branch)
def capture_previous_branch_name(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_name = None
        return
    previous = sender.objects.filter(pk=instance.pk).values_list('name', flat=True).first()
    instance._previous_name = previous


@receiver(post_save, sender=Branch)
def create_branch_permission_on_save(sender, instance, **kwargs):
    previous_name = getattr(instance, '_previous_name', None)
    _sync_branch_permission(instance)
    if previous_name and previous_name != instance.name:
        still_used = sender.objects.exclude(pk=instance.pk).filter(name=previous_name).exists()
        if not still_used:
            _delete_branch_permission(previous_name)

class Ats(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    subnet = models.CharField(max_length=45, unique=True, null=True, blank=True, help_text="e.g. 192.168.1.0/24")
    group = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, verbose_name="Group"
    )
    class Meta:
        managed = True
        db_table = 'ats'
        verbose_name = 'Subgroup'
        verbose_name_plural = 'Subgroups'
        unique_together = (('name', 'subnet'),)
        constraints = [
            models.UniqueConstraint(
                Lower(Trim('name')),
                Coalesce('group_id', models.Value(0)),
                condition=Q(name__isnull=False),
                name='uq_ats_group_norm_name',
            ),
        ]

    def __str__(self):
        return self.name

    @cached_property
    def network(self):
        if not self.subnet:
            return None
        try:
            return IPv4Network(self.subnet)
        except ValueError:
            return None

    def contains_ip(self, address):
        """
        Check if the given IP address falls within the subnet range of this branch.
        """
        nw = self.network
        if nw and address:
            try:
                return ip_address(address) in nw
            except ValueError:
                return False
        return False

    @property
    def branch(self):
        return self.group

    @branch.setter
    def branch(self, value):
        self.group = value






class Vendor(models.Model):
    name = models.CharField(max_length=200)

    class Meta:
        managed = True
        db_table = 'vendor'


    def __str__(self):
        return self.name

class DeviceModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    device_model = models.CharField(max_length=200)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        managed = True
        db_table = 'device_type'
        unique_together = (('vendor', 'device_model'),)


    def __str__(self):
        return self.device_model





class DevicePort(models.Model):
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID', default=1)
    managed_device = models.ForeignKey('Device', models.DO_NOTHING, blank=False, null=False, default=0, related_name='switch_ports_reverse')
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

    class Meta:
        managed = True
        db_table = 'device_ports'
        unique_together = (('managed_device', 'port'),)

class DeviceNeighbor(models.Model):
    mac1 = models.CharField(max_length=17)
    port1 = models.SmallIntegerField()
    mac2 = models.CharField(max_length=17)
    port2 = models.SmallIntegerField()

    class Meta:
        managed = True
        db_table = 'device_neighbors'
        unique_together = (('mac1', 'port1', 'mac2'),)

class Mac(models.Model):
    managed_device = models.ForeignKey('Device', models.DO_NOTHING, blank=False, null=False, default=0)
    mac = models.CharField(max_length=17, default='', blank=False, null=False)
    port = models.ForeignKey("DevicePort", models.DO_NOTHING, blank=False, null=False, default=0)
    vlan = models.SmallIntegerField()
    ip =  models.GenericIPAddressField(protocol='both', null=True, blank=True)
    data = models.DateTimeField(auto_now_add=True, blank=False)

    class Meta:
        managed = True
        db_table = 'mac'
        unique_together = (('managed_device', 'mac', 'vlan'),)

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

    ip = models.GenericIPAddressField(protocol='both', unique=True)
    hostname = models.CharField(max_length=200, blank=True, default="")
    vendor = models.CharField(max_length=120, blank=True, default="")
    model = models.CharField(max_length=160, blank=True, default="")
    firmware = models.CharField(max_length=160, blank=True, default="")
    sys_object_id = models.CharField(max_length=180, blank=True, default="")
    snmp_version = models.CharField(max_length=4, choices=SnmpVersion.choices, default=SnmpVersion.V2C)
    auth_profile = models.CharField(max_length=120, blank=True, default="")
    status = models.BooleanField(default=False)

    # Legacy Device integration fields
    device_type = models.ForeignKey('DeviceModel', on_delete=models.SET_NULL, blank=True, null=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    switch_mac = models.CharField(unique=True, max_length=17, null=True, blank=True)
    snmp_community_ro = models.CharField(max_length=100, null=True, blank=True)
    snmp_community_rw = models.CharField(max_length=100, null=True, blank=True)
    neighbor = models.ForeignKey("DeviceNeighbor", on_delete=models.SET_NULL, blank=True, null=True)
    parent_port = models.ForeignKey("DevicePort", on_delete=models.SET_NULL, blank=True, null=True, related_name='parent_devices')
    group = models.ForeignKey("Branch", on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Group')
    subgroup = models.ForeignKey('Ats', on_delete=models.SET_NULL, null=True, verbose_name='Subgroup')
    soft_version = models.CharField(max_length=80, blank=True, null=True)
    serial_number = models.CharField(unique=True, max_length=100, null=True, blank=True)
    rx_signal = models.FloatField(null=True, blank=True)
    tx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=50, null=True, blank=True)
    part_number = models.CharField(max_length=50, null=True, blank=True)

    profile = models.ForeignKey('DeviceProfile', on_delete=models.SET_NULL, null=True, blank=True)
    last_discovered_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        managed = True
        db_table = 'device'
        indexes = [
            models.Index(fields=['vendor', 'model']),
            models.Index(fields=['status', 'updated']),
            models.Index(fields=['ip', 'hostname']),
            models.Index(fields=['group', 'status', 'updated']),
            models.Index(fields=['profile', 'status']),
        ]

    def __str__(self):
        return self.hostname or str(self.ip)

    def effective_snmp_community(self):
        return self.snmp_community_ro or settings.SNMP_DEFAULT_COMMUNITY_RO

    @property
    def display_vendor(self):
        if not _is_unknown_text(self.vendor):
            return self.vendor
        if self.device_type_id and self.device_type and self.device_type.vendor:
            return self.device_type.vendor.name
        return ''

    @property
    def display_model(self):
        if not _is_unknown_text(self.model):
            return self.model
        if self.device_type_id and self.device_type:
            return self.device_type.device_model
        return ''

    @property
    def branch(self):
        return self.group

    @branch.setter
    def branch(self, value):
        self.group = value

    @property
    def ats(self):
        return self.subgroup

    @ats.setter
    def ats(self, value):
        self.subgroup = value


class MetricBinding(models.Model):
    class IndexStrategy(models.TextChoices):
        IF_INDEX = 'if_index', 'IfIndex'
        FIXED = 'fixed', 'Fixed'
        VENDOR_MAP = 'vendor_map', 'Vendor Map'

    class Converter(models.TextChoices):
        IDENTITY = 'identity', 'Identity'
        DIV10 = 'div10', 'Divide by 10'
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
    poll_interval_sec = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(86400)],
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'metric_subscription'
        indexes = [
            models.Index(fields=['device', 'enabled']),
            models.Index(fields=['metric', 'enabled']),
            models.Index(fields=['device', 'interface', 'enabled']),
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
            models.CheckConstraint(
                check=Q(poll_interval_sec__isnull=True) | Q(poll_interval_sec__gte=5),
                name='chk_subscription_poll_interval_gte_5',
            ),
        ]

    def __str__(self):
        if self.interface_id:
            return f"{self.device}:{self.interface.if_index}:{self.metric.key}"
        return f"{self.device}:{self.metric.key}"

    def threshold_direction(self) -> str:
        if not self.binding_id:
            return AlertRule.Direction.LOWER_IS_WORSE
        return self.binding.binding_params.get('threshold_direction', AlertRule.Direction.LOWER_IS_WORSE)

    def validate_thresholds(self, warn_value=None, crit_value=None):
        if warn_value is None or crit_value is None:
            return None
        direction = self.threshold_direction()
        if direction == AlertRule.Direction.HIGHER_IS_WORSE and crit_value < warn_value:
            return 'crit_threshold must be >= warn_threshold'
        if direction != AlertRule.Direction.HIGHER_IS_WORSE and crit_value > warn_value:
            return 'crit_threshold must be <= warn_threshold'
        return None


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
            models.Index(fields=['ts', 'id']),
            models.Index(fields=['subscription', 'quality', 'ts']),
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


# Universal naming aliases. Legacy names stay supported for compatibility.
# Universal naming aliases.
Device = Device
DeviceModel = DeviceModel
DevicePort = DevicePort
DeviceNeighbor = DeviceNeighbor
Group = Branch
SubGroup = Ats
