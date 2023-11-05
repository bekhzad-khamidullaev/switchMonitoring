from django.shortcuts import render, get_object_or_404, redirect
from .models import Vendor, SwitchModel, OltModel, Device, Switch, Olt
from .forms import SwitchForm, OltForm

def switch_list(request):
    switches = Switch.objects.all()
    return render(request, 'switch_list.html', {'switches': switches})

def switch_detail(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    return render(request, 'switch_detail.html', {'switch': switch})

def switch_create(request):
    if request.method == 'POST':
        form = SwitchForm(request.POST)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
    else:
        form = SwitchForm()
    return render(request, 'switch_form.html', {'form': form})

def switch_update(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        form = SwitchForm(request.POST, instance=switch)
        if form.is_valid():
            switch = form.save()
            return redirect('switch_detail', pk=switch.pk)
    else:
        form = SwitchForm(instance=switch)
    return render(request, 'switch_form.html', {'form': form})

def switch_delete(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    if request.method == 'POST':
        switch.delete()
        return redirect('switch_list')
    return render(request, 'switch_confirm_delete.html', {'switch': switch})

# Similar views for Olt model

def olt_list(request):
    olts = Olt.objects.all()
    return render(request, 'olt_list.html', {'olts': olts})

def olt_detail(request, pk):
    olt = get_object_or_404(Olt, pk=pk)
    return render(request, 'olt_detail.html', {'olt': olt})

def olt_create(request):
    if request.method == 'POST':
        form = OltForm(request.POST)
        if form.is_valid():
            olt = form.save()
            return redirect('olt_detail', pk=olt.pk)
    else:
        form = OltForm()
    return render(request, 'olt_form.html', {'form': form})

def olt_update(request, pk):
    olt = get_object_or_404(Olt, pk=pk)
    if request.method == 'POST':
        form = OltForm(request.POST, instance=olt)
        if form.is_valid():
            olt = form.save()
            return redirect('olt_detail', pk=olt.pk)
    else:
        form = OltForm(instance=olt)
    return render(request, 'olt_form.html', {'form': form})

def olt_delete(request, pk):
    olt = get_object_or_404(Olt, pk=pk)
    if request.method == 'POST':
        olt.delete()
        return redirect('olt_list')
    return render(request, 'olt_confirm_delete.html', {'olt': olt})
