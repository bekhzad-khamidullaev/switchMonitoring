from django.db import models
from django.utils import timezone


class Vendor(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self) -> str:
        return self.name


class DeviceModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='models')
    name = models.CharField(max_length=64)
    sys_object_id = models.CharField(max_length=64, unique=True)
    max_ports = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("vendor", "name")

    def __str__(self) -> str:
        return f"{self.vendor} {self.name}"


class Device(models.Model):
    hostname = models.CharField(max_length=128, blank=True)
    ip = models.GenericIPAddressField(unique=True)
    community = models.CharField(max_length=64, default='public')
    model = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True, blank=True)
    last_polled = models.DateTimeField(null=True, blank=True)
    status = models.BooleanField(default=False)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('device_detail', args=[str(self.pk)])

    def __str__(self) -> str:
        return self.hostname or str(self.ip)


class Interface(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='interfaces')
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=128, blank=True)
    admin_status = models.BooleanField(default=False)
    oper_status = models.BooleanField(default=False)
    speed = models.BigIntegerField(null=True, blank=True)
    rx_power = models.FloatField(null=True, blank=True)
    tx_power = models.FloatField(null=True, blank=True)
    vlan = models.CharField(max_length=64, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    errors_in = models.PositiveBigIntegerField(null=True, blank=True)
    errors_out = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("device", "index")

    def __str__(self) -> str:
        return f"{self.device} port {self.index}"
