from django.http import JsonResponse

from snmp.services.observability.metrics import get_metrics_snapshot


def app_metrics_view(request):
    return JsonResponse(get_metrics_snapshot())
