import logging
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from snmp.models import Device as DeviceModel
from snmp.models import DeviceModel as DeviceModelModel

from .access import (
    convert_uptime_to_human_readable,
    get_permitted_branches,
    user_can_access_managed_device,
)

try:
    from ping3 import ping as ping_host
except Exception:  # pragma: no cover - optional dependency
    ping_host = None

logger = logging.getLogger("ICMP RESPONSE")

SNMP_COMMUNITY = settings.SNMP_DEFAULT_COMMUNITY_RO
OID_SYSTEM_HOSTNAME = 'iso.3.6.1.2.1.1.5.0'
OID_SYSTEM_UPTIME = 'iso.3.6.1.2.1.1.3.0'
OID_SYSTEM_DESCRIPTION = 'iso.3.6.1.2.1.1.1.0'


def refresh_device_status(managed_device):
    ip_addr = managed_device.ip
    try:
        if ip_addr is None:
            return HttpResponse(status=400)
        if ping_host is None:
            logger.warning('ping3 is not installed; cannot refresh device ICMP status')
            return HttpResponse(status=503)

        host_alive = ping_host(ip_addr, unit='ms', size=64, timeout=2)
        if host_alive is not None:
            managed_device.status = True
            managed_device.save()
            return JsonResponse({'status': 'UP' if managed_device.status else 'DOWN'})
        return redirect('device_detail', managed_device.pk)
    except Exception as exc:
        logger.info('Error refreshing status for %s: %s', ip_addr, exc)
        return HttpResponse(status=500)


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
@require_POST
def update_optical_info(request, pk):
    from snmp.lib.update_port_info import SNMPUpdater

    managed_device = get_object_or_404(DeviceModel, pk=pk)
    if not user_can_access_managed_device(request.user, managed_device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        snmp_updater = SNMPUpdater(managed_device, settings.SNMP_DEFAULT_COMMUNITY_RO)
        snmp_updater.update_switch_data()
        return JsonResponse(
            {
                'rx_signal': managed_device.rx_signal,
                'tx_signal': managed_device.tx_signal,
                'sfp_vendor': managed_device.sfp_vendor,
                'part_number': managed_device.part_number,
            }
        )
    except Exception:
        return JsonResponse({'error': 'An error occurred during SNMP update.'}, status=500)


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
@require_POST
def update_device_ports_data(request, pk):
    from snmp.lib.update_port_info import PortsInfo

    managed_device = get_object_or_404(DeviceModel, pk=pk)
    if not user_can_access_managed_device(request.user, managed_device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        port_info = PortsInfo()
        port_info.create_switch_ports(managed_device)
        return JsonResponse({'message': 'Device port data updated successfully.'})
    except Exception as exc:
        return JsonResponse({'error': f'An error occurred during device port update: {exc}'}, status=500)


@login_required
def devices_offline(request):
    user_permitted_branches = get_permitted_branches(request.user)
    offline_items = DeviceModel.objects.filter(
        status=False,
        branch__in=user_permitted_branches,
    ).order_by('ats')

    search_query = request.GET.get('search')
    if search_query:
        offline_items = offline_items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(offline_items, 25)
    page_number = request.GET.get('page')
    page_items = paginator.get_page(page_number)
    return render(request, 'device_list_offline.html', {'down_devices': page_items})


@login_required
def devices_high_signal_15(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = DeviceModel.objects.filter(
        rx_signal__lte=-15,
        rx_signal__gt=-20,
        branch__in=user_permitted_branches,
    ).order_by('rx_signal')

    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return render(request, 'devices_high_sig_15.html', {'devices_high_signal': page_items})


@login_required
def devices_high_signal_10(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = DeviceModel.objects.filter(
        rx_signal__lte=-11,
        rx_signal__gt=-15,
        branch__in=user_permitted_branches,
    ).order_by('rx_signal')

    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return render(request, 'devices_high_sig_10.html', {'devices_high_signal': page_items})


@login_required
def devices_high_signal_20(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = DeviceModel.objects.filter(
        rx_signal__lte=-20,
        branch__in=user_permitted_branches,
    ).order_by('rx_signal')

    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 25)
    page_items = paginator.get_page(request.GET.get('page'))
    return render(request, 'devices_high_sig.html', {'devices_high_signal': page_items})


@login_required
def devices_high_signal_11(request):
    user_permitted_branches = get_permitted_branches(request.user)
    items = DeviceModel.objects.filter(
        rx_signal__lte=-11,
        branch__in=user_permitted_branches,
    ).order_by('rx_signal')

    search_query = request.GET.get('search')
    if search_query:
        items = items.filter(
            Q(pk__icontains=search_query)
            | Q(device_type__vendor__name__icontains=search_query)
            | Q(hostname__icontains=search_query)
            | Q(ip__icontains=search_query)
            | Q(device_type__device_model__icontains=search_query)
            | Q(status__icontains=search_query)
            | Q(sfp_vendor__icontains=search_query)
            | Q(part_number__icontains=search_query)
            | Q(rx_signal__icontains=search_query)
            | Q(tx_signal__icontains=search_query)
        )

    paginator = Paginator(items, 100)
    page_items = paginator.get_page(request.GET.get('page'))
    return render(request, 'devices_high_sig_11.html', {'devices_high_signal': page_items})


@login_required
@permission_required('snmp.change_switch', raise_exception=True)
@require_POST
def refresh_device_inventory(request, pk):
    from snmp.management.commands.snmp import perform_snmpwalk

    managed_device = get_object_or_404(DeviceModel, pk=pk)
    if not user_can_access_managed_device(request.user, managed_device):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    hostname_resp = perform_snmpwalk(managed_device.ip, OID_SYSTEM_HOSTNAME, SNMP_COMMUNITY)
    uptime_resp = perform_snmpwalk(managed_device.ip, OID_SYSTEM_UPTIME, SNMP_COMMUNITY)
    if not hostname_resp or not uptime_resp:
        return JsonResponse({'error': 'Missing SNMP response'}, status=502)

    match_hostname = re.search(r'SNMPv2-MIB::sysName.0 = (.+)', hostname_resp[0])
    if not match_hostname:
        return JsonResponse({'error': 'Unexpected hostname response format.'}, status=500)
    managed_device.hostname = match_hostname.group(1).strip()

    match_uptime = re.search(r'SNMPv2-MIB::sysUpTime.0\s*=\s*(\d+)', uptime_resp[0])
    if not match_uptime:
        return JsonResponse({'error': 'Unexpected uptime response format.'}, status=500)
    managed_device.uptime = convert_uptime_to_human_readable(match_uptime.group(1).strip())

    description_resp = perform_snmpwalk(managed_device.ip, OID_SYSTEM_DESCRIPTION, SNMP_COMMUNITY)
    if description_resp:
        response_description = str(description_resp[0]).strip().split()
        with transaction.atomic():
            if not managed_device.device_type:
                model_instance = DeviceModelModel.objects.filter(device_model__in=response_description).first()
                if model_instance:
                    managed_device.device_type = model_instance
            elif managed_device.device_type.device_model not in response_description:
                model_instance = DeviceModelModel.objects.filter(device_model__in=response_description).first()
                if model_instance:
                    managed_device.device_type = model_instance

    managed_device.save()
    return redirect('device_detail', pk=pk)
