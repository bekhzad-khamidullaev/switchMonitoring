from django import forms
from .models import Switch, Olt

class SwitchForm(forms.ModelForm):
    class Meta:
        model = Switch
        fields = ['device_model', 'device_hostname', 'device_ip', 'device_optical_info', 'device_snmp_community', 'device_general_oid']

class OltForm(forms.ModelForm):
    class Meta:
        model = Olt
        fields = ['device_model', 'device_hostname', 'device_ip', 'device_optical_info', 'device_snmp_community', 'device_general_oid']
