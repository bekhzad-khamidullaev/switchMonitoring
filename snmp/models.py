from django.db import models

class Node(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class ATS(models.Model):
    name = models.CharField(max_length=100)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name='ats_list')

    def __str__(self):
        return self.name

class Switch(models.Model):
    hostname = models.CharField(max_length=200, blank=True, null=True)
    ip = models.GenericIPAddressField(unique=True)
    snmp_community_ro = models.CharField(default='public', max_length=64)
    status = models.BooleanField(default=True)
    ats = models.ForeignKey(ATS, on_delete=models.SET_NULL, null=True, related_name='switches')

    def __str__(self):
        return f"{self.hostname or self.ip}"

class SwitchPort(models.Model):
    switch = models.ForeignKey(Switch, on_delete=models.CASCADE, related_name='ports')
    port_index = models.PositiveIntegerField()
    description = models.CharField(max_length=255, blank=True, null=True)
    vlan_id = models.PositiveIntegerField(null=True, blank=True)  # добавлен VLAN
    speed = models.CharField(max_length=64, blank=True, null=True)
    admin_state = models.CharField(max_length=64, blank=True, null=True)
    oper_state = models.CharField(max_length=64, blank=True, null=True)
    rx_signal = models.FloatField(null=True, blank=True)  # Уровень RX сигнала
    tx_signal = models.FloatField(null=True, blank=True)  # Уровень TX сигнала

    def __str__(self):
        return f"Port {self.port_index} on {self.switch.hostname or self.switch.ip}"

class SwitchPortStats(models.Model):
    port = models.ForeignKey(SwitchPort, on_delete=models.CASCADE, related_name='stats')
    timestamp = models.DateTimeField(auto_now_add=True)
    octets_in = models.BigIntegerField()  # RX traffic
    octets_out = models.BigIntegerField()  # TX traffic

    class Meta:
        ordering = ['-timestamp']

class SwitchVlan(models.Model):
    port = models.ForeignKey(SwitchPort, on_delete=models.CASCADE, related_name='vlans')
    vlan_id = models.IntegerField()
    vlan_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"VLAN {self.vlan_id} on port {self.port.port_index}"
