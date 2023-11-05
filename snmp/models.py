from django.db import models

class Vendor(models.Model):
    vendor = models.CharField(max_length=200)

    def __str__(self):
        return self.vendor

class DeviceModel(models.Model):
    deviceModel = models.CharField(max_length=200)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.deviceModel

class Device(models.Model):
    DEVICE_CHOICES = [
        ('Switch', 'Switch'),
        ('Olt', 'Olt'),
    ]
    deviceType = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    deviceModel = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.deviceType

class Switch(models.Model):
    DeviceType = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    deviceModel = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip_addr = models.GenericIPAddressField(null=False)
    uptime = models.DurationField(null=True, blank=True)
    sysinfo = models.CharField(max_length=300, null=True, blank=True)
    snmp_community = models.CharField(default='snmp2netread', max_length=200)
    created_time = models.DateTimeField(auto_now=True)
    oid = models.CharField(max_length=300, default='1.3.6.1.2.1.1.1.0')

    def __str__(self):
        return self.hostname


class Olt(models.Model):
    DeviceType = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    deviceModel = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip_addr = models.GenericIPAddressField(null=False)
    uptime = models.DurationField(null=True, blank=True)
    sysinfo = models.CharField(max_length=300, null=True, blank=True)
    snmp_community = models.CharField(default='snmp2netread', max_length=200)
    created_time = models.DateTimeField(auto_now=True)
    oid = models.CharField(max_length=300, default='1.3.6.1.2.1.1.1.0')

    def __str__(self):
        return self.hostname
