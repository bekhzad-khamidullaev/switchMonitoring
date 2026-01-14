from collections import defaultdict

from django.db.models import Min
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from snmp.models import Branch, HostGroup, Switch
from snmp.views.qoshimcha import get_permitted_branches


def _build_group_tree(groups, switches_by_group):
    children_map = defaultdict(list)
    by_id = {}
    for g in groups:
        by_id[g.id] = g
        children_map[g.parent_id].append(g)

    def node(g):
        return {
            'type': 'group',
            'id': g.id,
            'name': g.name,
            'children': [node(c) for c in sorted(children_map.get(g.id, []), key=lambda x: (x.sort_order, x.name))],
            'hosts': switches_by_group.get(g.id, []),
        }

    roots = sorted(children_map.get(None, []), key=lambda x: (x.sort_order, x.name))
    return [node(r) for r in roots]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def monitoring_tree(request):
    branches = get_permitted_branches(request.user)

    # Groups
    groups = list(HostGroup.objects.filter(branch__in=branches).select_related('branch'))

    # Hosts
    switches = (
        Switch.objects
        .select_related('ats', 'ats__branch')
        .filter(ats__branch__in=branches)
        .annotate(min_rx=Min('interfaces__optics__rx_dbm'), min_tx=Min('interfaces__optics__tx_dbm'))
        .values('id', 'hostname', 'ip', 'status', 'group_id', 'min_rx', 'min_tx', 'ats_id', 'ats__name', 'ats__branch_id')
    )

    switches_by_group = defaultdict(list)
    ungrouped_by_branch = defaultdict(list)

    for s in switches:
        host = {
            'type': 'host',
            'id': s['id'],
            'hostname': s['hostname'],
            'ip': s['ip'],
            'status': bool(s['status']),
            'min_rx': s['min_rx'],
            'min_tx': s['min_tx'],
        }
        if s['group_id']:
            switches_by_group[s['group_id']].append(host)
        else:
            ungrouped_by_branch[s['ats__branch_id']].append(host)

    # Build output per region (Branch)
    out = []
    for b in Branch.objects.filter(id__in=[br.id for br in branches]).order_by('name'):
        branch_groups = [g for g in groups if g.branch_id == b.id]
        tree = _build_group_tree(branch_groups, switches_by_group)
        out.append({
            'type': 'region',
            'id': b.id,
            'name': b.name,
            'groups': tree,
            'ungrouped_hosts': ungrouped_by_branch.get(b.id, []),
        })

    return Response(out)
