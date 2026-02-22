from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Max, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from snmp.models import AlertEvent, AlertRule, Device, DeviceNeighbor, DevicePort, MetricSample

from .access import get_permitted_groups, user_has_global_device_access


@login_required
def devices_updown(request):
    user_permitted_groups = get_permitted_groups(request.user)

    # Device Status
    devices_online = Device.objects.filter(status=True, group__in=user_permitted_groups).count()
    devices_offline = Device.objects.filter(status=False, group__in=user_permitted_groups).count()

    # Alerts
    open_alerts = AlertEvent.objects.filter(
        state=AlertEvent.State.OPEN,
        subscription__device__group__in=user_permitted_groups
    )
    critical_alerts_count = open_alerts.filter(severity=AlertRule.Severity.CRITICAL).count()
    warning_alerts_count = open_alerts.filter(severity=AlertRule.Severity.WARNING).count()

    # Signal Quality Buckets
    high_signal_20 = Device.objects.filter(switch_ports_reverse__rx_signal__lte=-20, group__in=user_permitted_groups).distinct().count()
    high_signal_15 = Device.objects.filter(switch_ports_reverse__rx_signal__lte=-15, switch_ports_reverse__rx_signal__gt=-20, group__in=user_permitted_groups).distinct().count()
    high_signal_10 = Device.objects.filter(switch_ports_reverse__rx_signal__lte=-11, switch_ports_reverse__rx_signal__gt=-15, group__in=user_permitted_groups).distinct().count()
    high_signal_11 = Device.objects.filter(switch_ports_reverse__rx_signal__lte=-11, group__in=user_permitted_groups).distinct().count()

    # Vendor Distribution (Top 10)
    vendor_stats = (
        Device.objects.filter(group__in=user_permitted_groups)
        .values('vendor')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Model Distribution (Top 10)
    model_stats = (
        Device.objects.filter(group__in=user_permitted_groups)
        .values('model')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Recent Events
    recent_alerts = open_alerts.select_related(
        'subscription__device', 'subscription__metric'
    ).order_by('-opened_at')[:8]

    # Polling Health (last 24h)
    time_threshold = timezone.now() - timezone.timedelta(hours=24)
    subscriptions_with_last_sample = (
        MetricSample.objects.filter(
            subscription__device__group__in=user_permitted_groups,
            ts__gte=time_threshold,
        )
        .values('subscription_id')
        .annotate(
            last_ts=Max('ts'),
            last_bad_ts=Max('ts', filter=Q(quality=MetricSample.Quality.BAD)),
        )
    )
    total_metrics_count = subscriptions_with_last_sample.count()
    bad_metrics_count = subscriptions_with_last_sample.filter(
        last_bad_ts__isnull=False,
        last_ts=F('last_bad_ts'),
    ).count()
    health_score_pct = 100
    if total_metrics_count > 0:
        health_score_pct = max(0, min(100, round((1 - (bad_metrics_count / total_metrics_count)) * 100)))

    return render(
        request,
        'dashboard.html',
        {
            'up_count': devices_online,
            'down_count': devices_offline,
            'critical_alerts_count': critical_alerts_count,
            'warning_alerts_count': warning_alerts_count,
            'high_sig_sw': high_signal_20,
            'high_sig_sw_15': high_signal_15,
            'high_sig_sw_10': high_signal_10,
            'high_sig_sw_11': high_signal_11,
            'vendor_stats': list(vendor_stats),
            'model_stats': list(model_stats),
            'recent_alerts': recent_alerts,
            'bad_metrics_count': bad_metrics_count,
            'health_score_pct': health_score_pct,
        },
    )


@login_required
def neighbor_devices_map(request):
    nodes, links = _build_host_topology(request.user)
    node_index = {node['id']: node for node in nodes}
    return render(
        request,
        'neighbor_devices_map.html',
        {
            'topology_nodes': nodes,
            'topology_links': links,
            'topology_tree_rows': _build_topology_tree_rows(nodes, links),
            'topology_link_rows': _build_topology_link_rows(links, node_index),
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
        devices = Device.objects.filter(group__in=permitted_groups)
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
                'group': device.group.name if device.group_id and device.group else '',
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

        left_port = int(neighbor.port1)
        right_port = int(neighbor.port2)
        # LLDP relations are directional; dedupe only mirrored records
        # for the exact same device-port pair, while preserving parallel links.
        endpoint_key = tuple(sorted(((left.pk, left_port), (right.pk, right_port))))
        if endpoint_key in seen:
            continue
        seen.add(endpoint_key)

        if left.pk <= right.pk:
            source, target = left, right
            source_port, target_port = left_port, right_port
            source_mac, target_mac = mac1, mac2
        else:
            source, target = right, left
            source_port, target_port = right_port, left_port
            source_mac, target_mac = mac2, mac1

        source_key = (str(source.pk), source_port)
        target_key = (str(target.pk), target_port)
        source_state = port_state_by_device_port.get(source_key)
        target_state = port_state_by_device_port.get(target_key)
        link_status = _resolve_link_status(source_state, target_state)

        links.append(
            {
                'source': str(source.pk),
                'target': str(target.pk),
                'left_port': source_port,
                'right_port': target_port,
                'left_mac': source_mac,
                'right_mac': target_mac,
                'left_oper': source_state['oper'] if source_state else None,
                'left_admin': source_state['admin'] if source_state else None,
                'left_port_label': source_state['label'] if source_state else '',
                'right_oper': target_state['oper'] if target_state else None,
                'right_admin': target_state['admin'] if target_state else None,
                'right_port_label': target_state['label'] if target_state else '',
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


def _build_topology_link_rows(links, node_index):
    rows = []
    for link in links:
        source = node_index.get(link['source'])
        target = node_index.get(link['target'])
        rows.append(
            {
                'source_id': link['source'],
                'target_id': link['target'],
                'source_name': source['hostname'] if source else link['source'],
                'target_name': target['hostname'] if target else link['target'],
                'source_url': source['detail_url'] if source else '',
                'target_url': target['detail_url'] if target else '',
                'left_port': link['left_port'],
                'right_port': link['right_port'],
                'left_label': link.get('left_port_label') or f"p{link['left_port']}",
                'right_label': link.get('right_port_label') or f"p{link['right_port']}",
                'status': link.get('status') or 'unknown',
            }
        )
    return rows


def _build_topology_tree_rows(nodes, links):
    node_index = {node['id']: node for node in nodes}
    adjacency = {node['id']: [] for node in nodes}
    for link in links:
        source = link['source']
        target = link['target']
        adjacency.setdefault(source, []).append((target, link))
        adjacency.setdefault(target, []).append((source, link))

    visited = set()
    rows = []
    ordered_ids = sorted(node_index.keys(), key=lambda key: (node_index[key].get('hostname') or '').lower())

    def walk(node_id, parent_id=None, depth=0, parent_link=None):
        if node_id in visited:
            return
        visited.add(node_id)
        node = node_index[node_id]
        if parent_id and parent_link:
            if parent_link['source'] == parent_id:
                left_label = parent_link.get('left_port_label') or f"p{parent_link['left_port']}"
                right_label = parent_link.get('right_port_label') or f"p{parent_link['right_port']}"
                ports = f'{left_label} -> {right_label}'
            else:
                right_label = parent_link.get('right_port_label') or f"p{parent_link['right_port']}"
                left_label = parent_link.get('left_port_label') or f"p{parent_link['left_port']}"
                ports = f'{right_label} -> {left_label}'
            parent_name = node_index.get(parent_id, {}).get('hostname') or '-'
            link_status = parent_link.get('status') or 'unknown'
        else:
            ports = '-'
            parent_name = 'Root'
            link_status = 'root'

        rows.append(
            {
                'node_id': node_id,
                'hostname': node.get('hostname') or node_id,
                'ip': node.get('ip') or '',
                'detail_url': node.get('detail_url') or '',
                'alive': bool(node.get('status')),
                'depth': depth,
                'parent_name': parent_name,
                'ports': ports,
                'link_status': link_status,
            }
        )

        children = sorted(
            adjacency.get(node_id, []),
            key=lambda item: (node_index.get(item[0], {}).get('hostname') or '').lower(),
        )
        for child_id, child_link in children:
            if child_id == parent_id:
                continue
            walk(child_id, node_id, depth + 1, child_link)

    for node_id in ordered_ids:
        if node_id not in visited:
            walk(node_id)

    return rows
