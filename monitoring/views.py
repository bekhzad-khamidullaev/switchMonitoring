from django.shortcuts import render, get_object_or_404
from .models import Device


def device_list(request):
    devices = Device.objects.all()
    return render(request, 'monitoring/device_list.html', {'devices': devices})


def device_detail(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return render(request, 'monitoring/device_detail.html', {'device': device})
