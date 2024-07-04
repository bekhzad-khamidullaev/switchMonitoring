from django.shortcuts import render
from .utils import get_zabbix_hosts, get_zabbix_metrics

def hosts_view(request):
    hosts = get_zabbix_hosts()
    return render(request, 'hosts.html', {'hosts': hosts})

def metrics_view(request, host_id):
    metrics = get_zabbix_metrics(host_id)
    return render(request, 'metrics.html', {'metrics': metrics})
