
from django.http import JsonResponse
from snmp.models import Switch
from django.shortcuts import redirect
import requests
from urllib3.exceptions import InsecureRequestWarning
from django.contrib.auth.decorators import login_required

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


@login_required
def sync_hosts_from_zabbix(request):
    # Zabbix API token and endpoint
    zabbix_url = 'https://monitoring.tshtt.uz/api_jsonrpc.php'
    zabbix_token = '89296f0cae9f7d302495371e27be491100d516196608be0caace979572467cf7'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {zabbix_token}'
    }
    # Define the API request payload
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
        # Fetch hosts from Zabbix
        response = requests.post(zabbix_url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        hosts_result = response.json()

        if 'result' in hosts_result:
            for host_data in hosts_result['result']:
                hostname = host_data['name']

                # Fetch interface information for the host
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

                # Make a request to get interface information
                interfaces_response = requests.post(zabbix_url, headers=headers, json=interfaces_payload, verify=False)
                interfaces_response.raise_for_status()
                interfaces_result = interfaces_response.json()

                if 'result' in interfaces_result and interfaces_result['result']:
                    
                    ip_address = interfaces_result['result'][0]['ip']  # Assuming only one interface per host
                    
                    # Retrieve the list of IPs from Zabbix
                    # Retrieve the list of IPs from Zabbix
                    # zabbix_ips = set(interface['ip'] for host_data in hosts_result['result'] for interface in host_data.get('interfaces', []))


                    # # Retrieve the list of IPs from your database
                    # db_ips = set(Switch.objects.values_list('ip', flat=True))
                    # # Find IPs that exist in the database but not in Zabbix
                    # ips_to_delete = db_ips - zabbix_ips
                    # for ip in ips_to_delete:
                    #     print(ip)
                    # Switch.objects.filter(ip__in=ips_to_delete).delete()
                    # Check if the IP address already exists in the database
                    if not Switch.objects.filter(ip=ip_address).exists():
                        # If IP address doesn't exist, create a new switch
                        switch = Switch.objects.create(hostname=hostname, ip=ip_address)
                        # You can perform additional operations here if needed

            return redirect('dashboard')
        else:
            return redirect('dashboard')
    except Exception as e:
        return redirect('dashboard')