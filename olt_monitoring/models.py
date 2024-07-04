from django.db import models
from simple_history.models import HistoricalRecords
from django.utils import timezone
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group
from vendors.models import Vendor, Branch, HostModel, SubnetAts

class Olt(models.Model):
    ip = models.GenericIPAddressField(protocol='both', null=True, blank=True)
    hostname = models.CharField(max_length=200, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    model = models.ForeignKey(HostModel, on_delete=models.SET_NULL, blank=True, null=True)
    status = models.BooleanField(default=False, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, blank=True, null=True)
    ats = models.ForeignKey(SubnetAts, on_delete=models.SET_NULL, null=True)
    soft_version = models.CharField(max_length=80, blank=True, null=True)
    serial_number = models.CharField(unique=True, max_length=100, null=True, blank=True)
    uptime = models.CharField(max_length=200, blank=True, null=True)
    last_update = models.DateTimeField(auto_now=True, null=True, blank=True)
    mac = models.CharField(unique=True, max_length=17, null=True, blank=True)
    community_ro = models.CharField(max_length=20, default='public', null=True, blank=True)
    community_rw = models.CharField(max_length=20, default='private', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        managed = True
        db_table = 'olt'
        unique_together = (('hostname', 'ip'),)
        indexes = [
            models.Index(fields=['status', 'hostname', 'ip']),
        ]
    
    def save(self, *args, **kwargs):
        self.last_update = timezone.now()
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.hostname or f"Olt with IP: {self.ip}"


class Slot(models.Model):
    host = models.ForeignKey(Olt, related_name='slots', on_delete=models.CASCADE, related_query_name='slot')
    slot_number = models.IntegerField()
    temperature = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f'{self.host.hostname} slot: {self.slot_number}'
    

