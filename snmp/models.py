from django.db import models
from simple_history.models import HistoricalRecords



class Vendor(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

class SwitchModel(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    device_model = models.CharField(max_length=200)
    rx_oid = models.CharField(max_length=200, null=True, blank=True)
    tx_oid = models.CharField(max_length=200, null=True, blank=True)
    part_num_oid = models.CharField(max_length=200, null=True, blank=True)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)
    
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
    device_model = models.ForeignKey(SwitchModel, on_delete=models.SET_NULL, blank=True, null=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    device_hostname = models.CharField(max_length=200, null=True, blank=True)
    device_ip = models.GenericIPAddressField(unique=True, protocol='both', null=True, blank=True)
    device_snmp_community = models.CharField(max_length=100, default='snmp2netread')
    sysdescr_oid = models.CharField(max_length=200, default='1.3.6.1.2.1.1.1.0')
    status = models.BooleanField(default=False, null=True, blank=True)
    uplink = models.ForeignKey("Switch", on_delete=models.SET_NULL, blank=True, null=True)
    tx_signal = models.FloatField(null=True, blank=True)
    rx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)
    part_number = models.CharField(max_length=200, null=True, blank=True)
    ats = models.CharField(max_length=200, null=True, blank=True)
    high_signal_value = models.FloatField(default='11')
    history = HistoricalRecords() 

    def __str__(self):
        return f"{self.device_hostname}"


class Olt(models.Model):
    device_model_local = models.CharField(max_length=200, null=True, blank=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    device_hostname = models.CharField(max_length=200, null=True, blank=True)
    device_ip = models.GenericIPAddressField(unique=True, protocol='both', null=True, blank=True)
    device_snmp_community = models.CharField(max_length=100, default='snmp2netread')
    sysdescr_oid = models.CharField(max_length=200, default='1.3.6.1.2.1.1.1.0')
    status = models.BooleanField(default=False, null=True, blank=True)
    uplink = models.IntegerField(blank=True, null=True)
    history = HistoricalRecords() 
    tx_signal = models.FloatField(null=True, blank=True)
    rx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)
    part_number = models.CharField(max_length=200, null=True, blank=True)
    ats = models.CharField(max_length=200, null=True, blank=True)
    high_signal_value = models.FloatField(default='11')

    def __str__(self):
        return f"{self.device_hostname}"
