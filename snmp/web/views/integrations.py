from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
import requests
from urllib3.exceptions import InsecureRequestWarning

from snmp.models import Device as DeviceModel

if not settings.ZABBIX_VERIFY_SSL:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


@login_required
@permission_required('snmp.add_device', raise_exception=True)
@require_POST
def sync_hosts_from_zabbix(request):
    zabbix_url = settings.ZABBIX_URL
    zabbix_token = settings.ZABBIX_TOKEN
    verify_ssl = settings.ZABBIX_VERIFY_SSL
    if not zabbix_url or not zabbix_token:
        return redirect('dashboard')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {zabbix_token}',
    }
    payload = {
        'jsonrpc': '2.0',
        'method': 'host.get',
        'params': {'output': ['hostid', 'host', 'name']},
        'auth': zabbix_token,
        'id': 1,
    }

    try:
        response = requests.post(zabbix_url, headers=headers, json=payload, verify=verify_ssl, timeout=15)
        response.raise_for_status()
        hosts_result = response.json()

        if 'result' not in hosts_result:
            return redirect('dashboard')

        for host_data in hosts_result['result']:
            hostname = host_data['name']
            interfaces_payload = {
                'jsonrpc': '2.0',
                'method': 'hostinterface.get',
                'params': {'output': ['ip'], 'hostids': [host_data['hostid']]},
                'auth': zabbix_token,
                'id': 1,
            }
            interfaces_response = requests.post(
                zabbix_url,
                headers=headers,
                json=interfaces_payload,
                verify=verify_ssl,
                timeout=15,
            )
            interfaces_response.raise_for_status()
            interfaces_result = interfaces_response.json()

            if 'result' in interfaces_result and interfaces_result['result']:
                ip_address = interfaces_result['result'][0]['ip']
                if not DeviceModel.objects.filter(ip=ip_address).exists():
                    DeviceModel.objects.create(hostname=hostname, ip=ip_address)

        return redirect('dashboard')
    except Exception:
        return redirect('dashboard')
