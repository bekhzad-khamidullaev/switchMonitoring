from django.db import models
from simple_history.models import HistoricalRecords


class Branch(models.Model):
    name = models.CharField(max_length=200, null=True, blank=True)
    subnet = models.GenericIPAddressField(unique=True, protocol='both', null=True, blank=True)

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


class Switch(models.Model):
    model = models.ForeignKey(SwitchModel, on_delete=models.SET_NULL, blank=True, null=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    snmp_community = models.CharField(max_length=100, default='snmp2netread')
    sysdescr_oid = models.CharField(max_length=200, default='1.3.6.1.2.1.1.1.0')
    status = models.BooleanField(default=False, null=True, blank=True)
    uplink = models.ForeignKey("Switch", on_delete=models.SET_NULL, blank=True, null=True)
    rx_signal = models.FloatField(null=True, blank=True)
    tx_signal = models.FloatField(null=True, blank=True)
    sfp_vendor = models.CharField(max_length=200, null=True, blank=True)
    part_number = models.CharField(max_length=200, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, blank=True, null=True)
    high_signal_value = models.FloatField(default='11', blank=True, null=True)
    history = HistoricalRecords() 

    def __str__(self):
        return self.device_hostname