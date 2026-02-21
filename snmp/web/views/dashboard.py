from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from snmp.models import Device, DeviceNeighbor, DevicePort

from .access import get_permitted_groups, user_has_global_device_access


@login_required
def devices_updown(request):
    user_permitted_groups = get_permitted_groups(request.user)
    devices_online = Device.objects.filter(status=True, branch__in=user_permitted_groups).count()
    devices_offline = Device.objects.filter(status=False, branch__in=user_permitted_groups).count()
    high_signal_20 = Device.objects.filter(rx_signal__lte=-20, branch__in=user_permitted_groups).count()
    high_signal_15 = Device.objects.filter(rx_signal__lte=-15, rx_signal__gt=-20, branch__in=user_permitted_groups).count()
    high_signal_10 = Device.objects.filter(rx_signal__lte=-11, rx_signal__gt=-15, branch__in=user_permitted_groups).count()
    high_signal_11 = Device.objects.filter(rx_signal__lte=-11, branch__in=user_permitted_groups).count()

    return render(
        request,
        'dashboard.html',
        {
            'up_count': devices_online,
            'down_count': devices_offline,
            'high_sig_sw': high_signal_20,
            'high_sig_sw_15': high_signal_15,
            'high_sig_sw_10': high_signal_10,
            'high_sig_sw_11': high_signal_11,
        },
    )


@login_required
def neighbor_devices_map(request):
    nodes, links = _build_host_topology(request.user)
    return render(
        request,
        'neighbor_devices_map.html',
        {
            'topology_nodes': nodes,
            'topology_links': links,
        },
    )


@login_required
def neighbor_devices_map_data(request):
    nodes, links = _build_host_topology(request.user)
    return JsonResponse({'nodes': nodes, 'links': links})


def _build_host_topology(user):
    if user_has_global_device_access(user):
        devices = Device.objects.all()
        neighbors = DeviceNeighbor.objects.all()
    else:
        permitted_groups = get_permitted_groups(user)
        devices = Device.objects.filter(branch__in=permitted_groups)
        device_macs = devices.exclude(switch_mac__isnull=True).exclude(switch_mac='').values_list('switch_mac', flat=True)
        neighbors = DeviceNeighbor.objects.filter(mac1__in=device_macs, mac2__in=device_macs)

    devices_by_mac = {}
    device_ids = []
    nodes = []
    for device in devices:
        device_ids.append(device.pk)
        mac = (device.switch_mac or '').strip().lower()
        if mac:
            devices_by_mac[mac] = device
        nodes.append(
            {
                'id': str(device.pk),
                'hostname': device.hostname or f"Device-{device.pk}",
                'ip': str(device.ip or ''),
                'status': bool(device.status),
                'mac': mac,
                'group': device.branch.name if device.branch_id and device.branch else '',
                'detail_url': reverse('device_detail', args=[device.pk]),
            }
        )

    port_state_by_device_port = {}
    if device_ids:
        ports = DevicePort.objects.filter(managed_device_id__in=device_ids).values(
            'managed_device_id', 'port', 'oper', 'admin', 'name', 'alias', 'description'
        )
        for port in ports:
            label = port.get('alias') or port.get('name') or port.get('description') or ''
            port_state_by_device_port[(str(port['managed_device_id']), int(port['port']))] = {
                'oper': port['oper'],
                'admin': port['admin'],
                'label': label,
            }

    links = []
    seen = set()
    for neighbor in neighbors:
        mac1 = (neighbor.mac1 or '').strip().lower()
        mac2 = (neighbor.mac2 or '').strip().lower()
        left = devices_by_mac.get(mac1)
        right = devices_by_mac.get(mac2)
        if not left or not right or left.pk == right.pk:
            continue

        pair = tuple(sorted((left.pk, right.pk)))
        if pair in seen:
            continue
        seen.add(pair)

        left_key = (str(left.pk), int(neighbor.port1))
        right_key = (str(right.pk), int(neighbor.port2))
        left_state = port_state_by_device_port.get(left_key)
        right_state = port_state_by_device_port.get(right_key)
        link_status = _resolve_link_status(left_state, right_state)

        links.append(
            {
                'source': str(left.pk),
                'target': str(right.pk),
                'left_port': neighbor.port1,
                'right_port': neighbor.port2,
                'left_mac': mac1,
                'right_mac': mac2,
                'left_oper': left_state['oper'] if left_state else None,
                'left_admin': left_state['admin'] if left_state else None,
                'left_port_label': left_state['label'] if left_state else '',
                'right_oper': right_state['oper'] if right_state else None,
                'right_admin': right_state['admin'] if right_state else None,
                'right_port_label': right_state['label'] if right_state else '',
                'status': link_status,
            }
        )

    return nodes, links


def _is_port_up(state):
    if not state:
        return None
    admin = state.get('admin')
    oper = state.get('oper')
    if admin is None and oper is None:
        return None
    return admin == 1 and oper == 1


def _resolve_link_status(left_state, right_state):
    left_up = _is_port_up(left_state)
    right_up = _is_port_up(right_state)
    if left_up is None and right_up is None:
        return 'unknown'
    if left_up is False or right_up is False:
        return 'down'
    if left_up is True and right_up is True:
        return 'up'
    return 'unknown'
