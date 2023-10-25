from django.shortcuts import render, get_object_or_404, redirect
from .models import Vendor, DeviceModel, Olt, Switch
from .forms import OltForm, SwitchForm

def vendor_list(request):
    vendors = Vendor.objects.all()
    return render(request, 'vendor_list.html', {'vendors': vendors})

def device_model_list(request):
    device_models = DeviceModel.objects.all()
    return render(request, 'device_model_list.html', {'device_models': device_models})

def olt_list(request):
    olts = Olt.objects.all()
    return render(request, 'olt_list.html', {'olts': olts})

def switch_list(request):
    switches = Switch.objects.all()
    return render(request, 'switch_list.html', {'switches': switches})

def olt_detail(request, olt_id):
    olt = get_object_or_404(Olt, pk=olt_id)
    return render(request, 'olt_detail.html', {'olt': olt})

def switch_detail(request, switch_id):
    switch = get_object_or_404(Switch, pk=switch_id)
    return render(request, 'switch_detail.html', {'switch': switch})

def create_olt(request):
    if request.method == 'POST':
        form = OltForm(request.POST)
        if form.is_valid():
            olt = form.save()
            return redirect('olt_detail', olt_id=olt.id)
    else:
        form = OltForm()
    return render(request, 'create_olt.html', {'form': form})

def create_switch(request):
    if request.method == 'POST':
        form = SwitchForm(request.POST)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', switch_id=switch.id)
    else:
        form = SwitchForm()
    return render(request, 'create_switch.html', {'form': form})
