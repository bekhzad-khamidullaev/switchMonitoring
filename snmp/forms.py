from django import forms
from django.conf import settings

from .models import Ats, Device, DeviceProfile


class DeviceForm(forms.ModelForm):
    snmp_version = forms.ChoiceField(
        choices=Device.SnmpVersion.choices,
        required=True,
        initial=Device.SnmpVersion.V2C,
    )
    ats = forms.ModelChoiceField(queryset=Ats.objects.all(), required=False, label='Subgroup')
    profile = forms.ModelChoiceField(queryset=DeviceProfile.objects.none(), required=False)

    class Meta:
        model = Device
        fields = [
            'ip', 'hostname', 'snmp_community_ro', 'snmp_community_rw',
            'snmp_version', 'profile', 'branch', 'ats', 'device_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].label = 'Group'
        self.fields['profile'].queryset = DeviceProfile.objects.order_by('priority', 'vendor', 'model_pattern')
        self.fields['profile'].empty_label = 'No profile'
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
