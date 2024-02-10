from django import forms
from .models import Switch

class SwitchForm(forms.ModelForm):
    class Meta:
        model = Switch
        fields = ['model', 'ip', 'uplink']

