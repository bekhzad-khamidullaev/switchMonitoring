from django.db import models
from django.contrib.auth.models import User
from pysnmp.hlapi import *
from background_task import background

@background(schedule=3600)  # Schedule the task to run every 3600 seconds
def schedule_optical_signal_check():
    from django.core import management
    management.call_command('optical_signal_check')



class Vendor(models.Model):
    vendor = models.CharField(max_length=200)
    
    def __str__(self):
        return self.vendor

class DeviceModel(models.Model):
    deviceModel = models.CharField(max_length=200)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return self.deviceModel
    
class Olt(models.Model):
    deviceModel = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip_addr = models.GenericIPAddressField(null=False)
    uptime = models.DurationField(null=True, blank=True)
    sysinfo = models.CharField(max_length=300, null=True, blank=True)
    snmp_community = models.CharField(default='public', max_length=200)
    # created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, default='auth.User')
    created_time = models.DateTimeField(auto_now=True)
    oid = models.CharField(max_length=300, default='1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4')

    def __str__(self):
        return self.hostname

    def get_optical_signal_status(self):
        # Create an SNMP query to get the value for the specified OID
        oid = self.oid
        community = self.snmp_community
        target_ip = self.ip_addr

        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((target_ip, 161)),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )

        if errorIndication:
            return f"Error: {errorIndication}"
        elif errorStatus:
            return f"Error: {errorStatus.prettyPrint()}"
        else:
            for varBind in varBinds:
                return varBind[-1].prettyPrint()

        return "Optical signal status not available"

class Switch(models.Model):
    deviceModel = models.ForeignKey(DeviceModel, on_delete=models.SET_NULL, null=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    ip_addr = models.GenericIPAddressField(null=False)
    uptime = models.DurationField(null=True, blank=True)
    sysinfo = models.CharField(max_length=300, null=True, blank=True)
    snmp_community = models.CharField(default='public', max_length=200)
    # created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, default='auth.User')
    created_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.hostname