from django.shortcuts import render, get_object_or_404
from snmp.models import SwitchPort
from django.http import JsonResponse
from django.utils.timezone import now, timedelta

def port_chart_partial(request, port_id):
    port = get_object_or_404(SwitchPort, pk=port_id)

    # Получение статистики за последние 24 часа
    stats = port.stats.filter(timestamp__gte=now() - timedelta(hours=24)).order_by('timestamp')

    data = {
        "labels": [stat.timestamp.strftime("%H:%M") for stat in stats],
        "rx": [stat.octets_in for stat in stats],
        "tx": [stat.octets_out for stat in stats],
    }

    return render(request, 'snmp/port_chart.html', {'data': data, 'port': port})
