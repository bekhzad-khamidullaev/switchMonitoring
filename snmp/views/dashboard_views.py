from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from snmp.models import Switch, NeighborLink
from .qoshimcha import get_permitted_branches

@login_required
def switches_updown(request):
    user_permitted_branches = get_permitted_branches(request.user)
    # NOTE: branch is derived via ATS relation
    sw_online = Switch.objects.filter(status=True, ats__branch__in=user_permitted_branches).count()
    sw_offline = Switch.objects.filter(status=False, ats__branch__in=user_permitted_branches).count()

    # Count switches that have at least one optical port with RX in given range
    base_qs = Switch.objects.filter(ats__branch__in=user_permitted_branches).distinct()
    high_signal_sw = base_qs.filter(interfaces__optics__rx_dbm__lte=-20).count()
    high_signal_sw_15 = base_qs.filter(interfaces__optics__rx_dbm__lte=-15, interfaces__optics__rx_dbm__gt=-20).count()
    high_signal_sw_10 = base_qs.filter(interfaces__optics__rx_dbm__lte=-11, interfaces__optics__rx_dbm__gt=-15).count()
    high_signal_sw_11 = base_qs.filter(interfaces__optics__rx_dbm__lte=-11).count()

    return render(request, 'dashboard.html', {
        'up_count': sw_online,
        'down_count': sw_offline,
        'high_sig_sw': high_signal_sw,
        'high_sig_sw_15': high_signal_sw_15,
        'high_sig_sw_10': high_signal_sw_10,
        'high_sig_sw_11': high_signal_sw_11,
    })


@login_required
def neighbor_switches_map(request):
    switches = Switch.objects.all()
    # Keep template compatibility with legacy SwitchesNeighbors fields.
    neighbors = [
        {
            'mac1': (n.local_switch.switch_mac if n.local_switch else ''),
            'port1': (n.local_interface.ifindex if n.local_interface else None),
            'mac2': n.remote_mac,
            'port2': n.remote_port,
        }
        for n in NeighborLink.objects.select_related('local_switch', 'local_interface').all()
    ]

    context = {
        'switches': switches,
        'neighbors': neighbors,
    }

    return render(request, 'neighbor_switches_map.html', context)