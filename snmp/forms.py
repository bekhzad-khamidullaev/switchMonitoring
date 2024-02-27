from django import forms
from .models import Switch

class SwitchForm(forms.ModelForm):
    # device_model = forms.ModelChoiceField(queryset=SwitchModel.objects.all(), label='Switch Model')

    class Meta:
        model = Switch
        fields = ['ip', 'hostname']
