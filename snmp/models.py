from django.db import models

class Vendor(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class SwitchModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    device_model = models.CharField(max_length=200)
    
    def __str__(self):
        return self.device_model


class OltModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    device_model = models.CharField(max_length=200)
    
    def __str__(self):
        return self.device_model


class Device(models.Model):
    DEVICE_CHOICES = [
        ('Switch', 'Switch'),
        ('Olt', 'Olt'),
    ]
    device_type = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    device_model = models.ForeignKey(SwitchModel, on_delete=models.SET_NULL, null=True, blank=True)
    device_model_olt = models.ForeignKey(OltModel, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.device_type


class Switch(models.Model):
    device_type = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    device_model = models.ForeignKey(SwitchModel, on_delete=models.SET_NULL, null=True, blank=True)
    device_hostname = models.CharField(max_length=200, null=True, blank=True)
    device_ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    device_optical_info = models.IntegerField(null=True, blank=True)
    device_snmp_community = models.CharField(max_length=100, default='snmp2netread')
    device_general_oid = models.CharField(max_length=200, default='1.3.6.1.2.1.1.1.0')

    def __str__(self):
        return self.device_model


class Olt(models.Model):
    device_type = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True)
    device_model = models.ForeignKey(OltModel, on_delete=models.SET_NULL, null=True, blank=True)
    device_hostname = models.CharField(max_length=200, null=True, blank=True)
    device_ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    device_optical_info = models.IntegerField(null=True)
    device_snmp_community = models.CharField(max_length=100, default='snmp2netread')
    device_general_oid = models.CharField(max_length=200, default='1.3.6.1.2.1.1.1.0')
        
    def __str__(self):
        return self.device_ip
