from django import forms
from django.conf import settings

from .models import Device, DeviceProfile


class DeviceForm(forms.ModelForm):
    snmp_version = forms.ChoiceField(
        choices=Device.SnmpVersion.choices,
        required=True,
        initial=Device.SnmpVersion.V2C,
    )
    profile = forms.ModelChoiceField(queryset=DeviceProfile.objects.none(), required=False)

    class Meta:
        model = Device
        fields = [
            'ip', 'hostname', 'snmp_community_ro', 'snmp_community_rw',
            'snmp_version', 'profile', 'group', 'subgroup', 'device_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group'].label = 'Group'
        self.fields['subgroup'].label = 'Subgroup'
        self.fields['subgroup'].required = False
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


class DeviceHostSettingsForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = [
            'ip', 'hostname', 'vendor', 'model', 'firmware', 'sys_object_id',
            'snmp_version', 'auth_profile', 'status',
            'device_type', 'uptime', 'switch_mac',
            'snmp_community_ro', 'snmp_community_rw',
            'neighbor', 'parent_port',
            'profile', 'group', 'subgroup',
            'soft_version', 'serial_number',
            'rx_signal', 'tx_signal', 'sfp_vendor', 'part_number',
            'last_discovered_at',
        ]
        widgets = {
            'last_discovered_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile'].queryset = DeviceProfile.objects.order_by('priority', 'vendor', 'model_pattern')
        self.fields['profile'].empty_label = 'No profile'
        self.fields['group'].label = 'Group'
        self.fields['subgroup'].label = 'Subgroup'
        self.fields['subgroup'].required = False
        self.fields['last_discovered_at'].required = False
        self.fields['last_discovered_at'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']

        if self.instance.pk and self.instance.last_discovered_at:
            self.initial['last_discovered_at'] = self.instance.last_discovered_at.strftime('%Y-%m-%dT%H:%M')

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (
                f'{css} w-full rounded-md border border-surface-200 px-3 py-2 text-sm text-surface-900 '
                'focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100'
            ).strip()

    def save(self, commit=True):
        device = super().save(commit=False)
        device.snmp_community_ro = (self.cleaned_data.get('snmp_community_ro') or '').strip()
        device.snmp_community_rw = (self.cleaned_data.get('snmp_community_rw') or '').strip()
        device.switch_mac = (self.cleaned_data.get('switch_mac') or '').strip() or None
        device.serial_number = (self.cleaned_data.get('serial_number') or '').strip() or None
        if commit:
            device.save()
        return device
