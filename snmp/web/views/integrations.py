import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from urllib3.exceptions import InsecureRequestWarning
import logging

from snmp.models import Ats, Branch
from snmp.models import Device as DeviceModel
from snmp.tasks import discover_device_task, poll_device_metrics_task

from .access import get_permitted_groups, user_has_global_device_access

logger = logging.getLogger(__name__)


def _configure_zabbix_ssl_warnings(verify_ssl: bool) -> None:
    if verify_ssl:
        return
    try:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    except Exception:
        logger.debug("failed to disable urllib3 warnings for insecure zabbix ssl")


def _zabbix_request(zabbix_url, headers, payload, verify_ssl):
    response = requests.post(zabbix_url, headers=headers, json=payload, verify=verify_ssl, timeout=30)
    response.raise_for_status()
    parsed = response.json()
    if not isinstance(parsed, dict):
        raise ValueError('invalid zabbix response format')
    if parsed.get('error'):
        raise ValueError(f"zabbix api error: {parsed.get('error')}")
    return parsed


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
    _configure_zabbix_ssl_warnings(verify_ssl)

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
        hosts_result = _zabbix_request(zabbix_url, headers, payload, verify_ssl)

        if 'result' not in hosts_result:
            return redirect('dashboard')

        host_entries = [item for item in hosts_result.get('result', []) if isinstance(item, dict)]
        host_ids = [str(item.get('hostid', '')).strip() for item in host_entries if str(item.get('hostid', '')).strip()]
        if not host_ids:
            return redirect('dashboard')

        interfaces_payload = {
            'jsonrpc': '2.0',
            'method': 'hostinterface.get',
            'params': {
                'output': ['hostid', 'ip'],
                'hostids': host_ids,
            },
            'auth': zabbix_token,
            'id': 2,
        }
        interfaces_result = _zabbix_request(zabbix_url, headers, interfaces_payload, verify_ssl)
        interfaces_by_hostid = {}
        unresolved_ips = []
        for row in interfaces_result.get('result', []):
            if not isinstance(row, dict):
                continue
            hostid = str(row.get('hostid', '')).strip()
            ip_value = str(row.get('ip', '')).strip()
            if not ip_value:
                continue
            if not hostid:
                unresolved_ips.append(ip_value)
                continue
            # Keep first interface with a non-empty IP for each host.
            interfaces_by_hostid.setdefault(hostid, ip_value)
        if unresolved_ips:
            # Fallback for non-standard payloads without hostid (seen in some proxies/mocks).
            for hostid, ip_value in zip(host_ids, unresolved_ips):
                interfaces_by_hostid.setdefault(hostid, ip_value)

        processed_ips = set()
        for host_data in host_entries:
            hostid = str(host_data.get('hostid', '')).strip()
            hostname = _normalize_name(host_data.get('name') or host_data.get('host'))
            if not hostid:
                continue

            ip_address = interfaces_by_hostid.get(hostid)
            if not ip_address:
                continue
            if ip_address in processed_ips:
                continue
            processed_ips.add(ip_address)

            group = _select_group_from_hostgroups(host_data.get('hostgroups'))
            defaults = {'hostname': hostname}
            if group:
                defaults['group'] = group

            try:
                device, created = DeviceModel.objects.get_or_create(ip=ip_address, defaults=defaults)
            except Exception:
                logger.exception(
                    'zabbix sync failed to upsert device',
                    extra={'hostid': hostid, 'ip': ip_address, 'hostname': hostname},
                )
                continue

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
        logger.exception('zabbix sync failed')
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
