from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from snmp.models import Switch, SwitchesNeighbors
from .qoshimcha import get_permitted_branches

@login_required
def switches_updown(request):
    user_permitted_branches = get_permitted_branches(request.user)
    sw_online = Switch.objects.filter(status=True, branch__in=user_permitted_branches).count()
    sw_offline = Switch.objects.filter(status=False, branch__in=user_permitted_branches).count()
    high_signal_sw = Switch.objects.filter(rx_signal__lte=-20, branch__in=user_permitted_branches).count()
    high_signal_sw_15 = Switch.objects.filter(rx_signal__lte=-15, rx_signal__gt=-20, branch__in=user_permitted_branches).count()
    high_signal_sw_10 = Switch.objects.filter(rx_signal__lte=-11, rx_signal__gt=-15, branch__in=user_permitted_branches).count()

    return render(request, 'dashboard.html', {
        'up_count': sw_online,
        'down_count': sw_offline,
        'high_sig_sw': high_signal_sw,
        'high_sig_sw_15': high_signal_sw_15,
        'high_sig_sw_10': high_signal_sw_10
    })


@login_required
def neighbor_switches_map(request):
    switches = Switch.objects.all()
    neighbors = SwitchesNeighbors.objects.all()

    context = {
        'switches': switches,
        'neighbors': neighbors,
    }

    return render(request, 'neighbor_switches_map.html', context)