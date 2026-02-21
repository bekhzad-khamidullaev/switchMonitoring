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

from .access import get_permitted_groups, user_has_global_device_access

if not settings.ZABBIX_VERIFY_SSL:
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def _normalize_name(raw_name):
    if raw_name is None:
        return ""
    return str(raw_name).strip()


def _get_existing_branch(name, parent):
    normalized = _normalize_name(name)
    if not normalized:
        return None
    siblings = Branch.objects.filter(parent=parent).exclude(name__isnull=True).only("id", "name")
    normalized_lower = normalized.lower()
    for sibling in siblings:
        sibling_name = _normalize_name(sibling.name)
        if sibling_name.lower() == normalized_lower:
            return sibling
    return None


def _upsert_group_hierarchy(path_chunks):
    parent = None
    current = None
    for chunk in path_chunks:
        name = _normalize_name(chunk)
        if not name:
            continue
        current = _get_existing_branch(name=name, parent=parent)
        if not current:
            current = Branch.objects.create(name=name, parent=parent)
        parent = current
    return current


def _parse_group_path(raw_path):
    return [part for part in (_normalize_name(chunk) for chunk in (raw_path or "").split("/")) if part]


def _select_group_from_hostgroups(hostgroups):
    if not hostgroups:
        return None

    names = []
    seen = set()
    for item in hostgroups:
        raw_name = _normalize_name((item or {}).get("name", ""))
        if raw_name:
            dedupe_key = raw_name.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            names.append(raw_name)
    if not names:
        return None

    # Prefer the most specific path, then deterministic by name.
    names.sort(key=lambda n: (len([p for p in n.split("/") if p.strip()]), n), reverse=True)
    selected = names[0]
    chunks = _parse_group_path(selected)
    if not chunks:
        return None
    return _upsert_group_hierarchy(chunks)


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

        processed_ips = set()
        for host_data in hosts_result['result']:
            hostname = host_data['name']
            group = _select_group_from_hostgroups(host_data.get('hostgroups'))
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
                if ip_address in processed_ips:
                    continue
                processed_ips.add(ip_address)
                defaults = {'hostname': hostname}
                if group:
                    defaults['group'] = group

                device, created = DeviceModel.objects.get_or_create(ip=ip_address, defaults=defaults)
                if not created:
                    updates = {}
                    if hostname and device.hostname != hostname:
                        updates['hostname'] = hostname
                    if group and device.group_id != group.id:
                        updates['group'] = group
                    if device.subgroup_id is not None:
                        updates['subgroup'] = None
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
    if scope not in {'all', 'group', 'subgroup', 'branch', 'ats', 'device_ids'}:
        return JsonResponse({'error': 'invalid scope'}, status=400)

    queryset = DeviceModel.objects.all()
    if not user_has_global_device_access(request.user):
        permitted = get_permitted_groups(request.user)
        queryset = queryset.filter(group__in=permitted)

    if scope in {'group', 'branch'}:
        group_id = request.POST.get('group_id') or request.POST.get('branch_id')
        if not group_id or not str(group_id).isdigit():
            return JsonResponse({'error': 'group_id is required'}, status=400)
        queryset = queryset.filter(group_id=int(group_id))
    elif scope in {'subgroup', 'ats'}:
        subgroup_id = request.POST.get('subgroup_id') or request.POST.get('ats_id')
        if not subgroup_id or not str(subgroup_id).isdigit():
            return JsonResponse({'error': 'subgroup_id is required'}, status=400)
        if not Ats.objects.filter(pk=int(subgroup_id)).exists():
            return JsonResponse({'error': 'subgroup not found'}, status=404)
        queryset = queryset.filter(subgroup_id=int(subgroup_id))
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
