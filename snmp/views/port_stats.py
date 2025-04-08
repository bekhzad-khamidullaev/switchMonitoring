from django.http import JsonResponse
from snmp.models import SwitchPort
from django.utils.timezone import now, timedelta

def port_traffic_data(request, port_id):
    port = SwitchPort.objects.get(pk=port_id)
    stats = port.stats.filter(timestamp__gte=now() - timedelta(hours=24)).order_by('timestamp')

    data = {
        "labels": [s.timestamp.strftime("%H:%M") for s in stats],
        "rx": [s.octets_in for s in stats],
        "tx": [s.octets_out for s in stats],
    }
    return JsonResponse(data)