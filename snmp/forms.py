from django import forms
from django.conf import settings

from .models import Device, DeviceProfile, ManagedDevice

class ManagedDeviceForm(forms.ModelForm):
    snmp_version = forms.ChoiceField(
        choices=Device.SnmpVersion.choices,
        required=True,
        initial=Device.SnmpVersion.V2C,
    )
    snmp_community_ro = forms.CharField(max_length=20, required=True)
    snmp_community_rw = forms.CharField(max_length=20, required=True)

    class Meta:
        model = ManagedDevice
        fields = ['ip', 'hostname', 'snmp_community_ro', 'snmp_community_rw']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['snmp_community_ro'].initial = self.instance.snmp_community_ro or settings.SNMP_DEFAULT_COMMUNITY_RO
        self.fields['snmp_community_rw'].initial = self.instance.snmp_community_rw or settings.SNMP_DEFAULT_COMMUNITY_RW
        if self.instance and self.instance.pk and hasattr(self.instance, 'device'):
            self.fields['snmp_version'].initial = self.instance.device.snmp_version

    def save(self, commit=True):
        managed_device = super().save(commit=False)
        managed_device.snmp_community_ro = self.cleaned_data['snmp_community_ro'].strip()
        managed_device.snmp_community_rw = self.cleaned_data['snmp_community_rw'].strip()

        if not commit:
            return managed_device

        managed_device.save()

        telemetry_device = (
            Device.objects.filter(managed_device=managed_device).first()
            or Device.objects.filter(ip=managed_device.ip).first()
        )
        if telemetry_device is None:
            telemetry_device = Device(
                managed_device=managed_device,
                ip=managed_device.ip,
            )

        telemetry_device.managed_device = managed_device
        telemetry_device.ip = managed_device.ip
        telemetry_device.hostname = managed_device.hostname or ''
        telemetry_device.status = bool(managed_device.status)
        telemetry_device.snmp_version = self.cleaned_data['snmp_version']
        telemetry_device.save()

        return managed_device


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
