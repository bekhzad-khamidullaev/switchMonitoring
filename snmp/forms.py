from django import forms
from .models import Switch, SwitchModel

class SwitchForm(forms.ModelForm):
    device_model = forms.ModelChoiceField(queryset=SwitchModel.objects.all(), label='Switch Model')

    class Meta:
        model = Switch
        fields = ['device_model', 'ip', 'hostname']
