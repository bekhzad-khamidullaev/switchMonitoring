from django import forms
from .models import Switch, Olt

class SwitchForm(forms.ModelForm):
    class Meta:
        model = Switch
        fields = ['device_model_local', 'device_hostname', 'device_ip', 'device_snmp_community', 'sysdescr_oid']

class OltForm(forms.ModelForm):
    class Meta:
        model = Olt
        fields = ['device_model_local', 'device_hostname', 'device_ip', 'device_snmp_community', 'sysdescr_oid']
