import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from urllib3.exceptions import InsecureRequestWarning

from snmp.models import Ats, Branch
from snmp.models import Device as DeviceModel
from snmp.tasks import discover_device_task, poll_device_metrics_task

from .access import get_permitted_branches, user_has_global_device_access

if not settings.ZABBIX_VERIFY_SSL:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def _upsert_branch_hierarchy(path):
    parent = None
    current = None
    for chunk in (path or "").split("/"):
        name = chunk.strip()
        if not name:
            continue
        current, _ = Branch.objects.get_or_create(name=name, parent=parent)
        parent = current
    return current


def _select_branch_from_hostgroups(hostgroups):
    if not hostgroups:
        return None

    names = []
    for item in hostgroups:
        raw_name = (item or {}).get("name", "")
        if raw_name and raw_name.strip():
            names.append(raw_name.strip())
    if not names:
        return None

    # Prefer the most specific path, then deterministic by name.
    names.sort(key=lambda n: (len([p for p in n.split("/") if p.strip()]), n), reverse=True)
    return _upsert_branch_hierarchy(names[0])


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
        'params': {
            'output': ['hostid', 'host', 'name'],
            'selectHostGroups': ['groupid', 'name'],
        },
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
            branch = _select_branch_from_hostgroups(host_data.get('hostgroups'))
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
                defaults = {'hostname': hostname}
                if branch:
                    defaults['branch'] = branch

                device, created = DeviceModel.objects.get_or_create(ip=ip_address, defaults=defaults)
                if not created:
                    updates = {}
                    if hostname and device.hostname != hostname:
                        updates['hostname'] = hostname
                    if branch and device.branch_id != branch.id:
                        updates['branch'] = branch
                    if updates:
                        DeviceModel.objects.filter(pk=device.pk).update(**updates)

        return redirect('dashboard')
    except Exception:
        return redirect('dashboard')


@login_required
@permission_required('snmp.change_device', raise_exception=True)
@require_POST
def run_bulk_device_job(request):
    action = (request.POST.get('action') or '').strip().lower()
    scope = (request.POST.get('scope') or 'all').strip().lower()

    if action not in {'discover', 'poll'}:
        return JsonResponse({'error': 'invalid action'}, status=400)
    if scope not in {'all', 'branch', 'ats', 'device_ids'}:
        return JsonResponse({'error': 'invalid scope'}, status=400)

    queryset = DeviceModel.objects.all()
    if not user_has_global_device_access(request.user):
        permitted = get_permitted_branches(request.user)
        queryset = queryset.filter(branch__in=permitted)

    if scope == 'branch':
        branch_id = request.POST.get('branch_id')
        if not branch_id or not str(branch_id).isdigit():
            return JsonResponse({'error': 'branch_id is required'}, status=400)
        queryset = queryset.filter(branch_id=int(branch_id))
    elif scope == 'ats':
        ats_id = request.POST.get('ats_id')
        if not ats_id or not str(ats_id).isdigit():
            return JsonResponse({'error': 'ats_id is required'}, status=400)
        if not Ats.objects.filter(pk=int(ats_id)).exists():
            return JsonResponse({'error': 'ats not found'}, status=404)
        queryset = queryset.filter(ats_id=int(ats_id))
    elif scope == 'device_ids':
        raw_ids = request.POST.getlist('device_ids')
        if not raw_ids:
            as_csv = (request.POST.get('device_ids') or '').strip()
            raw_ids = [part.strip() for part in as_csv.split(',') if part.strip()]
        expanded_ids = []
        for raw in raw_ids:
            expanded_ids.extend([part.strip() for part in str(raw).split(',') if part.strip()])
        device_ids = []
        for raw in expanded_ids:
            if not str(raw).isdigit():
                return JsonResponse({'error': 'device_ids must be numeric'}, status=400)
            device_ids.append(int(raw))
        if not device_ids:
            return JsonResponse({'error': 'device_ids is required'}, status=400)
        queryset = queryset.filter(pk__in=device_ids)

    queued = 0
    for device_id in queryset.values_list('id', flat=True).iterator(chunk_size=500):
        if action == 'discover':
            discover_device_task.delay(device_id)
        else:
            poll_device_metrics_task.delay(device_id)
        queued += 1

    payload = {'queued': queued, 'action': action, 'scope': scope}
    return JsonResponse(payload)
