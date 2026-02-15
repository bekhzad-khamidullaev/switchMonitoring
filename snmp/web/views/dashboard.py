from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from snmp.models import ManagedDevice as ManagedDeviceModel
from snmp.models import SwitchesNeighbors as DeviceNeighbors

from .access import get_permitted_branches, user_has_global_device_access


@login_required
def devices_updown(request):
    user_permitted_branches = get_permitted_branches(request.user)
    devices_online = ManagedDeviceModel.objects.filter(status=True, branch__in=user_permitted_branches).count()
    devices_offline = ManagedDeviceModel.objects.filter(status=False, branch__in=user_permitted_branches).count()
    high_signal_20 = ManagedDeviceModel.objects.filter(rx_signal__lte=-20, branch__in=user_permitted_branches).count()
    high_signal_15 = ManagedDeviceModel.objects.filter(rx_signal__lte=-15, rx_signal__gt=-20, branch__in=user_permitted_branches).count()
    high_signal_10 = ManagedDeviceModel.objects.filter(rx_signal__lte=-11, rx_signal__gt=-15, branch__in=user_permitted_branches).count()
    high_signal_11 = ManagedDeviceModel.objects.filter(rx_signal__lte=-11, branch__in=user_permitted_branches).count()

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
    if user_has_global_device_access(request.user):
        devices = ManagedDeviceModel.objects.all()
        neighbors = DeviceNeighbors.objects.all()
    else:
        permitted_branches = get_permitted_branches(request.user)
        devices = ManagedDeviceModel.objects.filter(branch__in=permitted_branches)
        device_macs = devices.exclude(switch_mac__isnull=True).exclude(switch_mac='').values_list('switch_mac', flat=True)
        neighbors = DeviceNeighbors.objects.filter(mac1__in=device_macs, mac2__in=device_macs)

    return render(request, 'neighbor_devices_map.html', {'devices': devices, 'neighbors': neighbors})
