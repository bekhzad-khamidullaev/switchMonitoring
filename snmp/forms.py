from django import forms
from .models import Olt, Switch

class OltForm(forms.ModelForm):
    class Meta:
        model = Olt
        fields = ['deviceModel', 'hostname', 'ip_addr', 'uptime', 'sysinfo', 'snmp_community']

class SwitchForm(forms.ModelForm):
    class Meta:
        model = Switch
        fields = ['deviceModel', 'hostname', 'ip_addr', 'uptime', 'sysinfo', 'snmp_community']
