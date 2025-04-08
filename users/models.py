from django.db import models
from django.contrib.auth.models import User
from snmp.models import Node, ATS

class AccessPermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, null=True, blank=True)
    ats = models.ForeignKey(ATS, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Admin'),
        ('node_manager', 'Node Manager'),
        ('ats_operator', 'ATS Operator'),
        ('readonly', 'Read Only'),
    ])

    def __str__(self):
        return f"{self.user.username} access to {self.node or self.ats}"
