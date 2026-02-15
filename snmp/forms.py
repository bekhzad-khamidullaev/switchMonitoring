from django import forms
from .models import ManagedDevice

class ManagedDeviceForm(forms.ModelForm):

    class Meta:
        model = ManagedDevice
        fields = ['ip', 'hostname']
