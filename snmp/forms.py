from django import forms
from django.conf import settings

from .models import Device, DeviceProfile

class DeviceForm(forms.ModelForm):
    snmp_version = forms.ChoiceField(
        choices=Device.SnmpVersion.choices,
        required=True,
        initial=Device.SnmpVersion.V2C,
    )

    class Meta:
        model = Device
        fields = [
            'ip', 'hostname', 'snmp_community_ro', 'snmp_community_rw', 
            'snmp_version', 'branch', 'ats', 'device_type'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['snmp_community_ro'].initial = self.instance.snmp_community_ro or settings.SNMP_DEFAULT_COMMUNITY_RO
        self.fields['snmp_community_rw'].initial = self.instance.snmp_community_rw or settings.SNMP_DEFAULT_COMMUNITY_RW

    def save(self, commit=True):
        device = super().save(commit=False)
        device.snmp_community_ro = self.cleaned_data['snmp_community_ro'].strip()
        device.snmp_community_rw = self.cleaned_data['snmp_community_rw'].strip()
        device.snmp_version = self.cleaned_data['snmp_version']
        
        if commit:
            device.save()
        return device


class DeviceProfileForm(forms.ModelForm):
    class Meta:
        model = DeviceProfile
        fields = ['vendor', 'model_pattern', 'firmware_pattern', 'priority', 'active']

    def clean_vendor(self):
        return self.cleaned_data['vendor'].strip()

    def clean_model_pattern(self):
        return self.cleaned_data['model_pattern'].strip()

    def clean_firmware_pattern(self):
        return self.cleaned_data.get('firmware_pattern', '').strip()
