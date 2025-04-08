from django.shortcuts import render, get_object_or_404
from snmp.models import Switch, SwitchPort
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required
def switch_detail(request, pk):
    switch = get_object_or_404(Switch, pk=pk)
    ports = switch.ports.all()
    return render(request, 'snmp/switch_detail.html', {'switch': switch, 'ports': ports})

@login_required
def port_traffic_data(request, port_id):
    port = get_object_or_404(SwitchPort, pk=port_id)
    stats = port.stats.all()
    data = {
        "labels": [stat.timestamp.strftime("%H:%M") for stat in stats],
        "rx": [stat.octets_in for stat in stats],
        "tx": [stat.octets_out for stat in stats],
    }
    return JsonResponse(data)
