from django.shortcuts import render, get_object_or_404, redirect
from .models import Olt, Switch


def olt_detail(request, olt_id):
    olt = get_object_or_404(Olt, pk=olt_id)
    return render(request, 'olt_detail.html', {'olt': olt})

def switch_detail(request, switch_id):
    switch = get_object_or_404(Switch, pk=switch_id)
    return render(request, 'switch_detail.html', {'switch': switch})