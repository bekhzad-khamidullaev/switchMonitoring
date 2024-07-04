from django.http import JsonResponse
from olt_monitoring.models import Olt
from django.shortcuts import redirect
import requests
from urllib3.exceptions import InsecureRequestWarning
from django.contrib.auth.decorators import login_required

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


@login_required
def sync_hosts_from_zabbix(request):

    zabbix_url = 'https://monitoring.tshtt.uz/api_jsonrpc.php'
    zabbix_token = '07a85582c7d772dd29ad5ee25b6c089fe0ca23f05724c707436752ddf81db328'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {zabbix_token}'
    }

    payload = {
        'jsonrpc': '2.0',
        'method': 'host.get',
        'params': {
            'output': ['hostid', 'host', 'name']
        },
        'auth': zabbix_token,
        'id': 1
    }

    try:

        response = requests.post(zabbix_url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        hosts_result = response.json()

        if 'result' in hosts_result:
            for host_data in hosts_result['result']:
                hostname = host_data['name']

                interfaces_payload = {
                    'jsonrpc': '2.0',
                    'method': 'hostinterface.get',
                    'params': {
                        'output': ['ip'],
                        'hostids': [host_data['hostid']]
                    },
                    'auth': zabbix_token,
                    'id': 1
                }


                interfaces_response = requests.post(zabbix_url, headers=headers, json=interfaces_payload, verify=False)
                interfaces_response.raise_for_status()
                interfaces_result = interfaces_response.json()

                if 'result' in interfaces_result and interfaces_result['result']:
                    
                    ip_address = interfaces_result['result'][0]['ip']
                    
                    if ip_address.startswith('10.244.'):

                        if not Olt.objects.filter(ip=ip_address).exists():

                            olt = Olt.objects.create(hostname=hostname, ip=ip_address)


            return redirect('dashboard')
        else:
            return redirect('dashboard')
    except Exception as e:
        return redirect('dashboard')